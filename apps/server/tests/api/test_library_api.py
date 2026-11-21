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


def test_file_route_resolves_relative_path_against_repo_root(
    client: TestClient, db_session_visible: Session, tmp_path: Path, monkeypatch
) -> None:
    """Older rows store ``file_path`` relative to the repo root."""
    (tmp_path / "tmp" / "downloads").mkdir(parents=True)
    (tmp_path / "tmp" / "downloads" / "rel.mp4").write_bytes(b"rel")
    monkeypatch.setattr("app.config.REPO_ROOT", tmp_path)
    job = _add(db_session_visible, file_path="tmp/downloads/rel.mp4")
    r = client.get(f"/api/downloads/{job}/file")
    assert r.status_code == 200
    assert r.content == b"rel"


def test_file_inline_and_attachment(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    r = client.get(f"/api/downloads/{job}/file?inline=1")
    assert r.headers["content-disposition"].startswith("inline;")
    r = client.get(f"/api/downloads/{job}/file")
    assert r.headers["content-disposition"].startswith("attachment;")


def test_file_supports_range(
    client: TestClient, db_session_visible: Session, tmp_path: Path
) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    r = client.get(f"/api/downloads/{job}/file?inline=1", headers={"Range": "bytes=0-1"})
    assert r.status_code == 206 and r.content == b"da"


def test_get_job(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "queued")
    r = client.get(f"/api/downloads/{job}")
    assert r.status_code == 200 and r.json()["id"] == job
    full = _add(
        db_session_visible,
        vcodec="avc1",
        acodec="opus",
        dynamic_range="SDR",
        warning_message="w",
        playlist_title="PL",
        playlist_channel="Ch",
    )
    body = client.get(f"/api/downloads/{full}").json()
    assert (body["vcodec"], body["acodec"], body["dynamic_range"], body["warning_message"]) == (
        "avc1",
        "opus",
        "SDR",
        "w",
    )
    assert (body["playlist_title"], body["playlist_channel"]) == ("PL", "Ch")
    r = client.get("/api/downloads/999999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_bulk_delete(client: TestClient, db_session_visible: Session, tmp_path: Path) -> None:
    f = tmp_path / "v.mp4"
    f.write_bytes(b"data")
    job = _add(db_session_visible, file_path=str(f))
    res = client.post("/api/library/delete", json={"ids": [job, 999999]})
    assert res.status_code == 200
    assert res.json() == {"deleted": [job], "failed": [{"id": 999999, "reason": "not_found"}]}
    assert not f.exists()


def test_bulk_delete_validates(client: TestClient) -> None:
    for ids in ([], list(range(1, 502))):
        res = client.post("/api/library/delete", json={"ids": ids})
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "invalid_request"
