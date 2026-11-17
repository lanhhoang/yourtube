"""API tests for POST /api/downloads."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_downloads

U = "https://example.com/v"


def _post(client: TestClient, jobs: list[dict]):
    return client.post("/api/downloads", json={"jobs": jobs})


def _rows(session: Session) -> int:
    session.expire_all()
    return session.scalar(select(func.count()).select_from(Download)) or 0


def test_enqueue_single_with_cap(client: TestClient, db_session_visible: Session) -> None:
    r = _post(client, [{"url": U, "title": "T", "quality_cap": "720"}])
    assert r.status_code == 201
    job = r.json()["created"][0]
    assert job["quality_cap"] == "720" and job["title"] == "T" and job["status"] == "queued"


def test_enqueue_mixed_cap_and_exact(client: TestClient, db_session_visible: Session) -> None:
    r = _post(
        client,
        [
            {"url": U, "quality_cap": "1080"},
            {"url": U + "2", "video_format_id": "137", "audio_format_id": "140"},
        ],
    )
    assert r.status_code == 201
    a, b = db_session_visible.scalars(select(Download).order_by(Download.id)).all()[-2:]
    assert (a.quality_cap, a.video_format_id) == ("1080", None)
    assert (b.quality_cap, b.video_format_id, b.audio_format_id) == (None, "137", "140")


def test_enqueue_rejects_escaping_output_template(
    client: TestClient, db_session_visible: Session
) -> None:
    before = _rows(db_session_visible)
    r = _post(client, [{"url": U, "output_template": "../x.%(ext)s"}])
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert _rows(db_session_visible) == before


def test_enqueue_rejects_absolute_output_template(
    client: TestClient, db_session_visible: Session
) -> None:
    before = _rows(db_session_visible)
    r = _post(client, [{"url": U, "output_template": "/tmp/x.%(ext)s"}])
    assert r.status_code == 422
    assert _rows(db_session_visible) == before


def test_enqueue_blank_template_ok(client: TestClient) -> None:
    assert (
        _post(client, [{"url": U, "output_template": "", "audio_bitrate": ""}]).status_code == 201
    )


def test_enqueue_rejects_bad_bitrate(client: TestClient) -> None:
    assert _post(client, [{"url": U, "audio_bitrate": "loud"}]).status_code == 422


def test_enqueue_rejects_unknown_cap(client: TestClient) -> None:
    assert _post(client, [{"url": U, "quality_cap": "999"}]).status_code == 422


def test_enqueue_rejects_empty_jobs(client: TestClient) -> None:
    assert _post(client, []).status_code == 422


def test_enqueue_one_bad_job_creates_nothing(
    client: TestClient, db_session_visible: Session
) -> None:
    before = _rows(db_session_visible)
    assert _post(client, [{"url": U}, {"url": ""}]).status_code == 422
    assert _rows(db_session_visible) == before


def test_enqueue_downloads_single_commit(db_session_visible: Session) -> None:
    rows = enqueue_downloads(
        db_session_visible, [DownloadCreate(url=U), DownloadCreate(url=U + "2", quality_cap="480")]
    )
    assert [r.quality_cap for r in rows] == [None, "480"]
    assert all(r.id for r in rows)
