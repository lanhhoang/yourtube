"""SQLAlchemy ORM models for the YourTube web app.

The models here are the *only* source of truth for database schema at the
ORM level. Schema creation and upgrades are owned by Alembic (see
``alembic/versions/``); this module must not call ``create_all()`` at runtime.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models in the project."""


class Download(Base):
    """A queued, in-flight, or completed video download job.

    Lifecycle states are ``queued``, ``active``, ``done``, ``error``, and
    ``cancelled``. The ``status`` column is indexed to support queue scans.
    """

    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    uploader: Mapped[str | None] = mapped_column(String, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)

    # Format selection
    video_format_id: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_format_id: Mapped[str | None] = mapped_column(String, nullable=True)
    output_template: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_bitrate: Mapped[str | None] = mapped_column(String, nullable=True)
    subtitles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Queue and progress
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="queued", index=True
    )
    progress: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Error reporting
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Output file metadata
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    media_format: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Setting(Base):
    """A single key/value setting persisted in the database.

    Phase 2's settings service reads and writes rows of this table; Phase 3's
    settings page uses the same table to back its form.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
