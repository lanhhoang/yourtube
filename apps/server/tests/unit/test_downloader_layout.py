"""Default channel/playlist layout in ``run_download``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yt_dlp

from app.services.downloader import YtdlpProgress, run_download
from app.services.library_paths import PlaylistFolder


@pytest.fixture()
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(info={}, outtmpl=None, process_calls=0, extract_downloads=[])

    def extract_info(self, url, download=True, **_kwargs):
        state.extract_downloads.append(download)
        return dict(state.info)

    def process_ie_result(self, info, download=True, **_kwargs):
        state.process_calls += 1
        state.outtmpl = self.params["outtmpl"]["default"]
        path = self.prepare_filename(info)
        for hook in self.params["progress_hooks"]:
            hook({"status": "finished", "filename": path})
        return info

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    monkeypatch.setattr(yt_dlp.YoutubeDL, "process_ie_result", process_ie_result)
    return state


def test_default_layout_single(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "abc", "title": "100% Real", "channel": "Chan", "ext": "mp4"}
    result = run_download("https://youtu.be/abc", output_dir=str(tmp_path), quality_cap="best")
    assert fake_ydl.outtmpl == str(tmp_path / "chan" / "100-real") + ".%(ext)s"
    assert result.path == str(tmp_path / "chan" / "100-real.mp4")
    assert fake_ydl.extract_downloads == [False]


def test_default_layout_playlist(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "abc", "title": "Ep", "channel": "Guest", "ext": "mp4"}
    run_download("u", output_dir=str(tmp_path), playlist=PlaylistFolder("Mix", "Owner", "PL1"))
    assert fake_ydl.outtmpl.startswith(str(tmp_path / "owner" / "mix" / "ep"))


def test_percent_in_downloads_dir_is_escaped(tmp_path: Path, fake_ydl: Any) -> None:
    root = tmp_path / "100%"
    fake_ydl.info = {"id": "abc", "title": "t", "channel": "c", "ext": "mp4"}
    result = run_download("u", output_dir=str(root))
    assert result.path == str(root / "c" / "t.mp4")


def test_default_layout_creates_the_folder(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "abc", "title": "t", "channel": "c", "ext": "mp4"}
    run_download("u", output_dir=str(tmp_path))
    assert (tmp_path / "c").is_dir()


def test_default_layout_keeps_progress_hook(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "abc", "title": "t", "channel": "c", "ext": "mp4"}
    progress = YtdlpProgress()
    run_download("u", output_dir=str(tmp_path), progress_hook=progress)
    assert progress.filename == str(tmp_path / "c" / "t.mp4")


def test_custom_template_skips_layout(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "abc", "title": "t", "ext": "mp4"}
    run_download("u", output_dir=str(tmp_path), output_template="%(title)s.%(ext)s")
    assert fake_ydl.process_calls == 0
    assert fake_ydl.extract_downloads == [True]
