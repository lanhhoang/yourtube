"""FastAPI application entry point.

The lifespan ensures the database directory exists and runs Alembic
migrations to head before the app starts serving requests. ``/health``
verifies database reachability with ``SELECT 1`` and returns 503 if the
database is unavailable, so liveness/readiness probes can detect outages.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from alembic import command
from app.config import settings
from app.db import engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"

logger = logging.getLogger("yourtube")


def _ensure_data_dir() -> None:
    """Create the on-disk data and downloads directories if they do not exist."""
    for directory in (settings.data_dir, settings.downloads_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)


def _run_migrations() -> None:
    """Run ``alembic upgrade head`` against the configured database."""
    alembic_cfg = AlembicConfig(str(ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: prepare the filesystem and migrate before serving."""
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    _ensure_data_dir()
    _run_migrations()
    logger.info("startup complete: migrations applied to %s", settings.database_url)
    yield
    engine.dispose()
    logger.info("shutdown complete")


app = FastAPI(title="YourTube", lifespan=lifespan)


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
