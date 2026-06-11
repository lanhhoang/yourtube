"""Integration test for ``WorkerPool._run_job`` outcome mapping.

The pool never spawns threads in this test: each test calls
``WorkerPool._run_job`` directly to keep the assertion scope tight and
avoid flakiness. ``run_download`` is monkeypatched on ``app.main`` to
simulate the success, cancellation, and failure paths.
"""

from __future__ import annotations

from pathlib import Path

from app.models import Download
from app.schemas import DownloadCreate
from app.services.downloader import DownloadCancelled
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
        return str(tmp_path / "video.mp4")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session_visible.refresh(row)
    assert row.status == "done"
    assert row.progress == 55.0
    assert row.file_path == str(tmp_path / "video.mp4")


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
