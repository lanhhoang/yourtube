"""``run_download`` subtitle picks and the subtitle-failure retry."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yt_dlp
from yt_dlp.utils import DownloadError

from app.services.downloader import SUBTITLE_WARNING, run_download

SUB_429 = (
    "ERROR: Unable to download video subtitles for 'fr-orig': HTTP Error 429: Too Many Requests"
)


@pytest.fixture()
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(info={}, calls=[], extract_downloads=[], raise_first=None)

    def extract_info(self, url, download=True, **_kwargs):
        state.extract_downloads.append(download)
        return dict(state.info)

    def process_ie_result(self, info, download=True, **_kwargs):
        state.calls.append(
            {
                "subtitleslangs": self.params.get("subtitleslangs"),
                "writesubtitles": self.params.get("writesubtitles"),
            }
        )
        if state.raise_first is not None:
            exc, state.raise_first = state.raise_first, None
            raise exc
        path = self.prepare_filename(info)
        for hook in self.params["progress_hooks"]:
            hook({"status": "finished", "filename": path})
        return info

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    monkeypatch.setattr(yt_dlp.YoutubeDL, "process_ie_result", process_ie_result)
    return state


def _french(**extra: Any) -> dict:
    return {"id": "a", "title": "t", "channel": "c", "ext": "mp4", "language": "fr", **extra}


def test_subtitle_langs_set_from_resolved_info(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}], "en": [{}]})
    run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls == [{"subtitleslangs": ["fr-orig"], "writesubtitles": True}]


def test_no_eligible_subtitles_turns_subs_off(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4"}
    fake_ydl.info["automatic_captions"] = {"en": [{}]}
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert fake_ydl.calls[0]["writesubtitles"] is False
    assert result.warning is None


def test_subtitle_failure_retries_without_subs(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}]})
    fake_ydl.raise_first = DownloadError(SUB_429)
    result = run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert [c["writesubtitles"] for c in fake_ydl.calls] == [True, False]
    assert result.warning == SUBTITLE_WARNING == "Subtitles couldn't be downloaded."
    assert result.path.endswith("t.mp4")


def test_media_error_is_not_retried(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = {"id": "a", "title": "t", "channel": "c", "ext": "mp4"}
    fake_ydl.raise_first = DownloadError("ERROR: HTTP Error 403: Forbidden")
    with pytest.raises(DownloadError):
        run_download("u", output_dir=str(tmp_path), subtitles=True)
    assert len(fake_ydl.calls) == 1


def test_custom_template_also_resolves_first(tmp_path: Path, fake_ydl: Any) -> None:
    fake_ydl.info = _french(automatic_captions={"fr-orig": [{}]})
    template = "%(title)s.%(ext)s"
    run_download("u", output_dir=str(tmp_path), output_template=template, subtitles=True)
    assert fake_ydl.extract_downloads == [False]
    assert fake_ydl.calls[0]["subtitleslangs"] == ["fr-orig"]
