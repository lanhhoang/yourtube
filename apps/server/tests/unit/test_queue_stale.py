"""Unit tests for ``app.services.queue`` stale detection and startup recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import (
    detect_stale_jobs,
    enqueue_download,
    requeue_active_on_startup,
)


def _make(url: str) -> DownloadCreate:
    return DownloadCreate(url=url, title="t")


def test_detect_stale_jobs_marks_old_active_rows_as_error(db_session: Session) -> None:
    """``detect_stale_jobs`` marks active rows older than the timeout as error."""
    row = enqueue_download(db_session, _make("https://example.com/stale"))
    far_past = datetime.now(timezone.utc) - timedelta(minutes=20)
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", claimed_at=far_past)
    )
    affected = detect_stale_jobs(db_session, timeout_minutes=10)
    assert affected == 1
    db_session.refresh(row)
    assert row.status == "error"
    assert row.error_code == "stale_worker"
    assert row.finished_at is not None


def test_detect_stale_jobs_ignores_recent_active_rows(db_session: Session) -> None:
    """``detect_stale_jobs`` does not touch active rows within the timeout."""
    row = enqueue_download(db_session, _make("https://example.com/fresh"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", claimed_at=datetime.now(timezone.utc))
    )
    affected = detect_stale_jobs(db_session, timeout_minutes=10)
    assert affected == 0
    db_session.refresh(row)
    assert row.status == "active"


def test_requeue_active_on_startup_resets_claimed_at(db_session: Session) -> None:
    """``requeue_active_on_startup`` moves active rows back to queued."""
    row = enqueue_download(db_session, _make("https://example.com/active"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", claimed_at=datetime.now(timezone.utc))
    )
    affected = requeue_active_on_startup(db_session)
    assert affected == 1
    db_session.refresh(row)
    assert row.status == "queued"
    assert row.claimed_at is None


def test_requeue_active_on_startup_ignores_queued_rows(db_session: Session) -> None:
    """``requeue_active_on_startup`` only touches active rows."""
    row = enqueue_download(db_session, _make("https://example.com/queued"))
    affected = requeue_active_on_startup(db_session)
    assert affected == 0
    db_session.refresh(row)
    assert row.status == "queued"
