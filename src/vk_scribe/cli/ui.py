"""
File:   ui.py
Brief:  Rich-based progress display shared by the CLI commands and the
        interactive menu.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from vk_scribe.infrastructure.downloader import DownloadHooks
from vk_scribe.services.pipeline import ExtractHooks

# Human-readable names for the pipeline stages, keyed by the stage id
# that ExtractHooks.on_stage emits.
STAGE_LABELS: dict[str, str] = {
    "speech": "Recognizing speech",
    "slides": "Detecting slides",
    "ocr": "Reading slide text",
    "report": "Writing report",
}

TITLE_WIDTH = 36  # video-title chars kept on a progress line


def _shorten(text: str, width: int) -> str:
    """Clip a long title so the progress line stays readable.

    Args:
        text: Title to clip.
        width: Maximum number of characters to keep.

    Returns:
        The clipped title with an ellipsis when truncated.
    """
    return text if len(text) <= width else text[: width - 1] + "..."


class _Bars:
    """Shared plumbing for the two-bar layout (overall + current)."""

    def __init__(self, progress: Progress, overall_label: str) -> None:
        """Create the hidden overall and current tasks.

        Args:
            progress: Rich progress both bars render in.
            overall_label: Description of the overall bar.
        """
        self._overall = progress.add_task(overall_label, total=None, visible=False)
        self._current = progress.add_task("", total=None, visible=False)


class DownloadBars(_Bars, DownloadHooks):
    """Render playlist download progress as two bars.

    The overall bar counts newly downloaded videos; the current bar
    follows the active video's byte progress and processing status.
    """

    def __init__(self, progress: Progress, console: Console) -> None:
        """Create the bars (hidden until the first event).

        Args:
            progress: Rich progress both bars render in.
            console: Console used for extra informational lines.
        """
        super().__init__(progress, "Downloading videos")
        self._progress = progress
        self._console = console

    def on_playlist_start(self, total: int, already: int) -> None:
        """Show how many videos remain once the playlist is known."""
        todo = max(total - already, 0)
        self._progress.update(self._overall, total=todo, completed=0, visible=todo > 0)
        if already:
            self._console.print(
                f"[dim]Playlist holds {total} videos; {already} already on "
                f"disk, {todo} to download.[/]"
            )

    def on_video_start(self, position: int, total: int, title: str) -> None:
        """Label the current bar with the video being downloaded."""
        prefix = f"[{position}/{total}] " if position > 0 else ""
        self._progress.update(
            self._current,
            description=f"{prefix}{_shorten(title, TITLE_WIDTH + 12)}",
            total=None,
            completed=0,
            visible=True,
        )

    def on_fraction(self, fraction: float | None) -> None:
        """Advance the current bar; None keeps it pulsing (unknown size)."""
        if fraction is None:
            self._progress.update(self._current, total=None, completed=0)
        else:
            self._progress.update(
                self._current,
                total=1.0,
                completed=min(max(fraction, 0.0), 1.0),
            )

    def on_status(self, message: str) -> None:
        """Show an indeterminate status (merging streams, subtitles)."""
        self._progress.update(
            self._current,
            description=_shorten(message, 64),
            total=None,
            completed=0,
            visible=True,
        )

    def on_video_end(self, success: bool) -> None:
        """Count a fully written video on the overall bar."""
        if success:
            self._progress.advance(self._overall)
        self._progress.update(self._current, visible=False)


class ExtractBars(_Bars, ExtractHooks):
    """Render per-video extraction progress as two bars.

    The overall bar counts processed videos; the current bar shows the
    active video, its stage (speech, slides, OCR), and stage progress.
    """

    def __init__(self, progress: Progress) -> None:
        """Create the bars (hidden until the first event).

        Args:
            progress: Rich progress both bars render in.
        """
        super().__init__(progress, "Processing videos")
        self._progress = progress
        self._overall_total: int | None = None
        self._prefix = ""  # e.g. "[3/12]" of the active video
        self._name = ""  # active video title, kept for stage labels

    def on_video_start(self, index: int, total: int, name: str) -> None:
        """Label the current bar with the video being processed."""
        if self._overall_total is None:
            self._overall_total = total
            self._progress.update(self._overall, total=total, visible=True)
        self._prefix = f"[{index}/{total}]"
        self._name = name
        self._progress.update(
            self._current,
            description=f"{self._prefix} {_shorten(name, TITLE_WIDTH + 12)}",
            total=None,
            completed=0,
            visible=True,
        )

    def on_status(self, message: str) -> None:
        """Show an indeterminate preparation message (model loading)."""
        self._progress.update(
            self._current,
            description=_shorten(message, 64),
            total=None,
            completed=0,
            visible=True,
        )

    def on_stage(self, stage: str) -> None:
        """Switch the current bar to a named processing stage."""
        label = STAGE_LABELS.get(stage, stage)
        title = _shorten(self._name, TITLE_WIDTH)
        self._progress.update(
            self._current,
            description=(
                f"{self._prefix} {label} - {title}"
                if title
                else f"{self._prefix} {label}"
            ),
            total=None,
            completed=0,
        )

    def on_fraction(self, fraction: float) -> None:
        """Advance the current bar to the given stage fraction."""
        self._progress.update(
            self._current,
            total=1.0,
            completed=min(max(fraction, 0.0), 1.0),
        )

    def on_video_end(self, success: bool) -> None:
        """Count a processed video on the overall bar."""
        if success:
            self._progress.advance(self._overall)
        self._progress.update(self._current, visible=False)


class CliProgress:
    """Own the rich Progress display and the hook objects driving it.

    Use as a context manager around the work::

        with CliProgress(console) as progress:
            download_playlist(..., hooks=progress.download_hooks())
            extract_folder(..., hooks=progress.extract_hooks())
    """

    def __init__(self, console: Console) -> None:
        """Create the renderer (rendering starts on enter).

        Args:
            console: Rich console used for rendering.
        """
        self._console = console
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeRemainingColumn(elapsed_when_finished=True),
            console=console,
        )
        self.download = DownloadBars(self._progress, console)
        self.extract = ExtractBars(self._progress)

    def __enter__(self) -> CliProgress:
        """Start rendering the progress display."""
        self._progress.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop rendering the progress display."""
        self._progress.stop()

    def download_hooks(self) -> DownloadHooks:
        """Return the hooks for ``download_playlist``.

        Returns:
            The download bar driver.
        """
        return self.download

    def extract_hooks(self) -> ExtractHooks:
        """Return the hooks for ``extract_folder``.

        Returns:
            The extraction bar driver.
        """
        return self.extract
