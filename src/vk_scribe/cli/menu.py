"""
File:   menu.py
Brief:  Interactive menu: step-by-step plain-language prompts instead of
        CLI flags.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from vk_scribe.cli.logging_setup import configure_logging
from vk_scribe.cli.ui import CliProgress
from vk_scribe.core.constants import (
    DEFAULT_CHANGE_RATIO,
    DEFAULT_SAMPLE_INTERVAL,
    DEFAULT_WHISPER_MODEL,
)
from vk_scribe.core.exceptions import VkScribeError
from vk_scribe.core.models import ExtractOptions
from vk_scribe.infrastructure.downloader import download_playlist
from vk_scribe.infrastructure.video import find_video_files
from vk_scribe.services.pipeline import extract_folder

logger = logging.getLogger(__name__)

WHISPER_MODELS: list[tuple[str, str]] = [
    # (model name, plain-language hint)
    ("tiny", "fastest, rough text"),
    ("base", "fast, lower accuracy"),
    ("small", "good balance"),
    ("medium", "more accurate, much slower"),
    ("large-v3", "best quality, needs a powerful GPU"),
]

LANGUAGES: list[tuple[str | None, str]] = [
    # (language code or None, display line)
    (None, "detect automatically"),
    ("ru", "Russian"),
    ("en", "English"),
]


@dataclass
class MenuPlan:
    """Everything the menu gathered for one work run."""

    action: str  # "run" | "download" | "extract"
    url: str = ""
    folder: Path = Path("vk_playlist")
    cookies: Path | None = None
    options: ExtractOptions | None = None  # None for download-only runs


def _ask_numbered(
    console: Console, title: str, variants: list[str], default: int = 1
) -> int:
    """Ask the user to pick one entry from a numbered list.

    Args:
        console: Console used for rendering.
        title: Question printed above the list.
        variants: One display line per option.
        default: 1-based index used when the user presses Enter.

    Returns:
        The chosen 1-based index.
    """
    console.print(f"\n[bold]{title}[/]")
    for number, label in enumerate(variants, start=1):
        marker = "   [dim]<- default[/]" if number == default else ""
        console.print(f"  [bold cyan]{number}.[/] {label}{marker}")
    while True:
        raw = typer.prompt(
            "Your choice", default=str(default), show_default=False
        ).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(variants):
            return int(raw)
        console.print(f"[yellow]Please enter a number 1-{len(variants)}.[/]")


def _ask_url(console: Console) -> str:
    """Ask for the playlist URL until a plausible one is given.

    Args:
        console: Console used for feedback.

    Returns:
        The URL, with a scheme prepended when omitted.
    """
    while True:
        raw = (
            str(typer.prompt("\nPlaylist URL (e.g. https://vkvideo.ru/playlist/...)"))
            .strip()
            .strip('"')
        )
        if not raw:
            console.print("[yellow]A URL is required to download.[/]")
            continue
        if "://" not in raw:
            raw = f"https://{raw}"
        return raw


def _ask_output_folder(console: Console) -> Path:
    """Ask where the playlist should be saved.

    Args:
        console: Console used for feedback.

    Returns:
        The chosen target folder.
    """
    while True:
        raw = (
            typer.prompt("\nFolder to save the videos into", default="vk_playlist")
            .strip()
            .strip('"')
        )
        if raw:
            return Path(raw)
        console.print("[yellow]Please name a folder.[/]")


def _ask_cookies(console: Console) -> Path | None:
    """Ask for an optional cookies file for private playlists.

    Args:
        console: Console used for feedback.

    Returns:
        Path to the cookies file, or None when skipped.
    """
    while True:
        raw = (
            typer.prompt(
                "\nCookies file (only needed for private playlists; "
                "press Enter to skip)",
                default="",
                show_default=False,
            )
            .strip()
            .strip('"')
        )
        if not raw:
            return None
        path = Path(raw)
        if path.exists():
            return path
        console.print(f"[yellow]File not found: {path} — check the path.[/]")


def _ask_extract_folder(console: Console) -> Path:
    """Ask for a local folder that contains downloaded videos.

    Args:
        console: Console used for feedback.

    Returns:
        The chosen folder, guaranteed to hold video files.
    """
    while True:
        raw = typer.prompt("\nFolder with the downloaded videos").strip().strip('"')
        folder = Path(raw) if raw else None
        if folder is None or not folder.is_dir():
            console.print(f"[yellow]Folder does not exist: {raw}[/]")
            continue
        videos = find_video_files(folder)
        if not videos:
            console.print("[yellow]No video files (.mp4/.mkv/.webm/.avi) there.[/]")
            continue
        done = sum(1 for video in videos if video.with_suffix(".txt").exists())
        console.print(f"Found {len(videos)} videos; {done} already have text reports.")
        return folder


def _ask_float(console: Console, question: str, default: float) -> float:
    """Ask for a positive number with a default.

    Args:
        console: Console used for feedback.
        question: Question text.
        default: Value used when the user presses Enter.

    Returns:
        The parsed positive float.
    """
    while True:
        raw = typer.prompt(question, default=str(default), show_default=False).strip()
        try:
            value = float(raw)
        except ValueError:
            console.print("[yellow]Please enter a number.[/]")
            continue
        if value <= 0:
            console.print("[yellow]Please enter a number greater than zero.[/]")
            continue
        return value


def _ask_limit(console: Console) -> int | None:
    """Ask how many videos to process at most.

    Args:
        console: Console used for feedback.

    Returns:
        The limit, or None for "all videos".
    """
    while True:
        raw = typer.prompt(
            "\nProcess only the first N videos? (press Enter for all)",
            default="",
            show_default=False,
        ).strip()
        if not raw:
            return None
        if raw.isdigit() and int(raw) >= 1:
            return int(raw)
        console.print("[yellow]Enter a whole number, or press Enter for all.[/]")


def _ask_extract_options(console: Console) -> ExtractOptions:
    """Walk through the extraction settings one friendly question at a time.

    Args:
        console: Console used for feedback.

    Returns:
        Validated options ready for ``extract_folder``.
    """
    model_number = _ask_numbered(
        console,
        "Speech recognition quality (Whisper model):",
        [f"{name} — {hint}" for name, hint in WHISPER_MODELS],
        default=WHISPER_MODELS.index(
            next(m for m in WHISPER_MODELS if m[0] == DEFAULT_WHISPER_MODEL)
        )
        + 1,
    )
    whisper_model = WHISPER_MODELS[model_number - 1][0]

    language_number = _ask_numbered(
        console,
        "Spoken language:",
        [hint for _, hint in LANGUAGES],
    )
    language = LANGUAGES[language_number - 1][0]

    while True:
        steps = _ask_numbered(
            console,
            "What to extract from each video?",
            [
                "Everything: speech text + slide text + PDF of the slides",
                "Speech text only (faster, no slide reading)",
                "Slide text only (no speech recognition)",
                "Let me pick the steps one by one",
            ],
        )
        if steps == 2:
            skip_whisper, skip_ocr, skip_pdf = False, True, True
        elif steps == 3:
            skip_whisper, skip_ocr, skip_pdf = True, False, True
        elif steps == 4:
            do_speech = typer.confirm("\nRecognize speech (Whisper)?", default=True)
            do_slides = typer.confirm("Read slide text (OCR)?", default=True)
            do_pdf = do_slides and typer.confirm(
                "Also build a PDF of the slides?", default=True
            )
            skip_whisper, skip_ocr, skip_pdf = (
                not do_speech,
                not do_slides,
                not do_pdf,
            )
        else:
            skip_whisper, skip_ocr, skip_pdf = False, False, False
        if not (skip_whisper and skip_ocr):
            break
        console.print(
            "[yellow]At least one of speech or slide reading must stay on.[/]"
        )

    limit = _ask_limit(console)
    overwrite = typer.confirm(
        "\nRedo videos that already have a text report?", default=False
    )

    sample_interval = DEFAULT_SAMPLE_INTERVAL
    change_ratio = DEFAULT_CHANGE_RATIO
    device = "auto"
    if typer.confirm("\nTune advanced settings?", default=False):
        device_number = _ask_numbered(
            console,
            "Whisper device:",
            [
                "auto — use the GPU when available",
                "cuda — force the NVIDIA GPU",
                "cpu — force the processor (slowest)",
            ],
        )
        device = ("auto", "cuda", "cpu")[device_number - 1]
        sample_interval = _ask_float(
            console,
            "Seconds between checked frames (slide detection)",
            sample_interval,
        )
        change_ratio = _ask_float(
            console,
            "Slide-change sensitivity, fraction of changed pixels "
            "(lower = more sensitive)",
            change_ratio,
        )

    return ExtractOptions(
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
    )


def _show_summary(console: Console, plan: MenuPlan) -> None:
    """Print everything the user chose, for a final check.

    Args:
        console: Console used for rendering.
        plan: The gathered choices.
    """
    lines: list[str] = []
    if plan.action in ("run", "download"):
        lines.append(f"[bold]Playlist:[/]  {plan.url}")
        lines.append(f"[bold]Save to:[/]   {plan.folder}")
        if plan.cookies is not None:
            lines.append(f"[bold]Cookies:[/]   {plan.cookies}")
    else:
        lines.append(f"[bold]Folder:[/]   {plan.folder}")
    if plan.options is not None:
        options = plan.options
        steps: list[str] = []
        if not options.skip_whisper:
            steps.append(f"speech ({options.whisper_model})")
        if not options.skip_ocr:
            steps.append("slide text")
        if not options.skip_pdf and not options.skip_ocr:
            steps.append("PDF deck")
        lines.append(f"[bold]Extract:[/]   {' + '.join(steps)}")
        lines.append(f"[bold]Language:[/]  {options.language or 'auto-detect'}")
        if options.limit is not None:
            lines.append(f"[bold]Limit:[/]     first {options.limit} videos")
        lines.append(f"[bold]Redo done:[/]   {'yes' if options.overwrite else 'no'}")
    console.print(
        Panel.fit("\n".join(lines), title="Ready to start", border_style="green")
    )


def _execute(console: Console, plan: MenuPlan) -> None:
    """Run the chosen job with live progress bars.

    Args:
        console: Console used for rendering.
        plan: The confirmed choices.

    Raises:
        VkScribeError: Propagated from the pipeline on failure.
    """
    with CliProgress(console) as progress:
        if plan.action in ("run", "download"):
            download_playlist(
                plan.url,
                plan.folder,
                cookies_file=plan.cookies,
                hooks=progress.download_hooks(),
            )
        if plan.action in ("run", "extract") and plan.options is not None:
            extract_folder(plan.folder, plan.options, hooks=progress.extract_hooks())


def _report_results(console: Console, plan: MenuPlan) -> None:
    """Print a plain-language summary of what is on disk now.

    Args:
        console: Console used for rendering.
        plan: The executed choices.
    """
    if plan.action == "download":
        console.print(
            f"\n[bold green]Download finished.[/] Videos are in: "
            f"{plan.folder.resolve()}"
        )
        return
    videos = find_video_files(plan.folder)
    reports = [video for video in videos if video.with_suffix(".txt").exists()]
    decks = list(plan.folder.glob("*.pdf"))
    console.print(
        f"\n[bold green]Done![/] Text reports: {len(reports)} of "
        f"{len(videos)} videos; PDF slide decks: {len(decks)}."
    )
    console.print(f"Everything is saved in: {plan.folder.resolve()}")


def _hint_for(error: VkScribeError) -> str:
    """Return a friendly next step for common failures.

    Args:
        error: The raised pipeline error.

    Returns:
        Hint text, or an empty string when nothing applies.
    """
    message = str(error).lower()
    if "ffmpeg" in message:
        return (
            "Fix: close this window and start .\\run.ps1 again — it will "
            "offer to install ffmpeg for you."
        )
    if "whisper" in message or "huggingface" in message:
        return (
            "Fix: if huggingface.co is unreachable, first run\n"
            "  set HF_ENDPOINT=https://hf-mirror.com\n"
            "in this console, then try again."
        )
    if "download" in message or "yt-dlp" in message:
        return (
            "Fix: run again to retry the failed videos (finished ones are "
            "skipped). If many fail, update the downloader: uv add yt-dlp -U"
        )
    return ""


def _run_menu(console: Console) -> None:
    """Gather choices, confirm, and execute.

    Args:
        console: Console used for rendering.

    Raises:
        typer.Exit: When the user declines to start or picks Exit.
    """
    console.print(
        Panel.fit(
            "[bold]vk-scribe[/] — turn a VK Video playlist into text\n"
            "speech transcript + slide text (OCR) + slide PDF deck",
            border_style="cyan",
        )
    )
    action_number = _ask_numbered(
        console,
        "What would you like to do?",
        [
            "Download a playlist and turn it into text (recommended)",
            "Only download the videos",
            "Extract text from videos already on this computer",
            "Exit",
        ],
    )
    if action_number == 4:
        raise typer.Exit(0)
    action = ("run", "download", "extract")[action_number - 1]

    url = ""
    cookies: Path | None = None
    if action in ("run", "download"):
        url = _ask_url(console)
        folder = _ask_output_folder(console)
        cookies = _ask_cookies(console)
    else:
        folder = _ask_extract_folder(console)
    options = _ask_extract_options(console) if action in ("run", "extract") else None

    plan = MenuPlan(
        action=action, url=url, folder=folder, cookies=cookies, options=options
    )
    _show_summary(console, plan)
    if not typer.confirm("Start now?", default=True):
        raise typer.Exit(0)

    _execute(console, plan)
    _report_results(console, plan)


def menu() -> None:
    """Launch the step-by-step interactive menu."""
    configure_logging(verbose=False)
    console = Console()
    finished = False
    exit_code = 0
    try:
        _run_menu(console)
        finished = True
    except (KeyboardInterrupt, typer.Abort):
        exit_code = 130
        console.print("\n[yellow]Cancelled — no harm done, run again any time.[/]")
    except typer.Exit as exc:
        exit_code = exc.exit_code
    except VkScribeError as exc:
        exit_code = 1
        console.print(f"\n[bold red]Something went wrong:[/] {exc}")
        hint = _hint_for(exc)
        if hint:
            console.print(f"\n[yellow]{hint}[/]")
    except Exception as exc:  # logged, then shown — window must stay readable
        exit_code = 1
        logger.exception("Unexpected error")
        console.print(f"\n[bold red]Unexpected error:[/] {exc}")
    if finished or exit_code != 0:
        console.input("\n[dim]Press Enter to close...[/]")
    if exit_code != 0:
        raise typer.Exit(exit_code)
