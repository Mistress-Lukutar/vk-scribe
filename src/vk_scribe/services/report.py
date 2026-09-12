"""
File:   report.py
Brief:  Combined text report and slide-deck PDF writing.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2

from vk_scribe.core.constants import SLIDE_IMAGE_QUALITY, SLIDES_DIR_SUFFIX
from vk_scribe.core.exceptions import SlideExportError
from vk_scribe.core.models import SlideRecord, TranscriptSegment
from vk_scribe.utils.timecodes import format_timecode

logger = logging.getLogger(__name__)


def write_report(
    video_path: Path,
    transcript: list[TranscriptSegment],
    subtitles: list[TranscriptSegment],
    slides: list[SlideRecord],
    source_url: str = "",
) -> Path:
    """Write the combined text report next to the video.

    Layout: speech transcript, then VK subtitles (if any), then OCR'd
    slide texts — every block prefixed with its [HH:MM:SS] timecode.

    Args:
        video_path: Video file the report belongs to.
        transcript: Whisper speech segments.
        subtitles: VK subtitle segments (may be empty).
        slides: OCR'd slide records.
        source_url: Original VK video URL for the header.

    Returns:
        Path of the written .txt file.
    """
    report_path = video_path.with_suffix(".txt")
    lines: list[str] = [
        f"# {video_path.stem}",
        f"# Source: {source_url or 'local file'}",
        "",
        "=" * 60,
        "РЕЧЬ (Whisper)",
        "=" * 60,
    ]
    if transcript:
        for seg in transcript:
            lines.append(f"[{format_timecode(seg.start)}] {seg.text}")
    else:
        lines.append("(нет)")
    lines.append("")
    if subtitles:
        lines.extend(["=" * 60, "СУБТИТРЫ VK", "=" * 60])
        for seg in subtitles:
            lines.append(f"[{format_timecode(seg.start)}] {seg.text}")
        lines.append("")
    lines.extend(["=" * 60, "СЛАЙДЫ (OCR)", "=" * 60])
    if slides:
        for idx, slide in enumerate(slides, start=1):
            timecodes = ", ".join(
                f"[{format_timecode(t)}]" for t in sorted(slide.timecodes)
            )
            lines.append(f"--- Слайд {idx} {timecodes}")
            lines.append(slide.ocr_text)
            lines.append("")
    else:
        lines.append("(не обнаружены)")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report written: %s", report_path)
    return report_path


def write_slides_pdf(video_path: Path, slides: list[SlideRecord]) -> Path | None:
    """Save unique slide frames as images and assemble them into a PDF.

    Each slide becomes one PDF page in order of first appearance, embedded
    losslessly via img2pdf (no recompression beyond the initial JPEG save).
    Images land in a ``<video_stem>_slides/`` subfolder, the PDF sits next
    to the video as ``<video_stem>.pdf``.

    Args:
        video_path: Video file the slides were extracted from.
        slides: Unique slide records with representative frames.

    Returns:
        Path of the written PDF, or None when there is nothing to save.

    Raises:
        SlideExportError: If JPEG encoding of a slide fails.
    """
    frames = [slide.frame for slide in slides if slide.frame is not None]
    if not frames:
        logger.info("No slide frames captured, PDF skipped")
        return None
    slides_dir = video_path.parent / f"{video_path.stem}{SLIDES_DIR_SUFFIX}"
    slides_dir.mkdir(exist_ok=True)
    image_paths: list[Path] = []
    for idx, frame in enumerate(frames, start=1):
        image_path = slides_dir / f"slide_{idx:03d}.jpg"
        # cv2.imwrite silently fails on non-ASCII paths on Windows (it uses
        # fopen with the ANSI codepage); encode in memory, write via pathlib
        ok, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, SLIDE_IMAGE_QUALITY]
        )
        if not ok:
            raise SlideExportError(f"JPEG encoding failed for slide {idx}")
        image_path.write_bytes(buffer.tobytes())
        image_paths.append(image_path)

    import img2pdf  # deferred: only needed when slides were found

    pdf_path = video_path.with_suffix(".pdf")
    with pdf_path.open("wb") as handle:
        # pass raw bytes: some img2pdf builds treat a list of str as raw
        # image data instead of filenames
        handle.write(img2pdf.convert(*[path.read_bytes() for path in image_paths]))
    logger.info(
        "Slide deck saved: %s (%d pages, images in %s)",
        pdf_path,
        len(image_paths),
        slides_dir.name,
    )
    return pdf_path
