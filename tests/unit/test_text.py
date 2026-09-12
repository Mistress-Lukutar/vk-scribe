"""
File:   test_text.py
Brief:  Tests for text normalization.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from vk_scribe.utils.text import normalize_text


def test_strips_punctuation_and_lowercases() -> None:
    """Punctuation/whitespace must vanish, letters lowercase."""
    assert normalize_text("Hello, World! 123") == "helloworld123"


def test_keeps_cyrillic_including_yo() -> None:
    """Cyrillic letters (and 'ё') must survive normalization."""
    assert normalize_text("Привет, Ёлка!") == "приветёлка"


def test_empty_and_symbol_only_input() -> None:
    """Symbol-only input must normalize to an empty string."""
    assert normalize_text("!!! ... ???") == ""
    assert normalize_text("") == ""
