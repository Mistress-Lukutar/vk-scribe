"""
File:   conftest.py
Brief:  Shared pytest fixtures for vk_scribe tests.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from vk_scribe.core.models import SlideRecord


@pytest.fixture
def make_slide() -> Callable[..., SlideRecord]:
    """Factory producing synthetic slide records for logic tests."""

    def _make(
        ocr_text: str = "",
        signature_value: int = 0,
        timecodes: list[float] | None = None,
    ) -> SlideRecord:
        return SlideRecord(
            timecodes=timecodes if timecodes is not None else [0.0],
            frame=np.full((36, 64, 3), signature_value, dtype=np.uint8),
            signature=np.full((36, 64), signature_value, dtype=np.uint8),
            ocr_text=ocr_text,
        )

    return _make
