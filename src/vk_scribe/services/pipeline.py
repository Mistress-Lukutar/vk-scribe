"""
File:   pipeline.py
Brief:  Extraction orchestration: per-video pipeline and folder batching.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
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


def process_video(
    video_path: Path,
    transcriber: SpeechTranscriber | None,
    ocr: SlideOcr | None,
    options: ExtractOptions,
    source_url: str = "",
) -> Path:
    """Run the full extraction pipeline for a single video.

    Args:
        video_path: Video file to process.
        transcriber: Whisper wrapper or None to skip speech.
        ocr: OCR wrapper or None to skip slides.
        options: Tuning parameters (thresholds, skips, language).
        source_url: Original VK URL for the report header.

    Returns:
        Path of the written report.
    """
    transcript: list[TranscriptSegment] = []
    if transcriber is not None:
        transcript = transcriber.transcribe(video_path, language=options.language)
    subtitles = find_subtitles(video_path)

    slides: list[SlideRecord] = []
    if ocr is not None:
        raw = detect_slide_changes(
            video_path,
            sample_interval=options.sample_interval,
            change_ratio=options.change_ratio,
            min_slide_seconds=options.min_slide_seconds,
        )
        unique = deduplicate_slides(raw, dedup_ratio=options.dedup_ratio)
        ocr_slides(unique, ocr)
        slides = merge_progressive_slides(unique)

    # report first: a PDF failure must not take the text down with it
    report_path = write_report(video_path, transcript, subtitles, slides, source_url)
    if slides and not options.skip_pdf:
        try:
            write_slides_pdf(video_path, slides)
        except SlideExportError as exc:
            logger.error("PDF export failed for %s: %s", video_path.name, exc)
    for slide in slides:
        slide.frame = None  # free pixel buffers once the PDF is written
    return report_path


def extract_folder(folder: Path, options: ExtractOptions) -> None:
    """Process every video in a folder, skipping already-done ones.

    Args:
        folder: Folder with videos (reports land next to them).
        options: Tuning parameters (thresholds, skips, limits).

    Raises:
        VkScribeError: If the folder does not exist.
    """
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
        return

    manifest = load_manifest(folder)
    transcriber = (
        None
        if options.skip_whisper
        else SpeechTranscriber(options.whisper_model, options.device)
    )
    ocr = None if options.skip_ocr else SlideOcr()

    failures: list[str] = []
    for idx, video in enumerate(pending, start=1):
        logger.info("=== [%d/%d] %s", idx, len(pending), video.name)
        try:
            process_video(
                video,
                transcriber=transcriber,
                ocr=ocr,
                options=options,
                source_url=manifest.get(video.name, ""),
            )
        except VkScribeError as exc:
            logger.error("Failed: %s", exc)
            failures.append(video.name)
    if failures:
        logger.warning("Failed videos (%d): %s", len(failures), failures)
    logger.info("Done. Reports are next to the videos in %s", folder)
