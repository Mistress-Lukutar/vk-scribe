"""
File:   test_video.py
Brief:  Tests for slide dedup/merge logic and video file discovery.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from vk_scribe.core.models import SlideRecord
from vk_scribe.infrastructure.video import (
    deduplicate_slides,
    find_video_files,
    merge_progressive_slides,
)


def test_find_video_files_filters_and_sorts(tmp_path: Path) -> None:
    """Only known containers must be returned, sorted by name."""
    for name in ("b.mkv", "a.mp4", "notes.txt", "c.webm", "d.avi"):
        (tmp_path / name).touch()
    found = find_video_files(tmp_path)
    assert [path.name for path in found] == ["a.mp4", "b.mkv", "c.webm", "d.avi"]


def test_deduplicate_merges_identical_signatures(
    make_slide: Callable[..., SlideRecord],
) -> None:
    """Visually identical slides must merge, collecting all timecodes."""
    records = [
        make_slide(signature_value=10, timecodes=[0.0]),
        make_slide(signature_value=200, timecodes=[10.0]),
        make_slide(signature_value=10, timecodes=[60.0]),
    ]
    unique = deduplicate_slides(records)
    assert len(unique) == 2
    assert unique[0].timecodes == [0.0, 60.0]


def test_deduplicate_keeps_distinct_slides(
    make_slide: Callable[..., SlideRecord],
) -> None:
    """Visually different slides must all survive."""
    records = [
        make_slide(signature_value=0, timecodes=[0.0]),
        make_slide(signature_value=255, timecodes=[5.0]),
    ]
    assert len(deduplicate_slides(records)) == 2


def test_merge_progressive_keeps_richest_text(
    make_slide: Callable[..., SlideRecord],
) -> None:
    """A slide whose text is a prefix of the next one must be absorbed."""
    base = "a" * 20  # >= MERGE_MIN_CHARS after normalization
    records = [
        make_slide(ocr_text=base, timecodes=[0.0]),
        make_slide(ocr_text=base + "b" * 5, timecodes=[30.0]),
    ]
    merged = merge_progressive_slides(records)
    assert len(merged) == 1
    assert merged[0].ocr_text == base + "b" * 5
    assert merged[0].timecodes == [0.0, 30.0]


def test_merge_progressive_drops_blank_slides(
    make_slide: Callable[..., SlideRecord],
) -> None:
    """Slides without any OCR text must be dropped entirely."""
    records = [
        make_slide(ocr_text="", timecodes=[0.0]),
        make_slide(ocr_text="полностью уникальный слайд", timecodes=[10.0]),
    ]
    merged = merge_progressive_slides(records)
    assert len(merged) == 1
    assert merged[0].timecodes == [10.0]


def test_merge_progressive_keeps_unrelated_texts(
    make_slide: Callable[..., SlideRecord],
) -> None:
    """Slides with non-overlapping text must not be merged."""
    records = [
        make_slide(ocr_text="титульный слайд номер один", timecodes=[0.0]),
        make_slide(ocr_text="совершенно другой материал", timecodes=[30.0]),
    ]
    assert len(merge_progressive_slides(records)) == 2
