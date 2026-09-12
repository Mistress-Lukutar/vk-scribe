"""
File:   test_timecodes.py
Brief:  Tests for timecode formatting.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

from vk_scribe.utils.timecodes import format_timecode


def test_formats_hours_minutes_seconds() -> None:
    """3661 seconds must render as 01:01:01."""
    assert format_timecode(3661) == "01:01:01"


def test_zero_renders_all_zeroes() -> None:
    """Zero must render as 00:00:00."""
    assert format_timecode(0) == "00:00:00"


def test_negative_clamps_to_zero() -> None:
    """Negative input must clamp to 00:00:00, not crash."""
    assert format_timecode(-5.0) == "00:00:00"


def test_fractional_seconds_truncated() -> None:
    """1.9 s must truncate (not round) to 00:00:01."""
    assert format_timecode(1.9) == "00:00:01"
