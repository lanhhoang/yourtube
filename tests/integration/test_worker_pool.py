"""Integration test for ``WorkerPool._run_job`` outcome mapping.

The pool never spawns threads in this test: each test calls
``WorkerPool._run_job`` directly to keep the assertion scope tight and
avoid flakiness. ``run_download`` is monkeypatched on ``app.main`` to
simulate the success, cancellation, and failure paths.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models import Download
from app.schemas import DownloadCreate
from app.services.downloader import DownloadCancelled, DownloadResult
from app.services.queue import enqueue_download
from app.services.settings import set_settings_batch


def test_worker_success_marks_job_done(monkeypatch, db_session_visible, tmp_path: Path) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/success"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**kwargs):
        hook = kwargs["progress_hook"]
        hook({"status": "downloading", "_percent_str": "55.0%"})
        hook({"status": "finished", "filename": str(tmp_path / "video.mp4")})
        return DownloadResult(
            path=str(tmp_path / "video.mp4"),
            file_size=2048,
            media_format="mp4",
            resolution_height=720,
        )

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "done"
    assert row.progress == 55.0
    assert row.file_path == str(tmp_path / "video.mp4")
    assert row.file_size == 2048
    assert row.media_format == "mp4"
    assert row.resolution_height == 720


def test_worker_cancelled_download_ends_cancelled(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/cancel"))
    db_session_visible.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**_kwargs):
        raise DownloadCancelled("cancelled by user")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "cancelled"


def test_worker_failure_maps_error(monkeypatch, db_session_visible, tmp_path: Path) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/fail"))
    db_session_visible.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    set_settings_batch(db_session_visible, {"downloads_dir": str(tmp_path)})
    db_session_visible.commit()

    def fake_run_download(**_kwargs):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "error"
    assert row.error_code == "http_forbidden"


def test_worker_loop_can_run_claimed_job_without_detached_instance(
    monkeypatch, db_session_visible, tmp_path: Path
) -> None:
    """Phase 5 regression: claim result must be detached-safe across the session boundary.

    The worker uses the ``_claim_once_for_test`` helper to obtain a
    claim payload, then drives ``_run_job`` with the integer id. The
    claim must work without the worker ever touching a session-bound
    ORM ``Download`` instance.
    """
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/safe"))
    db_session_visible.commit()

    def fake_run_download(**kwargs):
        return DownloadResult(
            path=str(tmp_path / "safe.mp4"),
            file_size=None,
            media_format=None,
            resolution_height=None,
        )

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    claimed = pool._claim_once_for_test()
    assert claimed is not None
    pool._run_job(claimed.id)

    db_session_visible.refresh(row)
    assert row.status == "done"


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
