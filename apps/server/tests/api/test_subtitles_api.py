"""API tests for subtitle listing and VTT serving."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Download


def _add(session: Session, status: str = "done", **fields: object) -> int:
    row = Download(url="https://example.com/x", status=status, title="T", **fields)
    session.add(row)
    session.commit()
    return row.id


def _video(session: Session, tmp_path: Path) -> int:
    (tmp_path / "a.mp4").write_text("v")
    (tmp_path / "a.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    (tmp_path / "a.fr-orig.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nSalut\n")
    return _add(session, file_path=str(tmp_path / "a.mp4"), resolution_height=1080)


def test_list_subtitles(client: TestClient, db_session_visible: Session, tmp_path: Path) -> None:
    job = _video(db_session_visible, tmp_path)
    assert client.get(f"/api/downloads/{job}/subtitles").json() == [
        {"lang": "fr-orig", "url": f"/api/downloads/{job}/subtitles/fr-orig.vtt"},
        {"lang": "en", "url": f"/api/downloads/{job}/subtitles/en.vtt"},
    ]


def test_list_subtitles_audio_is_empty(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    (tmp_path / "a.mp4").write_text("v")
    (tmp_path / "a.en.srt").write_text("x")
    job = _add(db_session_visible, file_path=str(tmp_path / "a.mp4"), resolution_height=None)
    assert client.get(f"/api/downloads/{job}/subtitles").json() == []


def test_subtitles_not_done_is_empty(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "queued")
    assert client.get(f"/api/downloads/{job}/subtitles").json() == []


def test_subtitles_missing_job_404(client: TestClient) -> None:
    assert client.get("/api/downloads/999999/subtitles").status_code == 404
    assert client.get("/api/downloads/999999/subtitles/en.vtt").status_code == 404


def test_vtt_served(client: TestClient, db_session_visible: Session, tmp_path: Path) -> None:
    job = _video(db_session_visible, tmp_path)
    r = client.get(f"/api/downloads/{job}/subtitles/en.vtt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/vtt; charset=utf-8"
    assert r.text.startswith("WEBVTT\n\n")


def test_vtt_unknown_lang_404(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    job = _video(db_session_visible, tmp_path)
    for lang in ("de.vtt", "..%2Fx.vtt", "en.srt.vtt"):
        assert client.get(f"/api/downloads/{job}/subtitles/{lang}").status_code == 404


def test_vtt_audio_404(client: TestClient, db_session_visible: Session, tmp_path: Path) -> None:
    (tmp_path / "a.mp4").write_text("v")
    (tmp_path / "a.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    job = _add(db_session_visible, file_path=str(tmp_path / "a.mp4"), resolution_height=None)
    assert client.get(f"/api/downloads/{job}/subtitles/en.vtt").status_code == 404


def test_vtt_not_done_404(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "queued")
    assert client.get(f"/api/downloads/{job}/subtitles/en.vtt").status_code == 404


def test_vtt_read_oserror_404(
    client: TestClient,
    db_session_visible: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _video(db_session_visible, tmp_path)

    def boom(path: Path) -> str:
        raise FileNotFoundError(str(path))

    monkeypatch.setattr("app.api.jobs.read_vtt", boom)
    r = client.get(f"/api/downloads/{job}/subtitles/en.vtt")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_lang_url_is_percent_encoded(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    (tmp_path / "a.mp4").write_text("v")
    (tmp_path / "a.x#y.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    job = _add(db_session_visible, file_path=str(tmp_path / "a.mp4"), resolution_height=1080)
    tracks = client.get(f"/api/downloads/{job}/subtitles").json()
    assert len(tracks) == 1
    assert tracks[0]["lang"] == "x#y"
    assert tracks[0]["url"].endswith("/subtitles/x%23y.vtt")
    assert client.get(tracks[0]["url"]).status_code == 200


def test_vtt_sidecar_passthrough(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    (tmp_path / "a.mp4").write_text("v")
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"
    (tmp_path / "a.en.vtt").write_text(vtt)
    job = _add(db_session_visible, file_path=str(tmp_path / "a.mp4"), resolution_height=1080)
    r = client.get(f"/api/downloads/{job}/subtitles/en.vtt")
    assert r.status_code == 200
    assert r.text == vtt
