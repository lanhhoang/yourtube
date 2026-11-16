"""Unit tests for ``app.services.queue`` cancel contract."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import cancel_job, claim_next, enqueue_download


def _make(url: str) -> DownloadCreate:
    return DownloadCreate(url=url, title="t")


def test_cancel_queued_row_transitions_to_cancelled(db_session: Session) -> None:
    """Cancelling a queued row sets status to ``cancelled`` immediately."""
    row = enqueue_download(db_session, _make("https://example.com/q"))
    result = cancel_job(db_session, row.id)
    assert result is True
    db_session.refresh(row)
    assert row.status == "cancelled"


def test_cancel_active_row_sets_cancel_requested(db_session: Session) -> None:
    """Cancelling an active row sets ``cancel_requested`` but keeps status active."""
    row = enqueue_download(db_session, _make("https://example.com/a"))
    claim_next(db_session)
    db_session.refresh(row)
    assert row.status == "active"
    result = cancel_job(db_session, row.id)
    assert result is True
    db_session.refresh(row)
    assert row.status == "active"
    assert row.cancel_requested is True


def test_cancel_terminal_rows_is_noop(db_session: Session) -> None:
    """Cancelling a row in a terminal state returns ``False`` and changes nothing."""
    for status in ("done", "error", "cancelled"):
        row = enqueue_download(db_session, _make(f"https://example.com/{status}"))
        db_session.execute(
            Download.__table__.update().where(Download.id == row.id).values(status=status)
        )
        result = cancel_job(db_session, row.id)
        assert result is False, f"cancel on {status} should return False"
        db_session.refresh(row)
        assert row.status == status
