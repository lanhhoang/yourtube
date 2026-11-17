"""Queue endpoints: list, cancel, retry, dismiss."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import resolve_repo_path
from app.db import get_session
from app.models import Download
from app.schemas import JobOut, QueueOut
from app.services.queue import (
    cancel_job,
    dismiss_job,
    get_active_jobs,
    get_failed_jobs,
    get_recent_completed_jobs,
    retry_job,
)

router = APIRouter(tags=["jobs"])


@router.get("/queue")
def get_queue(session: Session = Depends(get_session)) -> QueueOut:
    return QueueOut(
        active=[JobOut.from_row(r) for r in get_active_jobs(session)],
        failed=[JobOut.from_row(r) for r in get_failed_jobs(session)],
        completed=[JobOut.from_row(r) for r in get_recent_completed_jobs(session, limit=20)],
    )


@router.post("/downloads/{job_id}/cancel", status_code=204, response_class=Response)
def cancel(job_id: int, session: Session = Depends(get_session)) -> Response:
    if not cancel_job(session, job_id):
        raise ApiError(409, "not_cancellable", "This download can't be cancelled.")
    return Response(status_code=204)


def _not_failed(session: Session, job_id: int, verb: str) -> ApiError:
    if session.get(Download, job_id) is None:
        return ApiError(404, "not_found", "Download not found.")
    return ApiError(409, "not_failed", f"Only failed downloads can be {verb}.")


@router.post("/downloads/{job_id}/retry")
def retry(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    if not retry_job(session, job_id):
        raise _not_failed(session, job_id, "retried")
    row = session.get(Download, job_id, populate_existing=True)
    assert row is not None
    return JobOut.from_row(row)


@router.post("/downloads/{job_id}/dismiss", status_code=204, response_class=Response)
def dismiss(job_id: int, session: Session = Depends(get_session)) -> Response:
    if not dismiss_job(session, job_id):
        raise _not_failed(session, job_id, "dismissed")
    return Response(status_code=204)


@router.get("/downloads/{job_id}/file")
def download_file(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = session.get(Download, job_id)
    if row is None:
        raise ApiError(404, "not_found", "Download not found.")
    if row.status != "done" or not row.file_path:
        raise ApiError(409, "not_ready", "Download is not ready.")
    path = resolve_repo_path(row.file_path)
    if not path.exists():
        raise ApiError(404, "file_missing", "File is missing.")
    return FileResponse(path, filename=path.name)
