"""FastAPI application entry point.

The lifespan ensures the database directory exists, runs Alembic
migrations to head, recovers any stranded ``active`` rows, and starts
the worker pool. ``/health`` verifies database reachability with
``SELECT 1`` and returns 503 if the database is unavailable, so
liveness/readiness probes can detect outages.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from starlette.staticfiles import StaticFiles

from alembic import command
from app.config import settings
from app.db import SessionLocal, engine
from app.models import Download
from app.routes.pages import router as pages_router
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.queue import (
    ClaimedDownload,
    claim_next,
    detect_stale_jobs,
    is_cancel_requested,
    release_job,
    requeue_active_on_startup,
    update_progress,
)
from app.services.settings import resolve_runtime_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"

logger = logging.getLogger("yourtube")

STALE_CHECK_INTERVAL_SECONDS = 60.0
STALE_TIMEOUT_MINUTES = 10


def _ensure_data_dir() -> None:
    """Create the on-disk data and downloads directories if they do not exist."""
    for directory in (settings.data_dir, settings.downloads_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)


def _run_migrations() -> None:
    """Run ``alembic upgrade head`` against the configured database."""
    if os.environ.get("YT_SKIP_MIGRATIONS") == "1":
        return
    alembic_cfg = AlembicConfig(str(ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


def _persist_progress(job_id: int, percent: float) -> None:
    """Write a progress update from the worker thread.

    Uses its own short-lived session so the worker does not have to share
    state with the request that triggered the work.
    """
    with SessionLocal() as session:
        update_progress(session, job_id, percent)


def _cancel_requested(job_id: int) -> bool:
    """Read the cancellation flag for a job from the worker thread."""
    with SessionLocal() as session:
        return is_cancel_requested(session, job_id)


class WorkerPool:
    """Thread pool that consumes the ``downloads`` queue.

    The pool is a thin orchestration layer: each worker loop calls
    :func:`claim_next` to atomically claim the oldest queued row, then
    hands the job off to :meth:`_run_job` which drives the download
    through the existing services. State transitions, progress writes,
    and error mapping all happen through the existing service layer. A
    separate daemon thread periodically calls :func:`detect_stale_jobs`
    to reap rows left ``active`` by a crashed or hung worker.
    """

    def __init__(
        self,
        stale_check_interval_seconds: float = STALE_CHECK_INTERVAL_SECONDS,
        stale_timeout_minutes: int = STALE_TIMEOUT_MINUTES,
    ) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._stale_check_interval_seconds = stale_check_interval_seconds
        self._stale_timeout_minutes = stale_timeout_minutes

    def start(self, concurrency: int) -> None:
        """Spawn ``concurrency`` daemon worker threads plus the stale-check thread."""
        for index in range(max(1, concurrency)):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"worker-{index}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        stale_thread = threading.Thread(
            target=self._stale_check_loop,
            name="stale-check",
            daemon=True,
        )
        stale_thread.start()
        self._threads.append(stale_thread)

    def stop(self) -> None:
        """Signal workers to stop and join them."""
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()

    def _worker_loop(self) -> None:
        """Worker loop: claim a job, run it, repeat until stopped."""
        while not self._stop_event.is_set():
            claimed = self._claim_once_for_test()
            if claimed is None:
                self._stop_event.wait(1.0)
                continue
            self._run_job(claimed.id)

    def _stale_check_loop(self) -> None:
        """Periodically reap jobs left ``active`` by a crashed or hung worker."""
        while not self._stop_event.wait(self._stale_check_interval_seconds):
            with SessionLocal() as session:
                detect_stale_jobs(session, timeout_minutes=self._stale_timeout_minutes)

    def _claim_once_for_test(self) -> ClaimedDownload | None:
        """Claim the next queued job from a short-lived session.

        Exposed for tests and reused by :meth:`_worker_loop`. The session
        is closed before the caller uses the returned payload, so the
        payload must be detached-safe (``ClaimedDownload`` is).
        """
        with SessionLocal() as session:
            return claim_next(session)

    def _run_job(self, job_id: int) -> None:
        """Run a single claimed job to completion.

        Pulls the job row and runtime settings in one session, executes
        ``run_download`` (which may raise :class:`DownloadCancelled`),
        and writes the terminal state through :func:`release_job`.
        """
        with SessionLocal() as session:
            runtime = resolve_runtime_settings(session)
            Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
            job = session.get(Download, job_id)
            if job is None:
                return
            job_id_local = job.id
            job_url = job.url
            job_video_format_id = job.video_format_id
            job_audio_format_id = job.audio_format_id
            job_output_template = job.output_template
            job_audio_bitrate = job.audio_bitrate
            job_subtitles = job.subtitles

        progress = YtdlpProgress(
            cancel_requested=lambda: _cancel_requested(job_id_local),
            on_progress=lambda percent: _persist_progress(job_id_local, percent),
        )
        try:
            output_path = run_download(
                url=job_url,
                video_format_id=job_video_format_id,
                audio_format_id=job_audio_format_id,
                output_template=job_output_template,
                output_dir=str(runtime.downloads_dir),
                audio_bitrate=job_audio_bitrate,
                proxy=runtime.proxy_url,
                cookies_file=str(runtime.cookies_path) if runtime.cookies_path else None,
                subtitles=job_subtitles,
                progress_hook=progress,
            )
        except DownloadCancelled:
            with SessionLocal() as session:
                release_job(session, job_id_local, status="cancelled")
            return
        except Exception as exc:  # noqa: BLE001 - surface as user-facing error
            code, message = friendly_ytdlp_error(str(exc))
            with SessionLocal() as session:
                release_job(
                    session,
                    job_id_local,
                    status="error",
                    error_code=code,
                    error_message=message,
                )
            return
        with SessionLocal() as session:
            release_job(session, job_id_local, status="done", file_path=output_path or None)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: prepare the filesystem, migrate, recover, serve."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    _ensure_data_dir()
    _run_migrations()
    with SessionLocal() as session:
        requeue_active_on_startup(session)
        runtime = resolve_runtime_settings(session)
    Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
    worker_pool = WorkerPool()
    if settings.workers_enabled:
        worker_pool.start(runtime.max_concurrent)
        logger.info(
            "startup complete: %d worker(s) ready, downloads dir=%s",
            runtime.max_concurrent,
            runtime.downloads_dir,
        )
    else:
        logger.info(
            "startup complete: workers disabled, downloads dir=%s",
            runtime.downloads_dir,
        )
    _app.state.worker_pool = worker_pool
    yield
    worker_pool.stop()
    engine.dispose()
    logger.info("shutdown complete")


app = FastAPI(title="YourTube", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
app.include_router(pages_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe.

    Returns ``{"status": "ok"}`` when the database responds to ``SELECT 1``.
    Returns HTTP 503 with a structured error body when the database is
    unreachable, so reverse proxies and orchestrators can take action.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        logger.exception("health check failed: database unreachable")
        raise HTTPException(
            status_code=503,
            detail={"code": "db_unreachable", "message": str(exc)},
        ) from exc
    return {"status": "ok"}
