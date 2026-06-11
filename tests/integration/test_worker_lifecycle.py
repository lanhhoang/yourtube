"""Integration test for the worker lifecycle: enqueue -> claim -> release/cancel/stale.

This walks through the full queue state machine without spawning real
worker threads. It verifies the cross-service contract between
``app.services.queue`` and ``app.services.library``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import (
    cancel_job,
    claim_next,
    detect_stale_jobs,
    enqueue_download,
    release_job,
    requeue_active_on_startup,
)


def _make(url: str) -> DownloadCreate:
    return DownloadCreate(url=url, title="t")


def test_enqueue_claim_release_to_done(db_session: Session) -> None:
    """Happy path: enqueue -> claim -> release as done populates file metadata."""
    enqueued = enqueue_download(db_session, _make("https://example.com/happy"))
    claimed = claim_next(db_session)
    assert claimed is not None
    assert claimed.id == enqueued.id
    assert claimed.status == "active"

    db_session.refresh(enqueued)
    assert enqueued.status == "active"
    assert enqueued.claimed_at is not None

    updated = release_job(
        db_session,
        claimed.id,
        status="done",
        file_path="/tmp/video.mp4",
        file_size=1024,
        media_format="mp4",
        resolution_height=1080,
    )
    assert updated is True
    db_session.refresh(enqueued)
    assert enqueued.status == "done"
    assert enqueued.file_path == "/tmp/video.mp4"
    assert enqueued.file_size == 1024
    assert enqueued.media_format == "mp4"
    assert enqueued.resolution_height == 1080
    assert enqueued.finished_at is not None


def test_cancel_queued_row_immediately(db_session: Session) -> None:
    """Cancelling a queued row transitions it to ``cancelled`` without claiming."""
    enqueued = enqueue_download(db_session, _make("https://example.com/cancel"))
    assert cancel_job(db_session, enqueued.id) is True
    db_session.refresh(enqueued)
    assert enqueued.status == "cancelled"


def test_stale_detection_marks_old_active_row_as_error(db_session: Session) -> None:
    """A row claimed long ago is marked ``error`` with code ``stale_worker``."""
    enqueued = enqueue_download(db_session, _make("https://example.com/stale"))
    claimed = claim_next(db_session)
    assert claimed is not None
    assert claimed.id == enqueued.id
    far_past = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.execute(
        Download.__table__.update().where(Download.id == claimed.id).values(claimed_at=far_past)
    )

    affected = detect_stale_jobs(db_session, timeout_minutes=10)
    assert affected == 1
    db_session.refresh(enqueued)
    assert enqueued.status == "error"
    assert enqueued.error_code == "stale_worker"


def test_startup_requeue_moves_active_back_to_queued(db_session: Session) -> None:
    """``requeue_active_on_startup`` resets a stranded active row."""
    enqueued = enqueue_download(db_session, _make("https://example.com/stranded"))
    claim_next(db_session)
    affected = requeue_active_on_startup(db_session)
    assert affected == 1
    db_session.refresh(enqueued)
    assert enqueued.status == "queued"
    assert enqueued.claimed_at is None
