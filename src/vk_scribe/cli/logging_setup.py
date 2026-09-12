"""
File:   logging_setup.py
Brief:  Console logging configuration for the CLI entry point.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import logging


def configure_logging(verbose: bool) -> None:
    """Set up console logging for the CLI entry point.

    Non-verbose runs use a plain, message-only format so the console
    stays readable next to the progress bars; verbose runs keep the
    timestamped debug view.

    Args:
        verbose: Enable DEBUG-level output with timestamps when True.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s" if verbose else "%(message)s",
        datefmt="%H:%M:%S",
    )
    # yt-dlp chatters (progress lines, retries); silence it unless
    # debugging — errors still come through at WARNING and above.
    logging.getLogger("vk_scribe.ytdlp").setLevel(
        logging.DEBUG if verbose else logging.WARNING
    )
