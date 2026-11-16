"""Unit tests for ``app.services.queue.get_recent_completed_jobs``."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Download
from app.services.queue import get_recent_completed_jobs


def _done(session: Session, *, url: str, finished_at: datetime) -> Download:
    row = Download(url=url, status="done", progress=100.0, finished_at=finished_at)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_get_recent_completed_jobs_orders_oldest_first(db_session: Session) -> None:
    first = _done(
        db_session,
        url="https://example.com/a",
        finished_at=datetime(2026, 6, 12, 10, 0),
    )
    second = _done(
        db_session, url="https://example.com/b", finished_at=datetime(2026, 6, 12, 11, 0)
    )

    rows = get_recent_completed_jobs(db_session)

    assert [row.id for row in rows] == [first.id, second.id]


def test_get_recent_completed_jobs_respects_limit(db_session: Session) -> None:
    for index in range(5):
        _done(
            db_session,
            url=f"https://example.com/{index}",
            finished_at=datetime(2026, 6, 12, 10, index),
        )

    rows = get_recent_completed_jobs(db_session, limit=3)

    assert len(rows) == 3
    # The 3 most recent, still returned oldest-first.
    assert [row.url for row in rows] == [
        "https://example.com/2",
        "https://example.com/3",
        "https://example.com/4",
    ]


def test_get_recent_completed_jobs_ignores_non_done_rows(db_session: Session) -> None:
    queued = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session.add(queued)
    db_session.commit()

    rows = get_recent_completed_jobs(db_session)

    assert rows == []
