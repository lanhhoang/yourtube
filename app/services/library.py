"""Library service: list, search, and delete completed downloads."""

from __future__ import annotations

import os

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Download


def get_library(session: Session) -> list[Download]:
    """Return all ``done`` rows ordered by ``finished_at`` descending."""
    stmt = (
        select(Download)
        .where(Download.status == "done")
        .order_by(Download.finished_at.desc().nulls_last())
    )
    return list(session.execute(stmt).scalars())


def search_library(session: Session, query: str) -> list[Download]:
    """Search ``done`` rows by ``title`` or ``uploader`` (LIKE match)."""
    pattern = f"%{query}%"
    stmt = (
        select(Download)
        .where(
            Download.status == "done",
            or_(
                Download.title.ilike(pattern),
                Download.uploader.ilike(pattern),
            ),
        )
        .order_by(Download.finished_at.desc().nulls_last())
    )
    return list(session.execute(stmt).scalars())


def delete_from_library(session: Session, job_id: int) -> tuple[bool, str]:
    """Delete a completed download.

    Returns ``(True, "")`` on success (row deleted, file removed).
    Returns ``(False, "not_found")`` if the id does not exist.
    Returns ``(False, "not_done")`` if the job is not in ``done`` state.
    Missing files on disk are tolerated: returns ``(True, "file_missing")``.
    Other file deletion failures return ``(False, "delete_failed")`` and
    leave the database row intact.
    """
    row = session.get(Download, job_id)
    if row is None:
        return False, "not_found"
    if row.status != "done":
        return False, "not_done"

    file_missing = False
    if row.file_path:
        try:
            os.remove(row.file_path)
        except FileNotFoundError:
            file_missing = True
        except OSError:
            return False, "delete_failed"

    session.delete(row)
    session.commit()
    return True, "file_missing" if file_missing else ""
