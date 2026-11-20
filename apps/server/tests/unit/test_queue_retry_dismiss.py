"""Unit tests for ``app.services.queue`` retry, dismiss and failed-job listing."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import (
    dismiss_failed,
    dismiss_job,
    enqueue_download,
    get_failed_jobs,
    retry_job,
)


def _row(session: Session, status: str, **fields: object) -> Download:
    row = enqueue_download(
        session, DownloadCreate(url="https://example.com/x", title="t", video_format_id="137")
    )
    row.status = status
    for key, value in fields.items():
        setattr(row, key, value)
    session.commit()
    return row


def test_retry_resets_failed_job(db_session: Session) -> None:
    row = _row(
        db_session,
        "error",
        progress=40.0,
        error_code="timeout",
        error_message="slow",
        cancel_requested=True,
        batch_id="b1",
        batch_notified=True,
        finished_at=datetime(2026, 1, 1),
        claimed_at=datetime(2026, 1, 1),
    )
    assert retry_job(db_session, row.id) is True
    db_session.refresh(row)
    assert (
        row.status,
        row.progress,
        row.error_code,
        row.error_message,
        row.finished_at,
        row.claimed_at,
        row.cancel_requested,
        row.video_format_id,
    ) == ("queued", 0.0, None, None, None, None, False, "137")
    assert (row.batch_id, row.batch_notified) == (None, False)


def test_retry_twice_conflicts(db_session: Session) -> None:
    row = _row(db_session, "error")
    assert retry_job(db_session, row.id) is True
    assert retry_job(db_session, row.id) is False


def test_retry_ignores_non_failed(db_session: Session) -> None:
    for status in ("queued", "active", "done", "cancelled"):
        row = _row(db_session, status)
        assert retry_job(db_session, row.id) is False
        db_session.refresh(row)
        assert row.status == status
    assert retry_job(db_session, 999_999) is False


def test_dismiss_deletes_only_failed(db_session: Session) -> None:
    failed = _row(db_session, "error")
    done = _row(db_session, "done")
    failed_id, done_id = failed.id, done.id
    assert dismiss_job(db_session, failed_id) is True
    assert dismiss_job(db_session, done_id) is False
    assert db_session.get(Download, failed_id) is None
    assert db_session.get(Download, done_id) is not None


def test_dismiss_failed_removes_only_error_rows(db_session: Session) -> None:
    errors = [_row(db_session, "error"), _row(db_session, "error")]
    keep = [_row(db_session, s) for s in ("done", "queued", "active")]
    error_ids = [r.id for r in errors]
    keep_ids = [r.id for r in keep]
    assert dismiss_failed(db_session) == 2
    assert all(db_session.get(Download, i) is None for i in error_ids)
    assert all(db_session.get(Download, i) is not None for i in keep_ids)


def test_get_failed_jobs_newest_first(db_session: Session) -> None:
    now = datetime(2026, 1, 1)
    old = _row(db_session, "error", finished_at=now)
    new = _row(db_session, "error", finished_at=now + timedelta(hours=1))
    _row(db_session, "done", finished_at=now)
    assert [r.id for r in get_failed_jobs(db_session)] == [new.id, old.id]
