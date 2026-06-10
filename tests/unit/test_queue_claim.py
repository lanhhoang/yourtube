"""Unit tests for ``app.services.queue`` enqueue and claim semantics."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import claim_next, enqueue_download


def _make_payload(url: str = "https://example.com/v1") -> DownloadCreate:
    return DownloadCreate(url=url, title="Sample")


def test_enqueue_creates_queued_row(db_session: Session) -> None:
    """``enqueue_download`` creates a row with status ``"queued"`` and a new id."""
    row = enqueue_download(db_session, _make_payload())
    assert row.id is not None
    assert row.id > 0
    assert row.status == "queued"
    assert row.url == "https://example.com/v1"
    assert row.title == "Sample"


def test_claim_next_returns_oldest_queued_row(db_session: Session) -> None:
    """``claim_next`` returns the oldest queued row and marks it active."""
    first = enqueue_download(db_session, _make_payload("https://example.com/first"))
    enqueue_download(db_session, _make_payload("https://example.com/second"))
    claimed = claim_next(db_session)
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "active"
    assert claimed.claimed_at is not None


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

    # The only queued row is "https://example.com/active"... actually it's now active.
    # Add one more queued row to claim.
    queued = enqueue_download(db_session, _make_payload("https://example.com/winner"))

    claimed = claim_next(db_session)
    assert claimed is not None
    assert claimed.id == queued.id


def test_claim_next_is_idempotent_within_same_session(db_session: Session) -> None:
    """Calling ``claim_next`` twice on the same session claims one row, then returns None.

    The conditional UPDATE inside ``claim_next`` (``WHERE status = 'queued'``)
    ensures the second call sees no queued rows. This is the same SQL-level
    safety that protects against concurrent claims in production.
    """
    enqueued = enqueue_download(db_session, _make_payload("https://example.com/only"))
    first = claim_next(db_session)
    second = claim_next(db_session)
    assert first is not None
    assert first.id == enqueued.id
    assert first.status == "active"
    assert second is None
