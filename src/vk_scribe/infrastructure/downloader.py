"""
File:   downloader.py
Brief:  Playlist downloading via yt-dlp and the filename -> URL manifest.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.0
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from vk_scribe.core.constants import ARCHIVE_NAME, MANIFEST_NAME
from vk_scribe.core.exceptions import DownloadError

logger = logging.getLogger(__name__)


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
) -> None:
    """Download every video of a VK playlist into the output directory.

    Files are named ``NNN - Title [id].mp4`` so alphabetical order matches
    playlist order. A manifest with source URLs and a yt-dlp download
    archive (for resumable incremental runs) are stored alongside.

    Args:
        url: VK Video playlist URL.
        output_dir: Target folder (created if missing).
        cookies_file: Optional Netscape cookies file for private videos.

    Raises:
        DownloadError: If ffmpeg is missing or yt-dlp exits with an error.
    """
    ensure_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        url,
        "--format",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "--output",
        outtmpl,
        "--download-archive",
        str(output_dir / ARCHIVE_NAME),
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "ru.*,en.*",
        "--convert-subs",
        "vtt",
        "--ignore-errors",
        "--no-progress",
    ]
    if cookies_file is not None:
        command.extend(["--cookies", str(cookies_file)])

    logger.info("Downloading playlist: %s", url)
    result = subprocess.run(command, check=False)  # noqa: S603
    if result.returncode != 0:
        raise DownloadError(f"yt-dlp failed with exit code {result.returncode}")
    _write_manifest(url, output_dir)


def _write_manifest(url: str, output_dir: Path) -> None:
    """Store a filename -> webpage URL mapping for later report headers.

    Args:
        url: Playlist URL (re-extracted in flat mode).
        output_dir: Folder containing the downloaded videos.
    """
    try:
        import yt_dlp  # imported lazily: extract-only runs may skip it

        options = {"extract_flat": True, "quiet": True, "ignoreerrors": True}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = (info or {}).get("entries") or []
        manifest: dict[str, str] = {}
        for idx, entry in enumerate(entries, start=1):
            if not entry or not entry.get("id"):
                continue
            title = entry.get("title", "untitled")
            filename = f"{idx:03d} - {title} [{entry['id']}].mp4"
            manifest[filename] = entry.get("url") or entry.get("webpage_url") or ""
        manifest_path = output_dir / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Manifest saved: %s (%d entries)", manifest_path, len(manifest))
    except Exception as exc:  # manifest is optional metadata, never fatal
        logger.warning("Could not build playlist manifest: %s", exc)


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
