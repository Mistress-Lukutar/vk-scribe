"""
File:   transcriber.py
Brief:  Speech transcription via faster-whisper with CUDA -> CPU fallback.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

import logging
from pathlib import Path

from vk_scribe.core.exceptions import VkScribeError
from vk_scribe.core.models import TranscriptSegment

logger = logging.getLogger(__name__)


class SpeechTranscriber:
    """faster-whisper wrapper with automatic CUDA -> CPU fallback."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
    ) -> None:
        """Load the Whisper model.

        Args:
            model_size: Model name (tiny/base/small/medium/large-v3).
            device: ``auto`` (CUDA if usable, else CPU), ``cuda`` or ``cpu``.

        Raises:
            VkScribeError: If the model cannot be loaded on any backend.
        """
        from faster_whisper import WhisperModel  # deferred: heavy import

        attempts = (
            [("cuda", "float16"), ("cpu", "int8")]
            if device == "auto"
            else [(device, "float16" if device == "cuda" else "int8")]
        )
        last_error: Exception | None = None
        for dev, compute_type in attempts:
            try:
                self._model = WhisperModel(
                    model_size, device=dev, compute_type=compute_type
                )
                logger.info(
                    "Whisper '%s' loaded on %s (%s)", model_size, dev, compute_type
                )
                return
            except Exception as exc:  # CUDA libs missing -> try next backend
                logger.warning("Whisper on %s unavailable: %s", dev, exc)
                last_error = exc
        raise VkScribeError(f"Cannot load Whisper model: {last_error}")

    def transcribe(
        self,
        video_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegment]:
        """Transcribe the audio track of a video file.

        Args:
            video_path: Media file (audio decoded via PyAV, no ffmpeg call).
            language: ISO code (``ru``, ``en``) or None for auto-detect.

        Returns:
            Transcript segments with timecodes.
        """
        segments_iter, info = self._model.transcribe(
            str(video_path),
            language=language,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=5,
            condition_on_previous_text=False,
            no_repeat_ngram_size=3,
        )
        segments = [
            TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip())
            for seg in segments_iter
            if seg.text.strip()
        ]
        logger.info(
            "Transcribed %s: %d segments, language=%s (p=%.2f)",
            video_path.name,
            len(segments),
            info.language,
            info.language_probability,
        )
        return segments
