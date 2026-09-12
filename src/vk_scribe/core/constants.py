"""
File:   constants.py
Brief:  Package-wide tunables and fixed file names for vk_scribe.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from pathlib import Path

CLI_NAME = "vk-scribe"  # CLI display name
VIDEO_GLOBS = ("*.mp4", "*.mkv", "*.webm", "*.avi")  # containers to process
MANIFEST_NAME = "_playlist_manifest.json"  # filename -> source URL mapping
ARCHIVE_NAME = ".download_archive.txt"  # yt-dlp download archive file
MODEL_CACHE_DIR = Path.home() / ".cache" / "vk_scribe" / "ocr"  # OCR models

# East-Slavic (Russian) PP-OCRv5 recognition model for RapidOCR.
# Detection/classification are language-agnostic, so the packaged
# default models are reused; only the recognition part is swapped.
ESLAV_MODEL_SOURCES: dict[str, list[str]] = {
    "rec.onnx": [
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/"
        "onnx/PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile.onnx",
        "https://huggingface.co/monkt/paddleocr-onnx/resolve/main/"
        "languages/eslav/rec.onnx",
    ],
    "dict.txt": [
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/"
        "paddle/PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile/"
        "ppocrv5_cyrillic_dict.txt",
        "https://huggingface.co/monkt/paddleocr-onnx/resolve/main/"
        "languages/eslav/dict.txt",
    ],
}

DEFAULT_SAMPLE_INTERVAL = 2.0  # seconds between sampled frames
PIXEL_DIFF_FLOOR = 30  # per-pixel abs diff (0-255) counted as "changed"
DEFAULT_CHANGE_RATIO = 0.02  # fraction of changed pixels = slide change
DEFAULT_MIN_SLIDE_SECONDS = 3.0  # ignore segments shorter than this
DEFAULT_DEDUP_RATIO = 0.02  # changed-pixel fraction below which slides match
DEFAULT_OCR_MIN_SCORE = 0.5  # drop OCR lines below this confidence
DEFAULT_WHISPER_MODEL = "small"  # good speed/quality trade-off
SLIDE_IMAGE_QUALITY = 95  # JPEG quality for extracted slide images
SLIDES_DIR_SUFFIX = "_slides"  # folder suffix for per-video slide images
MERGE_MIN_CHARS = 15  # min text length for substring slide merging
