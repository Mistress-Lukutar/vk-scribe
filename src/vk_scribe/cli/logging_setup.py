"""
File:   logging_setup.py
Brief:  Console logging configuration for the CLI entry point.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

import logging


def configure_logging(verbose: bool) -> None:
    """Set up console logging for the CLI entry point.

    Args:
        verbose: Enable DEBUG-level output when True.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
