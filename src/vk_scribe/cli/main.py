"""
File:   main.py
Brief:  Typer application assembly and command registration.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

import typer

from vk_scribe.cli.commands.download import download
from vk_scribe.cli.commands.extract import extract
from vk_scribe.cli.commands.run import run
from vk_scribe.core.constants import CLI_NAME

app = typer.Typer(
    name=CLI_NAME,
    help="Download a VK Video playlist and extract speech + slide text.",
    no_args_is_help=True,
)
app.command(name="run")(run)
app.command(name="download")(download)
app.command(name="extract")(extract)
