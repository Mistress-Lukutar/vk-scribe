"""
File:   exceptions.py
Brief:  Package-wide exception hierarchy.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations


class VkScribeError(Exception):
    """Base exception for all vk_scribe errors."""


class DownloadError(VkScribeError):
    """Raised when playlist downloading fails."""


class ModelDownloadError(VkScribeError):
    """Raised when an OCR model cannot be fetched."""


class VideoOpenError(VkScribeError):
    """Raised when a video file cannot be decoded."""


class SlideExportError(VkScribeError):
    """Raised when slide images or the PDF cannot be written."""
