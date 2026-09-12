"""
File:   models.py
Brief:  Data records and the validated extraction options shared across
        the vk_scribe pipeline.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from vk_scribe.core.constants import (
    DEFAULT_CHANGE_RATIO,
    DEFAULT_DEDUP_RATIO,
    DEFAULT_MIN_SLIDE_SECONDS,
    DEFAULT_SAMPLE_INTERVAL,
    DEFAULT_WHISPER_MODEL,
)

if TYPE_CHECKING:
    import numpy as np


@dataclass
class TranscriptSegment:
    """Single speech/subtitle fragment with a timecode."""

    start: float  # seconds from video start
    end: float  # seconds from video start
    text: str


@dataclass
class SlideRecord:
    """A unique slide: representative frame, occurrence times, OCR text."""

    timecodes: list[float] = field(default_factory=list)
    frame: np.ndarray | None = None  # representative BGR frame
    signature: np.ndarray | None = None  # 36x64 grayscale thumb for dedup
    ocr_text: str = ""


class ExtractOptions(BaseModel):
    """Validated tuning parameters for the extraction pipeline.

    Built from CLI flags; guards against nonsensical thresholds before
    any heavy model is loaded.
    """

    whisper_model: str = DEFAULT_WHISPER_MODEL
    device: Literal["auto", "cuda", "cpu"] = "auto"
    language: str | None = None
    sample_interval: float = Field(default=DEFAULT_SAMPLE_INTERVAL, gt=0.0)
    change_ratio: float = Field(default=DEFAULT_CHANGE_RATIO, gt=0.0, lt=1.0)
    min_slide_seconds: float = Field(default=DEFAULT_MIN_SLIDE_SECONDS, gt=0.0)
    dedup_ratio: float = Field(default=DEFAULT_DEDUP_RATIO, gt=0.0, lt=1.0)
    skip_whisper: bool = False
    skip_ocr: bool = False
    skip_pdf: bool = False
    overwrite: bool = False
    limit: int | None = Field(default=None, ge=1)
