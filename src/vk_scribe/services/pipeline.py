"""
File:   pipeline.py
Brief:  Extraction orchestration: per-video pipeline and folder batching.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from vk_scribe.core.exceptions import SlideExportError, VkScribeError
from vk_scribe.core.models import ExtractOptions
from vk_scribe.infrastructure.downloader import load_manifest
from vk_scribe.infrastructure.ocr import SlideOcr, ocr_slides
from vk_scribe.infrastructure.subtitles import find_subtitles
from vk_scribe.infrastructure.transcriber import SpeechTranscriber
from vk_scribe.infrastructure.video import (
    deduplicate_slides,
    detect_slide_changes,
    find_video_files,
    merge_progressive_slides,
)
from vk_scribe.services.report import write_report, write_slides_pdf

if TYPE_CHECKING:
    from vk_scribe.core.models import SlideRecord, TranscriptSegment

logger = logging.getLogger(__name__)


class ExtractHooks:
    """Progress callbacks emitted while extracting text.

    The base implementation does nothing, so ``ExtractHooks()`` gives a
    silent, logging-only run; the CLI subclasses it to drive progress
    bars. Override only the hooks of interest.
    """

    def on_video_start(self, index: int, total: int, name: str) -> None:
        """Report that a video began processing.

        Args:
            index: 1-based position among the videos to process.
            total: Number of videos to process.
            name: Video file name.
        """

    def on_status(self, message: str) -> None:
        """Report a preparation phase (model loading, first-run downloads).

        Args:
            message: Short human-readable status.
        """

    def on_stage(self, stage: str) -> None:
        """Report that a processing stage started for the current video.

        Args:
            stage: One of ``speech``, ``slides``, ``ocr``, ``report``.
        """

    def on_fraction(self, fraction: float) -> None:
        """Report progress inside the current stage.

        Args:
            fraction: Completed fraction, 0..1.
        """

    def on_video_end(self, success: bool) -> None:
        """Report that the current video finished.

        Args:
            success: False when the video failed and was skipped.
        """


def process_video(
    video_path: Path,
    transcriber: SpeechTranscriber | None,
    ocr: SlideOcr | None,
    options: ExtractOptions,
    source_url: str = "",
    hooks: ExtractHooks | None = None,
) -> Path:
    """Run the full extraction pipeline for a single video.

    Args:
        video_path: Video file to process.
        transcriber: Whisper wrapper or None to skip speech.
        ocr: OCR wrapper or None to skip slides.
        options: Tuning parameters (thresholds, skips, language).
        source_url: Original VK URL for the report header.
        hooks: Optional progress callbacks.

    Returns:
        Path of the written report.
    """
    hooks = hooks or ExtractHooks()
    transcript: list[TranscriptSegment] = []
    if transcriber is not None:
        hooks.on_stage("speech")
        transcript = transcriber.transcribe(
            video_path, language=options.language, progress=hooks.on_fraction
        )
    subtitles = find_subtitles(video_path)

    slides: list[SlideRecord] = []
    if ocr is not None:
        hooks.on_stage("slides")
        raw = detect_slide_changes(
            video_path,
            sample_interval=options.sample_interval,
            change_ratio=options.change_ratio,
            min_slide_seconds=options.min_slide_seconds,
            progress=hooks.on_fraction,
        )
        unique = deduplicate_slides(raw, dedup_ratio=options.dedup_ratio)
        hooks.on_stage("ocr")
        ocr_slides(unique, ocr, progress=hooks.on_fraction)
        slides = merge_progressive_slides(unique)

    # report first: a PDF failure must not take the text down with it
    hooks.on_stage("report")
    report_path = write_report(video_path, transcript, subtitles, slides, source_url)
    if slides and not options.skip_pdf:
        try:
            write_slides_pdf(video_path, slides)
        except SlideExportError as exc:
            logger.error("PDF export failed for %s: %s", video_path.name, exc)
    for slide in slides:
        slide.frame = None  # free pixel buffers once the PDF is written
    return report_path


def extract_folder(
    folder: Path,
    options: ExtractOptions,
    hooks: ExtractHooks | None = None,
) -> None:
    """Process every video in a folder, skipping already-done ones.

    Args:
        folder: Folder with videos (reports land next to them).
        options: Tuning parameters (thresholds, skips, limits).
        hooks: Optional progress callbacks.

    Raises:
        VkScribeError: If the folder does not exist.
    """
    hooks = hooks or ExtractHooks()
    if not folder.is_dir():
        raise VkScribeError(f"Not a directory: {folder}")
    videos = find_video_files(folder)
    if options.limit is not None:
        videos = videos[: options.limit]
    pending = [
        video
        for video in videos
        if options.overwrite or not video.with_suffix(".txt").exists()
    ]
    logger.info(
        "Videos: %d total, %d to process, %d already done",
        len(videos),
        len(pending),
        len(videos) - len(pending),
    )
    if not pending:
        logger.info("Nothing to do: every video already has a report.")
        return

    manifest = load_manifest(folder)
    transcriber: SpeechTranscriber | None = None
    if not options.skip_whisper:
        hooks.on_status(
            f"Loading speech model '{options.whisper_model}'"
            " (first run downloads it)..."
        )
        transcriber = SpeechTranscriber(options.whisper_model, options.device)
    ocr: SlideOcr | None = None
    if not options.skip_ocr:
        hooks.on_status("Loading OCR engine...")
        ocr = SlideOcr()

    failures: list[str] = []
    for idx, video in enumerate(pending, start=1):
        logger.debug("=== [%d/%d] %s", idx, len(pending), video.name)
        hooks.on_video_start(idx, len(pending), video.name)
        try:
            process_video(
                video,
                transcriber=transcriber,
                ocr=ocr,
                options=options,
                source_url=manifest.get(video.name, ""),
                hooks=hooks,
            )
            hooks.on_video_end(True)
        except VkScribeError as exc:
            logger.error("Failed: %s", exc)
            hooks.on_video_end(False)
            failures.append(video.name)
    if failures:
        logger.warning("Failed videos (%d): %s", len(failures), failures)
    logger.info("Done. Reports are next to the videos in %s", folder)
