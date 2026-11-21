"""Tests for subtitle discovery and SRT -> VTT conversion."""

from __future__ import annotations

from pathlib import Path

from app.services.subtitles import media_sidecars, read_vtt, srt_to_vtt, subtitle_sidecars


def _touch(folder: Path, *names: str) -> None:
    for n in names:
        (folder / n).write_text("x")


def test_srt_to_vtt() -> None:
    src = "\ufeff1\r\n00:00:01,000 --> 00:00:02,500\r\nHi, there\r\n"
    assert srt_to_vtt(src) == "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\nHi, there\n"


def test_read_vtt_passes_vtt_through(tmp_path: Path) -> None:
    body = "WEBVTT\n\n00:00.000 --> 00:01.000\nx\n"
    f = tmp_path / "a.en.vtt"
    f.write_text(body)
    assert read_vtt(f) == body


def test_sidecars_found_and_vtt_wins(tmp_path: Path) -> None:
    _touch(
        tmp_path, "talk.mp4", "talk.fr-orig.srt", "talk.en.srt", "talk.en.vtt", "talk.txt",
        "talk.en.txt",
    )  # fmt: skip
    media = tmp_path / "talk.mp4"
    assert subtitle_sidecars(media) == {
        "fr-orig": tmp_path / "talk.fr-orig.srt",
        "en": tmp_path / "talk.en.vtt",
    }
    assert len(media_sidecars(media)) == 5


def test_sidecars_ignore_longer_stem(tmp_path: Path) -> None:
    _touch(
        tmp_path, "talk.mp4", "talk.2.mp4", "talk.2.srt", "talk.2.en.srt", "talk-2.mp4",
        "talk-2.en.srt",
    )  # fmt: skip
    assert media_sidecars(tmp_path / "talk.mp4") == []
    assert subtitle_sidecars(tmp_path / "talk.2.mp4") == {"en": tmp_path / "talk.2.en.srt"}


def test_sidecars_missing_folder(tmp_path: Path) -> None:
    media = tmp_path / "nope" / "a.mp4"
    assert media_sidecars(media) == []
    assert subtitle_sidecars(media) == {}
