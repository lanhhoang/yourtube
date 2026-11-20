"""Unit tests for the ffprobe media probe and library backfill."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

from app.models import Download
from app.services import media_probe
from app.services.media_probe import ProbeResult, backfill_media_info, probe_media


def _fake_ffprobe(monkeypatch: pytest.MonkeyPatch, streams: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(media_probe.shutil, "which", lambda _name: "/usr/bin/ffprobe")

    def run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"streams": streams}), "")

    monkeypatch.setattr(media_probe.subprocess, "run", run)


def test_probe_video_sdr(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_ffprobe(
        monkeypatch,
        [
            {"codec_type": "video", "codec_name": "h264", "color_transfer": "bt709"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    )
    assert probe_media(Path("x.mp4")) == ProbeResult("h264", "aac", "SDR")


def test_probe_hdr10_and_hlg(monkeypatch: pytest.MonkeyPatch) -> None:
    for transfer, expected in (("smpte2084", "HDR10"), ("arib-std-b67", "HLG")):
        _fake_ffprobe(
            monkeypatch,
            [{"codec_type": "video", "codec_name": "vp9", "color_transfer": transfer}],
        )
        result = probe_media(Path("x.mp4"))
        assert result is not None and result.dynamic_range == expected


def test_backfill_skips_attached_pic(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_ffprobe(
        monkeypatch,
        [
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
            {"codec_type": "audio", "codec_name": "opus"},
        ],
    )
    assert probe_media(Path("x.m4a")) == ProbeResult(None, "opus", None)


def test_probe_failures_return_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_probe.shutil, "which", lambda _name: "/usr/bin/ffprobe")

    def nonzero(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "bad")

    def timeout(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 30)

    def badjson(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "not json", "")

    for fn in (nonzero, timeout, badjson):
        monkeypatch.setattr(media_probe.subprocess, "run", fn)
        assert probe_media(Path("x.mp4")) is None


def test_backfill_missing_ffprobe(monkeypatch: pytest.MonkeyPatch, db_session_visible, tmp_path):
    monkeypatch.setattr(media_probe.shutil, "which", lambda _name: None)
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    row = Download(url="https://e.com/1", status="done", file_path=str(f))
    db_session_visible.add(row)
    db_session_visible.commit()

    assert backfill_media_info(db_session_visible) == 0
    db_session_visible.expire_all()
    got = db_session_visible.get(Download, row.id)
    assert got is not None
    assert (got.vcodec, got.acodec, got.dynamic_range) == (None, None, None)


def test_backfill_updates_only_unprobed_done_rows(
    monkeypatch: pytest.MonkeyPatch, db_session_visible, tmp_path
):
    _fake_ffprobe(
        monkeypatch,
        [
            {"codec_type": "video", "codec_name": "h264", "color_transfer": "bt709"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    )
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    target = Download(url="https://e.com/1", status="done", file_path=str(f))
    probed = Download(url="https://e.com/2", status="done", file_path=str(f), vcodec="av1")
    missing = Download(url="https://e.com/3", status="done", file_path=str(tmp_path / "gone.mp4"))
    errored = Download(url="https://e.com/4", status="error", file_path=str(f))
    db_session_visible.add_all([target, probed, missing, errored])
    db_session_visible.commit()

    assert backfill_media_info(db_session_visible) == 1
    db_session_visible.expire_all()

    def state(r: Download) -> tuple[str | None, str | None, str | None]:
        got = db_session_visible.get(Download, r.id)
        assert got is not None
        return (got.vcodec, got.acodec, got.dynamic_range)

    assert state(target) == ("h264", "aac", "SDR")
    assert state(probed) == ("av1", None, None)
    assert state(missing) == (None, None, None)
    assert state(errored) == (None, None, None)


def test_backfill_runs_off_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[int] = []
    monkeypatch.setattr(media_probe, "backfill_media_info", lambda _s: called.append(1) or 0)

    thread = media_probe.start_media_backfill()

    assert isinstance(thread, threading.Thread)
    assert thread.daemon
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert called == [1]
