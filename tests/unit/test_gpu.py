"""
File:   test_gpu.py
Brief:  Tests for the CUDA runtime probe (safe without a GPU).
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.1
"""

from __future__ import annotations

from vk_scribe.infrastructure.gpu import _can_load, cuda_runtime_available


def test_cuda_runtime_available_returns_bool() -> None:
    """The probe must answer without raising, with or without a GPU."""
    assert isinstance(cuda_runtime_available(), bool)


def test_can_load_missing_library_is_false() -> None:
    """A nonexistent library name must simply answer False."""
    assert _can_load(("definitely_not_a_real_library_42.dll",)) is False
