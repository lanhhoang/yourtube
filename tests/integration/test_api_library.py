"""Integration tests for ``DELETE /api/library/{job_id}``."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_delete_library_entry_removes_completed_job(db_session_visible, tmp_path: Path) -> None:
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
        response = client.delete(f"/api/library/{row.id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert not file_path.exists()


def test_delete_library_entry_rejects_non_done_job(db_session_visible) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.delete(f"/api/library/{row.id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "library_entry_not_done"


def test_delete_library_entry_returns_404_for_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/library/9999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "library_entry_not_found"
