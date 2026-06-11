"""Unit tests for ``app.services.queue`` enqueue and claim semantics.

Phase 5 tightens the claim contract: ``claim_next`` must return a
detached-safe :class:`ClaimedDownload` dataclass so the worker loop can
hold the result across session boundaries without tripping the
"session is closed" error path. The earlier queue semantics still
matter, so this file keeps the pre-existing coverage as well.
"""

from __future__ import annotations

import threading

from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import ClaimedDownload, claim_next, enqueue_download, release_job


def _make_payload(url: str = "https://example.com/v1") -> DownloadCreate:
    return DownloadCreate(url=url, title="Sample")


def test_enqueue_creates_queued_row(db_session: Session) -> None:
    """``enqueue_download`` creates a row with status ``queued`` and a new id."""
    row = enqueue_download(db_session, _make_payload())
    assert row.id is not None
    assert row.id > 0
    assert row.status == "queued"
    assert row.url == "https://example.com/v1"
    assert row.title == "Sample"


def test_claim_next_returns_detached_safe_payload(db_session: Session) -> None:
    """``claim_next`` returns a detached-safe dataclass that survives the session."""
    created = enqueue_download(db_session, DownloadCreate(url="https://example.com/watch?v=1"))

    claimed = claim_next(db_session)

    assert claimed is not None
    assert isinstance(claimed, ClaimedDownload)
    assert claimed.id == created.id
    assert claimed.status == "active"
    assert claimed.url == "https://example.com/watch?v=1"


def test_claim_next_returns_oldest_queued_row(db_session: Session) -> None:
    """``claim_next`` returns the oldest queued row and marks it active."""
    first = enqueue_download(db_session, _make_payload("https://example.com/first"))
    enqueue_download(db_session, _make_payload("https://example.com/second"))

    claimed = claim_next(db_session)

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "active"
    refreshed = db_session.get(Download, first.id)
    assert refreshed is not None
    assert refreshed.status == "active"
    assert refreshed.claimed_at is not None


def test_claim_next_skips_non_queued_rows(db_session: Session) -> None:
    """``claim_next`` skips rows that are not in ``queued`` state."""
    enqueue_download(db_session, _make_payload("https://example.com/done"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.url == "https://example.com/done")
        .values(status="done")
    )
    enqueue_download(db_session, _make_payload("https://example.com/error"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.url == "https://example.com/error")
        .values(status="error")
    )
    enqueue_download(db_session, _make_payload("https://example.com/cancelled"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.url == "https://example.com/cancelled")
        .values(status="cancelled")
    )
    enqueue_download(db_session, _make_payload("https://example.com/active"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.url == "https://example.com/active")
        .values(status="active")
    )

    queued = enqueue_download(db_session, _make_payload("https://example.com/winner"))
    claimed = claim_next(db_session)

    assert claimed is not None
    assert claimed.id == queued.id


def test_claim_next_is_idempotent_within_same_session(db_session: Session) -> None:
    """Calling ``claim_next`` twice claims one row, then returns ``None``."""
    enqueued = enqueue_download(db_session, _make_payload("https://example.com/only"))

    first = claim_next(db_session)
    second = claim_next(db_session)

    assert first is not None
    assert first.id == enqueued.id
    assert first.status == "active"
    assert second is None


def test_release_job_only_updates_active_rows(db_session: Session) -> None:
    """``release_job`` only transitions rows that are currently active."""
    row = enqueue_download(db_session, _make_payload("https://example.com/release"))
    updated = release_job(
        db_session,
        row.id,
        status="done",
        file_path="/tmp/video.mp4",
        file_size=10,
    )
    assert updated is False
    db_session.refresh(row)
    assert row.status == "queued"
    assert row.file_path is None


def test_two_sessions_claim_next_do_not_double_claim(db_engine: Engine) -> None:
    """Two concurrent sessions must not both claim the same queued row."""
    with db_engine.begin() as connection:
        connection.execute(delete(Download))

    session_local = sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    seed_session = session_local()
    try:
        seeded = enqueue_download(seed_session, _make_payload("https://example.com/concurrent"))
    finally:
        seed_session.close()

    barrier = threading.Barrier(2)
    results: list[ClaimedDownload | None] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        session = session_local()
        try:
            barrier.wait(timeout=2)
            claimed = claim_next(session)
            with lock:
                results.append(claimed)
        except BaseException as exc:  # noqa: BLE001 - fail test with captured error
            with lock:
                errors.append(exc)
        finally:
            session.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert errors == []
    claimed = [row for row in results if row is not None]
    assert len(claimed) == 1
    assert claimed[0].id == seeded.id

    with db_engine.begin() as connection:
        connection.execute(delete(Download))
