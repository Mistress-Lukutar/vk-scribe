"""
File:   test_subtitles.py
Brief:  Tests for WebVTT parsing and sidecar discovery.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.3.1
"""

from __future__ import annotations

from pathlib import Path

from vk_scribe.infrastructure.subtitles import find_subtitles, parse_vtt

SAMPLE_VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
Привет <c>мир</c>

00:00:03.000 --> 00:00:05,500
Привет <c>мир</c>

00:00:05.000 --> 00:00:08.000
Вторая строка
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_vtt_collapses_repeated_lines(tmp_path: Path) -> None:
    """Consecutive duplicate cue texts must be collapsed to one segment."""
    vtt = _write(tmp_path / "subs.vtt", SAMPLE_VTT)
    segments = parse_vtt(vtt)
    assert [seg.text for seg in segments] == ["Привет мир", "Вторая строка"]


def test_parse_vtt_timecodes_and_tags(tmp_path: Path) -> None:
    """Tags must be stripped; timecodes parse to seconds."""
    vtt = _write(tmp_path / "subs.vtt", SAMPLE_VTT)
    segments = parse_vtt(vtt)
    assert segments[0].start == 1.0
    assert segments[0].end == 3.0
    assert segments[1].end == 8.0


def test_parse_vtt_accepts_comma_millis(tmp_path: Path) -> None:
    """Comma-separated milliseconds must parse like dot-separated ones.

    Milliseconds are dropped by design: the pipeline is second-resolution.
    """
    content = "WEBVTT\n\n00:00:10,000 --> 00:00:11,500\nСтрока с запятой\n"
    vtt = _write(tmp_path / "comma.vtt", content)
    segments = parse_vtt(vtt)
    assert segments[0].start == 10.0
    assert segments[0].end == 11.0


def test_parse_vtt_strips_inline_timestamp_tags(tmp_path: Path) -> None:
    """Inline <HH:MM:SS.mmm> karaoke tags must be removed from text."""
    content = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nСло<00:00:01.500>во\n"
    vtt = _write(tmp_path / "inline.vtt", content)
    segments = parse_vtt(vtt)
    assert segments[0].text == "Слово"


def test_parse_vtt_empty_file(tmp_path: Path) -> None:
    """A cue-less file must yield an empty segment list."""
    vtt = _write(tmp_path / "empty.vtt", "WEBVTT\n")
    assert parse_vtt(vtt) == []


def test_find_subtitles_skips_empty_candidates(tmp_path: Path) -> None:
    """Empty sidecar files must be skipped in favour of a usable one."""
    (tmp_path / "video.mp4").touch()
    _write(tmp_path / "video.ru.vtt", "WEBVTT\n")
    _write(tmp_path / "video.vtt", SAMPLE_VTT)
    segments = find_subtitles(tmp_path / "video.mp4")
    assert len(segments) == 2


def test_find_subtitles_no_sidecar(tmp_path: Path) -> None:
    """A video without sidecar subtitles must yield an empty list."""
    (tmp_path / "video.mp4").touch()
    assert find_subtitles(tmp_path / "video.mp4") == []
