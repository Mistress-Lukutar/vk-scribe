# ruff: noqa: B008  # typer.Option/Argument in defaults is the Typer idiom
"""
File:   download.py
Brief:  "download" subcommand: fetch a playlist without text extraction.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

from pathlib import Path

import typer

from vk_scribe.cli.logging_setup import configure_logging
from vk_scribe.infrastructure.downloader import download_playlist


def download(
    url: str = typer.Argument(..., help="VK Video playlist URL"),
    output_dir: Path = typer.Option(
        Path("vk_playlist"), "--output-dir", "-o", help="Target folder"
    ),
    cookies_file: Path | None = typer.Option(
        None, "--cookies", help="Netscape cookies file for private videos"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logs"),
) -> None:
    """Only download the playlist (no text extraction)."""
    configure_logging(verbose)
    download_playlist(url, output_dir, cookies_file=cookies_file)
