"""Queue service: enqueue, claim, release, cancel, stale recovery, startup requeue.

The service owns the lifecycle transitions of the ``downloads`` table.
Claims are transaction-safe: ``claim_next`` uses a conditional UPDATE with
``RETURNING`` so only one row is claimed, even under concurrency.

Phase 5 introduces :class:`ClaimedDownload`: a frozen dataclass that
carries the minimal payload needed to run a job. Returning a dataclass
instead of an ORM ``Download`` instance keeps the worker loop
detached-safe -- the worker can hold the payload outside the claiming
session without triggering SQLAlchemy "detached instance" errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate


@dataclass(frozen=True)
class ClaimedDownload:
    """Detached-safe payload returned by :func:`claim_next`.

    Carries the three fields the worker loop needs to look the job back
    up in the database (``id``) and to render initial state in logs
    (``status`` and ``url``). A frozen dataclass is cheap to copy,
    comparable, and immune to accidental mutation between threads.
    """

    id: int
    status: str
    url: str


def update_progress(session: Session, job_id: int, percent: float) -> bool:
    """Persist a new progress value for an active job.

    Returns ``True`` when the row was updated, ``False`` when the row is
    not in ``active`` state (or does not exist). The value is clamped to
    ``[0.0, 100.0]`` so a misbehaving progress source cannot poison the
    progress column.
    """
    clamped = max(0.0, min(100.0, float(percent)))
    stmt = (
        update(Download)
        .where(Download.id == job_id, Download.status == "active")
        .values(progress=clamped)
    )
    result = session.execute(stmt)
    session.commit()
    return bool(result.rowcount)


def is_cancel_requested(session: Session, job_id: int) -> bool:
    """Return the current ``cancel_requested`` flag for ``job_id``.

    Reads the flag directly from the database so the worker callback can
    poll from a fresh session on every progress tick.
    """
    stmt = select(Download.cancel_requested).where(Download.id == job_id)
    return bool(session.execute(stmt).scalar_one_or_none())


def enqueue_download(session: Session, payload: DownloadCreate) -> Download:
    """Insert a new row in ``queued`` state and return it."""
    row = Download(
        url=payload.url,
        title=payload.title,
        uploader=payload.uploader,
        duration=payload.duration,
        thumbnail=payload.thumbnail,
        video_format_id=payload.video_format_id,
        audio_format_id=payload.audio_format_id,
        output_template=payload.output_template,
        audio_bitrate=payload.audio_bitrate,
        subtitles=payload.subtitles,
        status="queued",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def claim_next(session: Session) -> ClaimedDownload | None:
    """Claim the oldest ``queued`` row and return a detached-safe payload.

    Uses a conditional UPDATE with ``RETURNING`` so the operation is
    atomic across concurrent workers. The ``RETURNING`` clause projects
    only the three fields the worker needs (``id``, ``status``, ``url``)
    and packages them in a :class:`ClaimedDownload` dataclass. This keeps
    the result free of any session-bound ORM state.

    Returns ``None`` when no queued row is available.
    """
    subq: Select = (
        select(Download.id)
        .where(Download.status == "queued")
        .order_by(Download.created_at, Download.id)
        .limit(1)
    )
    stmt = (
        update(Download)
        .where(Download.id == subq.scalar_subquery(), Download.status == "queued")
        .values(status="active", claimed_at=func.current_timestamp())
        .returning(Download.id, Download.status, Download.url)
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    row = result.mappings().one_or_none()
    session.commit()
    if row is None:
        return None
    return ClaimedDownload(
        id=int(row["id"]),
        status=str(row["status"]),
        url=str(row["url"]),
    )


def release_job(
    session: Session,
    job_id: int,
    *,
    status: str,  # "done" | "error" | "cancelled"
    error_code: str | None = None,
    error_message: str | None = None,
    file_path: str | None = None,
    file_size: int | None = None,
    media_format: str | None = None,
    resolution_height: int | None = None,
) -> bool:
    """Transition a claimed job to its terminal state.

    Sets ``finished_at`` to now. For ``status="done"``, populates file
    metadata columns. For ``"error"``, sets ``error_code`` and
    ``error_message``. Returns ``True`` if the row was updated.
    """
    values: dict = {
        "status": status,
        "finished_at": func.current_timestamp(),
    }
    if error_code is not None:
        values["error_code"] = error_code
    if error_message is not None:
        values["error_message"] = error_message
    if file_path is not None:
        values["file_path"] = file_path
    if file_size is not None:
        values["file_size"] = file_size
    if media_format is not None:
        values["media_format"] = media_format
    if resolution_height is not None:
        values["resolution_height"] = resolution_height

    stmt = (
        update(Download).where(Download.id == job_id, Download.status == "active").values(**values)
    )
    result = session.execute(stmt)
    session.commit()
    return bool(result.rowcount)


def cancel_job(session: Session, job_id: int) -> bool:
    """Request cancellation.

    - ``queued`` -> ``cancelled`` immediately (returns ``True``)
    - ``active`` -> sets ``cancel_requested = True`` (returns ``True``)
    - ``done`` / ``error`` / ``cancelled`` -> no-op (returns ``False``)

    Uses conditional UPDATE statements so the result is independent of
    the session's identity map. Returns ``False`` if the row does not
    exist or is already in a terminal state.
    """
    cancel_stmt = (
        update(Download)
        .where(Download.id == job_id, Download.status == "queued")
        .values(status="cancelled", finished_at=func.current_timestamp())
    )
    cancel_result = session.execute(cancel_stmt)
    if bool(cancel_result.rowcount):
        session.commit()
        return True
    flag_stmt = (
        update(Download)
        .where(Download.id == job_id, Download.status == "active")
        .values(cancel_requested=True)
    )
    flag_result = session.execute(flag_stmt)
    session.commit()
    return bool(flag_result.rowcount)


def get_active_jobs(session: Session) -> list[Download]:
    """Return all rows with status ``queued`` or ``active``, ordered by ``created_at``."""
    stmt = (
        select(Download)
        .where(Download.status.in_(("queued", "active")))
        .order_by(Download.created_at, Download.id)
    )
    return list(session.execute(stmt).scalars())


def detect_stale_jobs(session: Session, timeout_minutes: int = 10) -> int:
    """Mark ``active`` rows older than ``timeout_minutes`` as ``error`` with code ``stale_worker``.

    Returns the number of rows affected.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    # SQLite stores naive datetimes by default; compare against a naive cutoff.
    cutoff_naive = cutoff.replace(tzinfo=None)
    stmt = (
        update(Download)
        .where(
            Download.status == "active",
            Download.claimed_at.is_not(None),
            Download.claimed_at < cutoff_naive,
        )
        .values(
            status="error",
            error_code="stale_worker",
            error_message="Worker did not complete within the timeout.",
            finished_at=func.current_timestamp(),
        )
    )
    result = session.execute(stmt)
    session.commit()
    return int(result.rowcount or 0)


