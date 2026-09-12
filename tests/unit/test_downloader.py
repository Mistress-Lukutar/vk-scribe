"""
File:   test_downloader.py
Brief:  Tests for manifest loading (no network involved).
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

import json
from pathlib import Path

from vk_scribe.infrastructure.downloader import load_manifest


def test_load_manifest_roundtrip(tmp_path: Path) -> None:
    """A valid manifest must load as a filename -> URL mapping."""
    data = {"001 - Title [42].mp4": "https://vkvideo.ru/video-1_42"}
    (tmp_path / "_playlist_manifest.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    assert load_manifest(tmp_path) == data


def test_load_manifest_missing_returns_empty(tmp_path: Path) -> None:
    """A folder without a manifest must yield an empty mapping."""
    assert load_manifest(tmp_path) == {}


def test_load_manifest_corrupt_returns_empty(tmp_path: Path) -> None:
    """A corrupt manifest must be ignored with an empty mapping."""
    (tmp_path / "_playlist_manifest.json").write_text("{not json", encoding="utf-8")
    assert load_manifest(tmp_path) == {}
