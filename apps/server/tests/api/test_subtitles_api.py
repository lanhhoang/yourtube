"""API tests for subtitle listing and VTT serving."""

from __future__ import annotations

from pathlib import Path

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
