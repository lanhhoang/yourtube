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
