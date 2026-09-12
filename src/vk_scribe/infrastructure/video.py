"""
File:   video.py
Brief:  Slide detection, deduplication, and merging over decoded video
        frames (OpenCV).
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from vk_scribe.core.constants import (
    DEFAULT_CHANGE_RATIO,
    DEFAULT_DEDUP_RATIO,
    DEFAULT_MIN_SLIDE_SECONDS,
    DEFAULT_SAMPLE_INTERVAL,
    MERGE_MIN_CHARS,
    PIXEL_DIFF_FLOOR,
    VIDEO_GLOBS,
)
from vk_scribe.core.exceptions import VideoOpenError
from vk_scribe.core.models import SlideRecord
from vk_scribe.utils.text import normalize_text

logger = logging.getLogger(__name__)


def find_video_files(directory: Path) -> list[Path]:
    """Collect processable video files in a directory, sorted by name.

    Args:
        directory: Folder to scan (non-recursive).

    Returns:
        Sorted list of video paths.
    """
    videos: list[Path] = []
    for pattern in VIDEO_GLOBS:
        videos.extend(directory.glob(pattern))
    return sorted(set(videos))


def _frame_signature(frame: np.ndarray) -> np.ndarray:
    """Compute a small grayscale signature used for frame differencing.

    Args:
        frame: Full-resolution BGR frame.

    Returns:
        36x64 uint8 grayscale thumbnail.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)


def detect_slide_changes(
    video_path: Path,
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
    change_ratio: float = DEFAULT_CHANGE_RATIO,
    min_slide_seconds: float = DEFAULT_MIN_SLIDE_SECONDS,
    progress: Callable[[float], None] | None = None,
) -> list[SlideRecord]:
    """Detect slide boundaries and pick one frame per stable slide segment.

    Frames are sampled every ``sample_interval`` seconds; a boundary is
    declared when the fraction of strongly-changed pixels (abs diff above
    ``PIXEL_DIFF_FLOOR``) between consecutive signatures exceeds
    ``change_ratio``. A pixel-count metric is used instead of a mean diff
    because text edits on a fixed template move few pixels but strongly,
    while codec noise moves many pixels weakly. Segments shorter than
    ``min_slide_seconds`` (fade transitions, build animations) are merged
    into their predecessor.

    Args:
        video_path: Video file to analyze.
        sample_interval: Seconds between sampled frames.
        change_ratio: Changed-pixel fraction (0-1) marking a slide change.
        min_slide_seconds: Minimum stable segment duration.
        progress: Optional callback invoked with the scanned fraction
            (0..1) of the video as frames are decoded.

    Returns:
        Slide records with timecodes and representative frames (no OCR yet).

    Raises:
        VideoOpenError: If the file cannot be decoded.
    """
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise VideoOpenError(f"Cannot open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if frame_count > 0 else 0.0
    logger.info(
        "Scanning %s (%.1f min, %.0f fps, step %.1fs)",
        video_path.name,
        duration / 60,
        fps,
        sample_interval,
    )

    samples: list[tuple[float, np.ndarray, np.ndarray]] = []
    timestamp = 0.0
    while timestamp <= duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
        ok, frame = capture.read()
        if ok and frame is not None:
            samples.append((timestamp, frame, _frame_signature(frame)))
        if progress is not None and duration > 0.0:
            progress(min(timestamp / duration, 1.0))
        timestamp += sample_interval
    if progress is not None:
        progress(1.0)
    capture.release()
    if not samples:
        raise VideoOpenError(f"No frames decoded from: {video_path}")

    boundaries = [0]
    for idx in range(1, len(samples)):
        changed = cv2.absdiff(samples[idx][2], samples[idx - 1][2])
        if float(np.mean(changed > PIXEL_DIFF_FLOOR)) > change_ratio:
            boundaries.append(idx)
    boundaries.append(len(samples))

    records: list[SlideRecord] = []
    # boundaries is one longer than boundaries[1:] by design (segment pairs)
    for start_idx, end_idx in zip(boundaries, boundaries[1:], strict=False):
        segment = samples[start_idx:end_idx]
        if not segment:
            continue
        seg_duration = segment[-1][0] - segment[0][0] + sample_interval
        if records and seg_duration < min_slide_seconds:
            continue  # too short: transition artifact, keep previous slide
        # last sample = richest frame for progressive "build" sequences
        anchor = segment[-1]
        records.append(
            SlideRecord(
                timecodes=[anchor[0]],
                frame=anchor[1],
                signature=anchor[2],
            )
        )
    logger.info("Detected %d raw slide segments", len(records))
    return records


def deduplicate_slides(
    records: list[SlideRecord],
    dedup_ratio: float = DEFAULT_DEDUP_RATIO,
) -> list[SlideRecord]:
    """Merge records whose frames are visually identical.

    Two slides match when the changed-pixel fraction between their
    signatures stays below ``dedup_ratio`` — the same metric used for
    change detection, so anything too weak to trigger a boundary cannot
    create a duplicate either. Handles lecturers returning to an earlier
    slide: all occurrence timecodes are collected on the first record.

    Args:
        records: Slide records in chronological order.
        dedup_ratio: Max changed-pixel fraction (0-1) to call slides equal.

    Returns:
        Deduplicated slide records.
    """
    unique: list[SlideRecord] = []
    for record in records:
        match = next(
            (
                known
                for known in unique
                if known.signature is not None
                and record.signature is not None
                and float(
                    np.mean(
                        cv2.absdiff(known.signature, record.signature)
                        > PIXEL_DIFF_FLOOR
                    )
                )
                <= dedup_ratio
            ),
            None,
        )
        if match is None:
            unique.append(record)
        else:
            match.timecodes.extend(record.timecodes)
    logger.info("Unique slides after visual dedup: %d", len(unique))
    return unique


def merge_progressive_slides(records: list[SlideRecord]) -> list[SlideRecord]:
    """Collapse "build" sequences where bullets appear one by one.

    If the normalized text of a slide is contained in a neighbour's text
    (and long enough to be meaningful), the shorter one is dropped and
    its timecodes migrate to the richer slide.

    Args:
        records: OCR'd slide records in chronological order.

    Returns:
        Merged slide records.
    """
    merged: list[SlideRecord] = []
    for record in records:
        norm = normalize_text(record.ocr_text)
        if not norm:
            continue  # blank slide (section divider, picture-only)
        if merged:
            prev = merged[-1]
            prev_norm = normalize_text(prev.ocr_text)
            shorter, longer = (
                (prev_norm, norm) if len(prev_norm) <= len(norm) else (norm, prev_norm)
            )
            if len(shorter) >= MERGE_MIN_CHARS and shorter in longer:
                keeper = record if len(norm) >= len(prev_norm) else prev
                keeper.timecodes = sorted(set(prev.timecodes + record.timecodes))
                if keeper is not merged[-1]:
                    merged[-1] = keeper
                continue
        merged.append(record)
    logger.info("Slides after progressive-merge: %d", len(merged))
    return merged
