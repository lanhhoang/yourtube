"""Pytest fixtures and configuration for the YourTube test suite.

The test suite builds its database by running Alembic migrations against a
session-scoped temporary SQLite file. ``os.environ["YT_DATABASE_URL"]`` is
set at module import time (before any ``app`` module is loaded) so that
``app.config.settings`` and the engine built in ``app.db`` both pick up
the test database URL.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

# --- Test database URL override --------------------------------------------
# Set the env var BEFORE importing any ``app`` modules so that the
# ``settings`` singleton and the engine created at import time in
# ``app.db`` are both bound to the test database.
_TEST_DIR = Path(tempfile.mkdtemp(prefix="yourtube-test-"))
_TEST_DB_PATH = _TEST_DIR / "test.db"
os.environ["YT_DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("YT_DATA_DIR", str(_TEST_DIR))
os.environ.setdefault("YT_DOWNLOADS_DIR", str(_TEST_DIR / "downloads"))

import pytest  # noqa: E402
from sqlalchemy import Connection, inspect  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"


# --- Migration bootstrap ---------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Apply Alembic migrations to the test database once per test session."""
    alembic_cfg = AlembicConfig(str(ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture()
def db_engine() -> Engine:
    """Per-test handle to the shared migrated engine."""
    return engine


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Per-test SQLAlchemy session isolated by a rollback-only transaction."""
    connection: Connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def db_inspector(db_engine: Engine):
    """Convenience fixture exposing a SQLAlchemy ``Inspector`` for the test DB."""
    return inspect(db_engine)
