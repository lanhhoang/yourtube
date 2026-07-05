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
from app.routes.pages import router as pages_router
from app.services.job_runner import run_claimed_job
from app.services.queue import claim_next, detect_stale_jobs, requeue_active_on_startup
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
            job_id = self._claim_once_for_test()
            if job_id is None:
                self._stop_event.wait(1.0)
                continue
            self._run_job(job_id)

    def _stale_check_loop(self) -> None:
        """Periodically reap jobs left ``active`` by a crashed or hung worker."""
        while not self._stop_event.wait(self._stale_check_interval_seconds):
            try:
                with SessionLocal() as session:
                    detect_stale_jobs(session, timeout_minutes=self._stale_timeout_minutes)
            except Exception:  # noqa: BLE001 - keep the loop alive across transient errors
                logger.exception("stale job check failed")

    def _claim_once_for_test(self) -> int | None:
        """Claim the next queued job id from a short-lived session.

        Exposed for tests and reused by :meth:`_worker_loop`.
        """
        with SessionLocal() as session:
            return claim_next(session)

    def _run_job(self, job_id: int) -> None:
        """Run a single claimed job to completion."""
        run_claimed_job(job_id)


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
