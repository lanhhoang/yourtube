"""Integration test for ``WorkerPool`` orchestration behavior.

The direct claimed-job execution path is unit-tested in
``tests/unit/test_job_runner.py``. This file keeps only the worker-pool
orchestration seams: delegating a claimed job to the runner, carrying
claim ids safely across a session boundary, and periodically reaping
stale active rows.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download


def test_worker_pool_delegates_claimed_job_to_job_runner(monkeypatch) -> None:
    seen: list[int] = []

    def fake_run_claimed_job(job_id: int) -> None:
        seen.append(job_id)

    monkeypatch.setattr("app.main.run_claimed_job", fake_run_claimed_job)

    from app.main import WorkerPool

    WorkerPool()._run_job(123)

    assert seen == [123]


def test_worker_loop_can_run_claimed_job_without_detached_instance(
    monkeypatch, db_session_visible
) -> None:
    """Phase 5 regression: claim result must be detached-safe across the session boundary.

    The worker uses the ``_claim_once_for_test`` helper to obtain a
    claim payload, then drives ``_run_job`` with the integer id. The
    claim must work without the worker ever touching a session-bound
    ORM ``Download`` instance.
    """
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/safe"))
    db_session_visible.commit()

    seen: list[int] = []

    def fake_run_claimed_job(job_id: int) -> None:
        seen.append(job_id)

    monkeypatch.setattr("app.main.run_claimed_job", fake_run_claimed_job)

    from app.main import WorkerPool

    pool = WorkerPool()
    claimed = pool._claim_once_for_test()
    assert claimed is not None
    assert claimed == row.id
    pool._run_job(claimed)

    assert seen == [row.id]


def test_worker_pool_reaps_stale_jobs_periodically(db_session_visible) -> None:
    """A row claimed long ago is marked ``error`` by the periodic stale check."""
    row = Download(
        url="https://example.com/stale",
        status="active",
        progress=0.0,
        claimed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    from app.main import WorkerPool

    pool = WorkerPool(stale_check_interval_seconds=0.05, stale_timeout_minutes=1)
    pool.start(1)
    try:
        for _ in range(100):
            db_session_visible.refresh(row)
            if row.status == "error":
                break
            time.sleep(0.05)
    finally:
        pool.stop()

    assert row.status == "error"
    assert row.error_code == "stale_worker"
