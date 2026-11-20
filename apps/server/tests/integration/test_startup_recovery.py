"""Integration test for startup recovery and worker pool startup wiring.

Lifespan must move stranded ``active`` rows back to ``queued`` so the
worker can reclaim them. This test exercises the lifespan through a
FastAPI ``TestClient`` and asserts the post-startup state of the row.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download


def test_startup_requeues_active_rows(db_session_visible) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/stranded"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session_visible.commit()

    with TestClient(app):
        pass

    db_session_visible.refresh(row)
    assert row.status == "queued"


def test_startup_moves_library(db_session_visible, tmp_path) -> None:
    from app.services.settings import get_setting, set_settings_batch

    old = tmp_path / "Old Name.mp4"
    old.write_bytes(b"x")
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    row = Download(
        url="https://www.youtube.com/watch?v=vid1",
        title="Old Name",
        uploader="Chan",
        status="done",
        file_path=str(old),
    )
    db_session_visible.add(row)
    db_session_visible.commit()

    with TestClient(app):
        pass

    db_session_visible.expire_all()
    new = tmp_path / "chan" / "old-name.mp4"
    assert new.exists() and not old.exists()
    assert db_session_visible.get(Download, row.id).file_path == str(new)
    assert get_setting(db_session_visible, "library_layout") == "v2"


def test_startup_starts_media_backfill(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr("app.main.start_media_backfill", lambda: calls.append(1))

    with TestClient(app):
        pass

    assert calls == [1]


def test_startup_survives_backfill_start_failure(monkeypatch) -> None:
    def boom() -> None:
        raise RuntimeError("nope")

    monkeypatch.setattr("app.main.start_media_backfill", boom)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
