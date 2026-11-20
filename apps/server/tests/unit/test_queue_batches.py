"""Unit tests for download batches and the one-summary claim."""

from __future__ import annotations

import threading

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import (
    claim_batch_summary,
    enqueue_download,
    enqueue_downloads,
    recent_batch_summaries,
    release_job,
    retry_job,
)


def _payloads(n: int, playlist_title: str | None = None) -> list[DownloadCreate]:
    return [
        DownloadCreate(url=f"https://example.com/{i}", title=f"t{i}", playlist_title=playlist_title)
        for i in range(n)
    ]


def _bid(rows: list[Download]) -> str:
    batch_id = rows[0].batch_id
    assert batch_id is not None
    return batch_id


def _settle(session: Session, rows: list[Download], statuses: list[str]) -> None:
    for row, status in zip(rows, statuses, strict=True):
        session.execute(update(Download).where(Download.id == row.id).values(status="active"))
        session.commit()
        release_job(session, row.id, status=status)


def test_batch_id_shared_for_multiple(db_session: Session) -> None:
    rows = enqueue_downloads(db_session, _payloads(3))
    assert rows[0].batch_id is not None
    assert len({r.batch_id for r in rows}) == 1


def test_single_job_has_no_batch(db_session: Session) -> None:
    row = enqueue_download(db_session, _payloads(1)[0])
    assert row.batch_id is None


def test_claim_waits_then_once(db_session_visible: Session) -> None:
    rows = enqueue_downloads(db_session_visible, _payloads(3, playlist_title="Mix"))
    batch_id = _bid(rows)
    _settle(db_session_visible, rows[:2], ["done", "done"])
    assert claim_batch_summary(db_session_visible, batch_id) is None
    _settle(db_session_visible, rows[2:], ["error"])
    summary = claim_batch_summary(db_session_visible, batch_id)
    assert summary is not None
    assert (summary.name, summary.done, summary.failed, summary.cancelled) == ("Mix", 2, 1, 0)
    assert summary.finished_at is not None
    assert claim_batch_summary(db_session_visible, batch_id) is None


def test_unnamed_batch_name(db_session_visible: Session) -> None:
    rows = enqueue_downloads(db_session_visible, _payloads(3))
    _settle(db_session_visible, rows, ["done", "done", "cancelled"])
    summary = claim_batch_summary(db_session_visible, _bid(rows))
    assert summary is not None
    assert summary.name == "3 videos"
    assert summary.cancelled == 1


def test_unnamed_single_video_batch_name(db_session_visible: Session) -> None:
    rows = enqueue_downloads(db_session_visible, _payloads(2))
    _settle(db_session_visible, rows, ["done", "done"])
    db_session_visible.execute(delete(Download).where(Download.id == rows[1].id))
    db_session_visible.commit()
    summary = claim_batch_summary(db_session_visible, _bid(rows))
    assert summary is not None
    assert summary.name == "1 video"


def test_claim_race_has_one_winner(db_session_visible: Session) -> None:
    for _ in range(50):
        rows = enqueue_downloads(db_session_visible, _payloads(2))
        batch_id = _bid(rows)
        _settle(db_session_visible, rows, ["done", "error"])
        barrier = threading.Barrier(2)
        results: list[object] = []
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                with SessionLocal() as s:
                    barrier.wait()
                    results.append(claim_batch_summary(s, batch_id))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        assert len(results) == 2
        assert len([r for r in results if r is not None]) == 1


def test_retry_leaves_batch_and_rest_claims_once(db_session_visible: Session) -> None:
    rows = enqueue_downloads(db_session_visible, _payloads(3))
    batch_id = _bid(rows)
    _settle(db_session_visible, rows, ["done", "error", "done"])
    assert retry_job(db_session_visible, rows[1].id) is True
    db_session_visible.refresh(rows[1])
    assert rows[1].batch_id is None
    assert rows[1].batch_notified is False
    summary = claim_batch_summary(db_session_visible, batch_id)
    assert summary is not None
    assert (summary.done, summary.failed) == (2, 0)
    assert claim_batch_summary(db_session_visible, batch_id) is None


def test_retry_after_summary_cannot_reclaim(db_session_visible: Session) -> None:
    rows = enqueue_downloads(db_session_visible, _payloads(2, playlist_title="Mix"))
    batch_id = _bid(rows)
    _settle(db_session_visible, rows, ["error", "done"])
    assert claim_batch_summary(db_session_visible, batch_id) is not None
    assert retry_job(db_session_visible, rows[0].id) is True
    assert claim_batch_summary(db_session_visible, batch_id) is None
    listed = recent_batch_summaries(db_session_visible)
    assert [s.batch_id for s in listed] == [batch_id]
    ids = db_session_visible.execute(
        select(Download.batch_id).where(Download.id == rows[0].id)
    ).scalar()
    assert ids is None
