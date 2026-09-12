"""
File:   test_models.py
Brief:  Tests for the ExtractOptions validation model.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vk_scribe.core.models import ExtractOptions


def test_defaults_match_constants() -> None:
    """Default options must load without any explicit arguments."""
    options = ExtractOptions()
    assert options.whisper_model == "small"
    assert options.device == "auto"
    assert options.sample_interval == 2.0
    assert options.limit is None


def test_change_ratio_must_be_fraction() -> None:
    """change_ratio outside (0, 1) must be rejected."""
    with pytest.raises(ValidationError):
        ExtractOptions(change_ratio=0.0)
    with pytest.raises(ValidationError):
        ExtractOptions(change_ratio=1.5)


def test_sample_interval_must_be_positive() -> None:
    """Non-positive sampling intervals must be rejected."""
    with pytest.raises(ValidationError):
        ExtractOptions(sample_interval=0.0)


def test_limit_must_be_at_least_one() -> None:
    """Zero/negative limits must be rejected."""
    with pytest.raises(ValidationError):
        ExtractOptions(limit=0)


def test_device_is_restricted() -> None:
    """Unknown device names must be rejected."""
    with pytest.raises(ValidationError):
        ExtractOptions(device="tpu")


def test_full_valid_construction() -> None:
    """A fully populated valid model must round-trip its fields."""
    options = ExtractOptions(
        whisper_model="medium",
        device="cuda",
        language="ru",
        skip_pdf=True,
        limit=3,
    )
    assert (options.whisper_model, options.device, options.language) == (
        "medium",
        "cuda",
        "ru",
    )
    assert options.skip_pdf is True
    assert options.limit == 3
