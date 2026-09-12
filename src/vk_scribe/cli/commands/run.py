# ruff: noqa: B008  # typer.Option/Argument in defaults is the Typer idiom
"""
File:   run.py
Brief:  "run" subcommand: download a playlist, then extract text.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

from pathlib import Path

import typer

from vk_scribe.cli.logging_setup import configure_logging
from vk_scribe.core.constants import (
    DEFAULT_CHANGE_RATIO,
    DEFAULT_SAMPLE_INTERVAL,
    DEFAULT_WHISPER_MODEL,
)
from vk_scribe.core.models import ExtractOptions
from vk_scribe.infrastructure.downloader import download_playlist
from vk_scribe.services.pipeline import extract_folder


def run(
    url: str = typer.Argument(..., help="VK Video playlist URL"),
    output_dir: Path = typer.Option(
        Path("vk_playlist"), "--output-dir", "-o", help="Target folder"
    ),
    cookies_file: Path | None = typer.Option(
        None, "--cookies", help="Netscape cookies file for private videos"
    ),
    whisper_model: str = typer.Option(
        DEFAULT_WHISPER_MODEL,
        "--whisper-model",
        "-m",
        help="Whisper size: tiny/base/small/medium/large-v3",
    ),
    device: str = typer.Option(
        "auto", "--device", help="Whisper backend: auto/cuda/cpu"
    ),
    language: str | None = typer.Option(
        None, "--language", "-l", help="Speech language (ru/en); auto if unset"
    ),
    sample_interval: float = typer.Option(
        DEFAULT_SAMPLE_INTERVAL,
        "--sample-interval",
        help="Seconds between sampled frames for slide detection",
    ),
    change_ratio: float = typer.Option(
        DEFAULT_CHANGE_RATIO,
        "--change-ratio",
        help="Changed-pixel fraction per slide change, lower = more sensitive",
    ),
    skip_whisper: bool = typer.Option(
        False, "--skip-whisper", help="Only OCR slides, no speech"
    ),
    skip_ocr: bool = typer.Option(
        False, "--skip-ocr", help="Only speech, no slide OCR"
    ),
    skip_pdf: bool = typer.Option(
        False, "--skip-pdf", help="Do not rebuild the slide deck as a PDF"
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Re-process videos that already have .txt"
    ),
    limit: int | None = typer.Option(
        None, "--limit", help="Process only the first N videos (testing)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logs"),
) -> None:
    """Download the playlist, then extract text for every video."""
    configure_logging(verbose)
    download_playlist(url, output_dir, cookies_file=cookies_file)
    extract_folder(
        output_dir,
        ExtractOptions(
            whisper_model=whisper_model,
            device=device,  # type: ignore[arg-type]
            language=language,
            sample_interval=sample_interval,
            change_ratio=change_ratio,
            skip_whisper=skip_whisper,
            skip_ocr=skip_ocr,
            skip_pdf=skip_pdf,
            overwrite=overwrite,
            limit=limit,
        ),
    )
