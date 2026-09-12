"""
File:   timecodes.py
Brief:  Timecode formatting helpers.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations


def format_timecode(seconds: float) -> str:
    """Format seconds as [HH:MM:SS].

    Args:
        seconds: Non-negative timestamp in seconds (negatives clamp to 0).

    Returns:
        Zero-padded timecode string.
    """
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
