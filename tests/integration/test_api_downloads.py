"""Integration tests for ``POST /api/downloads``, cancel, and file download."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download


def test_create_download_returns_201() -> None:
    with TestClient(app) as client:
        response = client.post("/api/downloads", json={"url": "https://example.com/video"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["url"] == "https://example.com/video"


def test_cancel_download_returns_updated_state(db_session_visible) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/cancel"))

    with TestClient(app) as client:
        response = client.post(f"/api/downloads/{row.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_download_returns_404_for_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.post("/api/downloads/9999/cancel")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "download_not_found"


def test_cancel_terminal_download_returns_409(db_session_visible) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/done"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="done")
    )
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.post(f"/api/downloads/{row.id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "download_not_cancellable"


def test_download_file_serves_completed_job(db_session_visible, tmp_path: Path) -> None:
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"data")
    row = Download(
        url="https://example.com/done",
        status="done",
        progress=100.0,
        file_path=str(file_path),
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/api/downloads/{row.id}/file")

    assert response.status_code == 200
    assert response.content == b"data"


def test_download_file_rejects_non_done_job(db_session_visible) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/api/downloads/{row.id}/file")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "download_not_ready"
