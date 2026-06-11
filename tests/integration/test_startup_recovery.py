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
