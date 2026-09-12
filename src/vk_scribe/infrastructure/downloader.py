"""
File:   downloader.py
Brief:  Playlist downloading via the yt-dlp Python API and the
        filename -> URL manifest.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.0
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from vk_scribe.core.constants import ARCHIVE_NAME, MANIFEST_NAME
from vk_scribe.core.exceptions import DownloadError

logger = logging.getLogger(__name__)


class DownloadHooks:
    """Progress callbacks emitted during a playlist download.

    The base implementation does nothing, so ``DownloadHooks()`` gives a
    silent, logging-only run; the CLI subclasses it to drive progress
    bars. Override only the hooks of interest.
    """

    def on_playlist_start(self, total: int, already: int) -> None:
        """Report the playlist structure before downloading starts.

        Args:
            total: Number of entries in the playlist.
            already: Entries already on disk from earlier runs.
        """

    def on_video_start(self, position: int, total: int, title: str) -> None:
        """Report that a video began downloading.

        Args:
            position: 1-based position in the playlist (0 if unknown).
            total: Playlist size (0 if unknown).
            title: Video title.
        """

    def on_fraction(self, fraction: float | None) -> None:
        """Report byte progress of the current download stream.

        Args:
            fraction: 0..1 of the current stream, or None when the size
                is unknown.
        """

    def on_status(self, message: str) -> None:
        """Report a non-download phase (merging streams, subtitles).

        Args:
            message: Short human-readable status.
        """

    def on_video_end(self, success: bool) -> None:
        """Report that a video finished processing.

        Args:
            success: True when the final file was written.
        """


def ensure_ffmpeg() -> None:
    """Verify that ffmpeg is available on PATH.

    Raises:
        DownloadError: If ffmpeg is not found.
    """
    if shutil.which("ffmpeg") is None:
        raise DownloadError(
            "ffmpeg not found on PATH. Install it first "
            "(https://ffmpeg.org/download.html) — yt-dlp needs it "
            "to mux VK streams into mp4."
        )


def download_playlist(
    url: str,
    output_dir: Path,
    cookies_file: Path | None = None,
    hooks: DownloadHooks | None = None,
) -> None:
    """Download every video of a VK playlist into the output directory.

    Files are named ``NNN - Title [id].mp4`` so alphabetical order matches
    playlist order. A manifest with source URLs and a yt-dlp download
    archive (for resumable incremental runs) are stored alongside.
    Videos already listed in the download archive are skipped without
    invoking the downloader at all.

    Args:
        url: VK Video playlist URL.
        output_dir: Target folder (created if missing).
        cookies_file: Optional Netscape cookies file for private videos.
        hooks: Optional progress callbacks.

    Raises:
        DownloadError: If ffmpeg is missing or yt-dlp reports failures.
    """
    hooks = hooks or DownloadHooks()
    ensure_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = _extract_flat(url)
    if entries:
        _write_manifest(entries, output_dir)
        already = _count_archived(entries, output_dir / ARCHIVE_NAME)
        hooks.on_playlist_start(len(entries), already)
        if already >= len(entries):
            logger.info(
                "All %d playlist entries are already on disk, nothing to download",
                len(entries),
            )
            return

    seen_position = -1

    def on_progress(data: dict[str, Any]) -> None:
        """Forward yt-dlp byte progress to the hooks."""
        nonlocal seen_position
        info: dict[str, Any] = data.get("info_dict") or {}
        position = int(info.get("playlist_index") or 0)
        if position != seen_position:
            seen_position = position
            title = str(info.get("title") or "video")
            hooks.on_video_start(position, len(entries), title)
        if data.get("status") == "downloading":
            downloaded = _as_float(data.get("downloaded_bytes"))
            expected = _as_float(data.get("total_bytes")) or _as_float(
                data.get("total_bytes_estimate")
            )
            hooks.on_fraction(downloaded / expected if expected > 0.0 else None)
        elif data.get("status") == "finished":
            hooks.on_fraction(1.0)

    def on_postprocess(data: dict[str, Any]) -> None:
        """Report merging phases and completed videos to the hooks."""
        if data.get("status") == "started":
            hooks.on_status("Merging streams, saving subtitles...")
        elif (
            data.get("status") == "finished"
            and data.get("postprocessor") == "MoveFiles"
        ):
            hooks.on_video_end(True)

    options: dict[str, Any] = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(
            output_dir / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
        ),
        "download_archive": str(output_dir / ARCHIVE_NAME),
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["ru.*", "en.*"],
        "convertsubtitles": "vtt",
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [on_progress],
        "postprocessor_hooks": [on_postprocess],
        "logger": _YtdlpLogBridge(),
    }
    if cookies_file is not None:
        options["cookiefile"] = str(cookies_file)

    logger.info("Downloading playlist: %s", url)
    import yt_dlp  # imported lazily: extract-only runs may skip it

    with yt_dlp.YoutubeDL(options) as ydl:
        retcode = ydl.download([url])
    if retcode != 0:
        raise DownloadError(
            "Some videos failed to download. Run again to retry — "
            "already downloaded videos are skipped automatically."
        )


class _YtdlpLogBridge:
    """Adapt yt-dlp messages to the stdlib logging tree.

    yt-dlp accepts a logger object with debug/warning/error; everything
    it prints (progress lines included) arrives here and is routed under
    the ``vk_scribe.ytdlp`` logger, which stays quiet unless verbose.
    """

    def __init__(self) -> None:
        """Bind the bridge to its stdlib logger."""
        self._logger = logging.getLogger("vk_scribe.ytdlp")

    def debug(self, message: str, *args: object) -> None:
        """Log a yt-dlp screen message at debug level."""
        self._logger.debug(message, *args)

    def info(self, message: str, *args: object) -> None:
        """Log a yt-dlp informational message."""
        self._logger.info(message, *args)

    def warning(self, message: str, *args: object) -> None:
        """Log a yt-dlp warning."""
        self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        """Log a yt-dlp error."""
        self._logger.error(message, *args)


def _extract_flat(url: str) -> list[dict[str, Any]]:
    """Read the playlist structure without downloading anything.

    Args:
        url: VK Video playlist URL.

    Returns:
        Flat entries that carry an id (empty when extraction fails —
        the download itself then runs without playlist totals).
    """
    try:
        import yt_dlp  # imported lazily: extract-only runs may skip it

        options: dict[str, Any] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "logger": _YtdlpLogBridge(),
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = (info or {}).get("entries") or []
        return [entry for entry in entries if entry and entry.get("id")]
    except Exception as exc:  # structure info is optional, never fatal
        logger.warning("Could not read the playlist structure: %s", exc)
        return []


def _count_archived(entries: list[dict[str, Any]], archive_path: Path) -> int:
    """Count playlist entries already recorded in the yt-dlp archive.

    Args:
        entries: Flat playlist entries with ``id`` and extractor key.
        archive_path: Path of the ``.download_archive.txt`` file.

    Returns:
        Number of entries whose archive line is already recorded.
    """
    if not archive_path.exists():
        return 0
    recorded = set(
        archive_path.read_text(encoding="utf-8", errors="replace").splitlines()
    )
    archived = 0
    for entry in entries:
        extractor = str(entry.get("extractor_key") or entry.get("ie_key") or "").lower()
        if f"{extractor} {entry['id']}" in recorded:
            archived += 1
    return archived


def _as_float(value: object) -> float:
    """Best-effort float conversion, 0.0 on failure.

    Args:
        value: Byte count of any type a hook payload may carry.

    Returns:
        The value as float, or 0.0 if it cannot be parsed.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _write_manifest(entries: list[dict[str, Any]], output_dir: Path) -> None:
    """Store a filename -> webpage URL mapping for later report headers.

    Args:
        entries: Flat playlist entries in playlist order.
        output_dir: Folder containing the downloaded videos.
    """
    manifest: dict[str, str] = {}
    for idx, entry in enumerate(entries, start=1):
        title = entry.get("title", "untitled")
        filename = f"{idx:03d} - {title} [{entry['id']}].mp4"
        manifest[filename] = str(entry.get("url") or entry.get("webpage_url") or "")
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Manifest saved: %s (%d entries)", manifest_path, len(manifest))


def load_manifest(output_dir: Path) -> dict[str, str]:
    """Load the filename -> URL manifest written during download.

    Args:
        output_dir: Folder containing the manifest.

    Returns:
        Mapping of video filename to its source URL (empty if missing).
    """
    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    try:
        data: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Corrupt manifest ignored: %s", manifest_path)
        return {}
    if not isinstance(data, dict):
        logger.warning("Manifest is not an object, ignored: %s", manifest_path)
        return {}
    return {str(key): str(value) for key, value in data.items()}
