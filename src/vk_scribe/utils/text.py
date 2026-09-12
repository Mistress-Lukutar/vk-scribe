"""
File:   text.py
Brief:  Text normalization helpers for fuzzy comparison.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy comparison (lowercase, alphanumerics only).

    Keeps Latin and Cyrillic letters (including ``ё``) plus digits, so
    OCR variants of the same slide compare equal regardless of
    punctuation, spacing, or case.

    Args:
        text: Raw OCR or transcript text.

    Returns:
        Squashed lowercase string without punctuation/whitespace.
    """
    return re.sub(r"[^0-9a-zа-яё]+", "", text.lower())
