"""Database engine, session factory, and FastAPI dependency.

Schema is owned by Alembic; this module only configures the engine and
session lifecycle. SQLite connection-level pragmas are applied via a
``connect`` event listener so they take effect for every new connection.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Apply SQLite pragmas to every new DBAPI connection.

    Foreign-key enforcement is off by default in SQLite; the worker relies on
    it, and Alembic's transactional DDL benefits from a sane busy timeout.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine with engine-specific configuration."""
    connect_args: dict = {}
    engine_kwargs: dict = {}
    if settings.database_url.startswith("sqlite"):
        # Allow the connection to be shared across threads so the FastAPI
        # threadpool and worker threads can use the same pool.
        connect_args["check_same_thread"] = False
        # SQLite file connections are cheap; avoid long-lived pooled
        # connections so tests and short-lived request sessions close
        # their DBAPI handles deterministically.
        engine_kwargs["poolclass"] = NullPool
    engine = create_engine(
        settings.database_url,
        future=True,
        connect_args=connect_args,
        **engine_kwargs,
    )
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped SQLAlchemy session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
