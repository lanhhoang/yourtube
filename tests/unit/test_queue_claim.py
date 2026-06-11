"""Unit tests for ``app.services.queue`` enqueue and claim semantics.

Phase 5 tightens the claim contract: ``claim_next`` must return a
detached-safe :class:`ClaimedDownload` dataclass so the worker loop can
hold the result across session boundaries without tripping the
"session is closed" error path.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas import DownloadCreate
from app.services.queue import ClaimedDownload, claim_next, enqueue_download


def test_claim_next_returns_detached_safe_payload(db_session: Session) -> None:
    """``claim_next`` returns a ``ClaimedDownload`` dataclass that survives the session."""
    created = enqueue_download(db_session, DownloadCreate(url="https://example.com/watch?v=1"))

    claimed = claim_next(db_session)

    assert claimed is not None
    assert isinstance(claimed, ClaimedDownload)
    assert claimed.id == created.id
    assert claimed.status == "active"
    assert claimed.url == "https://example.com/watch?v=1"
