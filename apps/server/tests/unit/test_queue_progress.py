"""Unit tests for ``app.services.queue.update_progress``."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download, update_progress


def test_update_progress_persists_percent_for_active_job(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/video"))
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session.commit()

    changed = update_progress(db_session, row.id, 42.5)

    assert changed is True
    db_session.refresh(row)
    assert row.progress == 42.5


def test_update_progress_ignores_non_active_job(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/queued"))

    changed = update_progress(db_session, row.id, 80.0)

    assert changed is False
    db_session.refresh(row)
    assert row.progress == 0.0


def test_update_progress_refreshes_claim_heartbeat(db_session: Session) -> None:
    """Progress keeps a long download from being reaped as a stale worker."""
    from datetime import datetime

    from app.services.queue import detect_stale_jobs

    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/long"))
    row.status = "active"
    row.claimed_at = datetime(2000, 1, 1)
    db_session.commit()

    assert update_progress(db_session, row.id, 10.0) is True
    assert detect_stale_jobs(db_session, timeout_minutes=10) == 0
    db_session.refresh(row)
    assert row.status == "active"
