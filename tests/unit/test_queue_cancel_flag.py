"""Unit tests for ``app.services.queue.is_cancel_requested``.

The worker uses this helper on each progress callback to detect whether
the user has asked to cancel a download. It must read the current
``cancel_requested`` flag without holding the request's session.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download, is_cancel_requested


def test_is_cancel_requested_reads_current_flag(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/cancel"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    db_session.commit()

    assert is_cancel_requested(db_session, row.id) is True


def test_is_cancel_requested_false_by_default(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/normal"))
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session.commit()

    assert is_cancel_requested(db_session, row.id) is False