def requeue_active_on_startup(session: Session) -> int:
    """Move all ``active`` rows back to ``queued`` and clear ``claimed_at``.

    Returns the number of rows affected.
    """
    stmt = (
        update(Download).where(Download.status == "active").values(status="queued", claimed_at=None)
    )
    result = session.execute(stmt)
    session.commit()
    return int(result.rowcount or 0)


def get_latest_completion_cursor(session: Session) -> tuple[datetime | None, int]:
    """Return the newest completion cursor as ``(finished_at, id)``.

    The cursor seeds the queue page so historical completions do not
    toast on initial page load. When no completed jobs exist, return
    ``(None, 0)``.
    """
    stmt = (
        select(Download.finished_at, Download.id)
        .where(Download.status == "done", Download.finished_at.is_not(None))
        .order_by(Download.finished_at.desc(), Download.id.desc())
        .limit(1)
    )
    row = session.execute(stmt).one_or_none()
    if row is None:
        return None, 0
    return row[0], int(row[1])


def get_completed_jobs_after(
    session: Session,
    *,
    after_finished_at: datetime | None,
    after_id: int,
) -> list[Download]:
    """Return completed jobs strictly after ``(after_finished_at, after_id)``.

    Results are ordered oldest-to-newest so the browser announces
    completions in the same order they finished.
    """
    stmt = select(Download).where(Download.status == "done", Download.finished_at.is_not(None))
    if after_finished_at is not None:
        stmt = stmt.where(
            or_(
                Download.finished_at > after_finished_at,
                and_(Download.finished_at == after_finished_at, Download.id > after_id),
            )
        )
    stmt = stmt.order_by(Download.finished_at, Download.id)
    return list(session.execute(stmt).scalars())
