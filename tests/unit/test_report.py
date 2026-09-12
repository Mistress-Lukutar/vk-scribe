"""
File:   test_report.py
Brief:  Tests for text report and slide-deck PDF writing.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from vk_scribe.core.models import SlideRecord, TranscriptSegment
from vk_scribe.services.report import write_report, write_slides_pdf


def test_write_report_layout(tmp_path: Path) -> None:
    """Report must contain all three sections with timecodes."""
    video = tmp_path / "001 - Лекция [123].mp4"
    video.touch()
    transcript = [TranscriptSegment(start=12.0, end=15.0, text="Речь")]
    slides = [SlideRecord(timecodes=[7.0, 70.0], ocr_text="Слайд текст")]

    report = write_report(video, transcript, [], slides, "https://vk.video/x")

    content = report.read_text(encoding="utf-8")
    assert report == video.with_suffix(".txt")
    assert "# 001 - Лекция [123]" in content
    assert "# Source: https://vk.video/x" in content
    assert "[00:00:12] Речь" in content
    assert "[00:00:07], [00:01:10]" in content  # sorted slide timecodes
    assert "СЛАЙДЫ (OCR)" in content


def test_write_report_empty_inputs(tmp_path: Path) -> None:
    """Missing transcript and slides must render placeholder markers."""
    video = tmp_path / "clip.mp4"
    video.touch()
    content = write_report(video, [], [], []).read_text(encoding="utf-8")
    assert "(нет)" in content
    assert "(не обнаружены)" in content


def test_write_slides_pdf_creates_deck(
    tmp_path: Path,
    make_slide: Callable[..., SlideRecord],
) -> None:
    """Slides must land as JPEGs and a valid PDF next to the video."""
    video = tmp_path / "lecture.mp4"
    video.touch()
    slides = [
        make_slide(ocr_text="first"),
        make_slide(ocr_text="second"),
    ]

    pdf_path = write_slides_pdf(video, slides)

    assert pdf_path is not None and pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    slides_dir = tmp_path / "lecture_slides"
    assert [path.name for path in sorted(slides_dir.glob("*.jpg"))] == [
        "slide_001.jpg",
        "slide_002.jpg",
    ]
    assert pdf_path.read_bytes()[:5] == b"%PDF-"


def test_write_slides_pdf_no_frames(tmp_path: Path) -> None:
    """No frames at all must skip the PDF without writing anything."""
    video = tmp_path / "empty.mp4"
    video.touch()
    assert write_slides_pdf(video, []) is None
    assert not (tmp_path / "empty.pdf").exists()
