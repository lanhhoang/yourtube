"""API tests for library and file endpoints."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Download


def _add(session: Session, status: str = "done", **fields: object) -> int:
    fields.setdefault("title", "T")
    row = Download(url="https://example.com/x", status=status, **fields)
    session.add(row)
    session.commit()
    return row.id


def test_library_lists_done_only_newest_first(
    client: TestClient, db_session_visible: Session
) -> None:
    old = _add(db_session_visible, finished_at=datetime(2026, 1, 1))
    new = _add(db_session_visible, finished_at=datetime(2026, 1, 2))
    _add(db_session_visible, "queued")
    assert [j["id"] for j in client.get("/api/library").json()] == [new, old]


def test_library_search_matches_title_or_uploader(
    client: TestClient, db_session_visible: Session
) -> None:
    a = _add(db_session_visible, title="Cats", uploader="Anath", finished_at=datetime(2026, 1, 1))
    b = _add(db_session_visible, title="Banana bread", finished_at=datetime(2026, 1, 2))
    c = _add(db_session_visible, title="Dogs", uploader="Bob", finished_at=datetime(2026, 1, 3))
    ids = lambda q: sorted(j["id"] for j in client.get("/api/library", params={"q": q}).json())  # noqa: E731
    assert ids("Ana") == sorted([a, b])
    assert ids("dogs") == [c]
    assert ids("  ") == sorted([a, b, c])


def test_library_delete_removes_row_and_file(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    assert client.delete(f"/api/library/{job}").status_code == 204
    assert not f.exists()
    db_session_visible.expire_all()
    assert db_session_visible.get(Download, job) is None


def test_library_delete_missing_file_is_204(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    job = _add(db_session_visible, file_path=str(tmp_path / "gone.mp4"))
    assert client.delete(f"/api/library/{job}").status_code == 204


def test_library_delete_active_conflicts(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "active")
    r = client.delete(f"/api/library/{job}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_done"


def test_library_delete_missing_404(client: TestClient) -> None:
    r = client.delete("/api/library/999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_file_route_streams_done_file(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    r = client.get(f"/api/downloads/{job}/file")
    assert r.status_code == 200
    assert r.content == b"data"
    assert "v.mp4" in r.headers["content-disposition"]


def test_file_route_not_found_404(client: TestClient) -> None:
    r = client.get("/api/downloads/999999/file")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_file_route_not_ready_409(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "active")
    r = client.get(f"/api/downloads/{job}/file")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_ready"


def test_file_route_missing_file_404(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    job = _add(db_session_visible, file_path=str(tmp_path / "gone.mp4"))
    r = client.get(f"/api/downloads/{job}/file")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "file_missing"
