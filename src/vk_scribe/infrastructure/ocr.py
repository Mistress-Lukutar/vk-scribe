"""
File:   ocr.py
Brief:  Slide OCR via RapidOCR with the East-Slavic recognition model.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vk_scribe import __version__
from vk_scribe.core.constants import (
    CLI_NAME,
    DEFAULT_OCR_MIN_SCORE,
    ESLAV_MODEL_SOURCES,
    MODEL_CACHE_DIR,
)
from vk_scribe.core.exceptions import ModelDownloadError
from vk_scribe.core.models import SlideRecord
from vk_scribe.utils.timecodes import format_timecode

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


def _download_file(urls: list[str], target: Path) -> None:
    """Download a file from the first reachable mirror.

    Args:
        urls: Candidate URLs, tried in order.
        target: Destination path (created atomically via .part file).

    Raises:
        ModelDownloadError: If every mirror fails.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    for url in urls:
        try:
            logger.info("Downloading %s", url)
            request = urllib.request.Request(
                url, headers={"User-Agent": f"{CLI_NAME}/{__version__}"}
            )
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                partial.open("wb") as handle,
            ):
                shutil.copyfileobj(response, handle)
            partial.replace(target)
            return
        except OSError as exc:
            logger.warning("Mirror failed: %s", exc)
    partial.unlink(missing_ok=True)
    raise ModelDownloadError(f"All mirrors failed for {target.name}")


def ensure_ocr_models(cache_dir: Path = MODEL_CACHE_DIR) -> dict[str, Path]:
    """Make sure the East-Slavic recognition model and dict exist locally.

    Args:
        cache_dir: Folder holding the downloaded model files.

    Returns:
        Mapping with ``rec_model`` and ``rec_keys`` paths.
    """
    paths = {
        "rec_model": cache_dir / "eslav_rec.onnx",
        "rec_keys": cache_dir / "eslav_dict.txt",
    }
    model_files = zip(paths.items(), ESLAV_MODEL_SOURCES.values(), strict=True)
    for (key, path), urls in model_files:
        if not path.exists():
            _download_file(urls, path)
        logger.debug("OCR %s: %s", key, path)
    return paths


def _to_float(value: object) -> float:
    """Best-effort float conversion, 0.0 on failure.

    Args:
        value: Score of any type a RapidOCR build may emit.

    Returns:
        The score as float, or 0.0 if it cannot be parsed.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


class SlideOcr:
    """Thin wrapper around RapidOCR with a Russian-capable rec model."""

    def __init__(self, min_score: float = DEFAULT_OCR_MIN_SCORE) -> None:
        """Load the OCR engine (downloads models on first run).

        Args:
            min_score: Minimum line confidence to keep in the output.
        """
        from rapidocr_onnxruntime import RapidOCR  # deferred: heavy import

        model_paths = ensure_ocr_models()
        self._engine = RapidOCR(
            rec_model_path=str(model_paths["rec_model"]),
            rec_keys_path=str(model_paths["rec_keys"]),
            rec_img_shape=[3, 48, 320],  # PP-OCRv5 input geometry
        )
        self._min_score = min_score
        logger.info("RapidOCR ready (eslav rec model, min score %.2f)", min_score)

    def read_slide(self, frame: np.ndarray) -> str:
        """Recognize all text on a slide frame.

        Args:
            frame: BGR frame containing the slide.

        Returns:
            Recognized lines joined by newlines (possibly empty).
        """
        rows = self._normalize_rows(self._engine(frame))
        lines = [
            text for text, score in rows if score >= self._min_score and len(text) > 1
        ]
        return "\n".join(lines)

    @staticmethod
    def _normalize_rows(output: object) -> list[tuple[str, float]]:
        """Normalize RapidOCR output across package versions.

        ``rapidocr_onnxruntime`` v1 returns ``(rows, elapse)`` with rows
        shaped ``[box, text, score]``; some builds emit dict rows
        ``{"box": ..., "text": ..., "score": ...}`` (a 3-key dict unpacks
        into its *key names*, which crashes a naive tuple unpack);
        ``rapidocr`` v3 returns a ``RapidOCROutput`` object with
        ``txts``/``scores`` attributes.

        Args:
            output: Raw value returned by the engine call.

        Returns:
            List of ``(stripped_text, score)`` tuples; malformed rows are
            skipped, non-numeric scores coerce to 0.0.
        """
        result: Any = output[0] if isinstance(output, tuple) else output
        if result is None:
            return []
        if hasattr(result, "txts"):  # rapidocr v3 RapidOCROutput
            texts = getattr(result, "txts", None) or []
            scores = getattr(result, "scores", None) or [1.0] * len(texts)
            return [
                (str(text).strip(), _to_float(score))
                for text, score in zip(texts, scores, strict=False)
            ]
        rows: list[tuple[str, float]] = []
        for row in result:
            if isinstance(row, dict):
                text, score = row.get("text", ""), row.get("score", 0.0)
            elif isinstance(row, (list, tuple)) and len(row) >= 3:
                text, score = row[1], row[2]
            else:
                logger.debug("Skipping malformed OCR row: %r", row)
                continue
            rows.append((str(text).strip(), _to_float(score)))
        return rows


def ocr_slides(
    records: list[SlideRecord],
    ocr: SlideOcr,
    progress: Callable[[float], None] | None = None,
) -> None:
    """Run OCR over every unique slide, filling ``ocr_text`` in place.

    Args:
        records: Unique slide records with representative frames.
        ocr: Initialized OCR wrapper.
        progress: Optional callback invoked with the completed fraction
            (0..1) of slides as recognition advances.
    """
    for idx, record in enumerate(records, start=1):
        if record.frame is None:
            continue
        record.ocr_text = ocr.read_slide(record.frame)
        logger.debug(
            "OCR slide %d/%d [%s]: %d chars",
            idx,
            len(records),
            format_timecode(record.timecodes[0]),
            len(record.ocr_text),
        )
        if progress is not None:
            progress(idx / len(records))
        # frame stays alive: write_slides_pdf() needs it after OCR
