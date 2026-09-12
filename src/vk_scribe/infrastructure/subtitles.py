"""
File:   subtitles.py
Brief:  VK sidecar subtitle (.vtt) discovery and parsing.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from vk_scribe.core.models import TranscriptSegment

logger = logging.getLogger(__name__)

_VTT_TIMESTAMP = re.compile(
    r"(\d{2}:\d{2}:\d{2})[.,]\d{3}\s*-->\s*(\d{2}:\d{2}:\d{2})[.,]\d{3}"
)
_VTT_TAG = re.compile(r"<[^>]+>")


def _parse_vtt_time(value: str) -> float:
    """Convert an HH:MM:SS timecode to seconds.

    Args:
        value: Timecode string with colon-separated parts.

    Returns:
        Timestamp in seconds.
    """
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def parse_vtt(path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT subtitle file into deduplicated segments.

    VK auto-subtitles repeat each line across overlapping windows, so
    consecutive duplicates are collapsed.

    Args:
        path: Path to the .vtt file.

    Returns:
        Subtitle segments in chronological order.
    """
    segments: list[TranscriptSegment] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = 0
    while idx < len(lines):
        match = _VTT_TIMESTAMP.search(lines[idx])
        if not match:
            idx += 1
            continue
        start = _parse_vtt_time(match.group(1))
        end = _parse_vtt_time(match.group(2))
        idx += 1
        text_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            cleaned = _VTT_TAG.sub("", lines[idx])
            cleaned = re.sub(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>", "", cleaned).strip()
            if cleaned:
                text_lines.append(cleaned)
            idx += 1
        text = " ".join(text_lines).strip()
        if text and (not segments or segments[-1].text != text):
            segments.append(TranscriptSegment(start=start, end=end, text=text))
    return segments


def find_subtitles(video_path: Path) -> list[TranscriptSegment]:
    """Load any .vtt file sitting next to a video.

    Args:
        video_path: Video file whose sidecar subtitles are wanted.

    Returns:
        Subtitle segments (empty list when no .vtt exists).
    """
    candidates = sorted(video_path.parent.glob(f"{video_path.stem}*.vtt"))
    for candidate in candidates:
        segments = parse_vtt(candidate)
        if segments:
            logger.info(
                "Found VK subtitles: %s (%d lines)", candidate.name, len(segments)
            )
            return segments
    return []
