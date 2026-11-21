"""Queue endpoints: list, cancel, retry, dismiss."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import resolve_repo_path
from app.db import get_session
from app.models import Download
from app.schemas import (
    BatchOut,
    DismissFailedOut,
    EnqueueRequest,
    EnqueueResult,
    JobOut,
    QueueOut,
    SubtitleTrackOut,
)
from app.services.push import notify_settled
from app.services.queue import (
    cancel_job,
    dismiss_failed,
    dismiss_job,
    enqueue_downloads,
    get_active_jobs,
    get_failed_jobs,
    get_recent_completed_jobs,
    recent_batch_summaries,
    retry_job,
)
from app.services.subtitles import read_vtt, subtitle_sidecars

router = APIRouter(tags=["jobs"])


@router.get("/queue")
def get_queue(session: Session = Depends(get_session)) -> QueueOut:
    return QueueOut(
        active=[JobOut.from_row(r) for r in get_active_jobs(session)],
        failed=[JobOut.from_row(r) for r in get_failed_jobs(session)],
        completed=[JobOut.from_row(r) for r in get_recent_completed_jobs(session, limit=20)],
        batches=[BatchOut(**asdict(b)) for b in recent_batch_summaries(session)],
    )


@router.post("/queue/dismiss-failed")
def dismiss_all_failed(session: Session = Depends(get_session)) -> DismissFailedOut:
    return DismissFailedOut(dismissed=dismiss_failed(session))


@router.post("/downloads", status_code=201)
def enqueue(body: EnqueueRequest, session: Session = Depends(get_session)) -> EnqueueResult:
    rows = enqueue_downloads(session, list(body.jobs))
    return EnqueueResult(created=[JobOut.from_row(r) for r in rows])


@router.post("/downloads/{job_id}/cancel", status_code=204, response_class=Response)
def cancel(
    job_id: int, background: BackgroundTasks, session: Session = Depends(get_session)
) -> Response:
    if not cancel_job(session, job_id):
        raise ApiError(409, "not_cancellable", "This download can't be cancelled.")
    session.expire_all()
    row = session.get(Download, job_id)
    if row is not None and row.status == "cancelled":
        background.add_task(notify_settled, job_id)
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


@router.get("/downloads/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobOut:
    row = session.get(Download, job_id)
    if row is None:
        raise ApiError(404, "not_found", "Download not found.")
    return JobOut.from_row(row)


@router.get("/downloads/{job_id}/file")
def download_file(
    job_id: int, inline: bool = False, session: Session = Depends(get_session)
) -> FileResponse:
    row = session.get(Download, job_id)
    if row is None:
        raise ApiError(404, "not_found", "Download not found.")
    if row.status != "done" or not row.file_path:
        raise ApiError(409, "not_ready", "Download is not ready.")
    path = resolve_repo_path(row.file_path)
    if not path.exists():
        raise ApiError(404, "file_missing", "File is missing.")
    return FileResponse(
        path,
        filename=path.name,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/downloads/{job_id}/subtitles")
def list_subtitles(job_id: int, session: Session = Depends(get_session)) -> list[SubtitleTrackOut]:
    row = session.get(Download, job_id)
    if row is None:
        raise ApiError(404, "not_found", "Download not found.")
    if row.status != "done" or not row.file_path or JobOut.from_row(row).media_kind == "audio":
        return []
    langs = subtitle_sidecars(resolve_repo_path(row.file_path))
    ordered = sorted(langs, key=lambda lang: (not lang.endswith("-orig"), lang))
    return [
        SubtitleTrackOut(lang=lang, url=f"/api/downloads/{job_id}/subtitles/{lang}.vtt")
        for lang in ordered
    ]


@router.get("/downloads/{job_id}/subtitles/{lang}.vtt")
def get_subtitle(
    job_id: int, lang: str, session: Session = Depends(get_session)
) -> PlainTextResponse:
    row = session.get(Download, job_id)
    if row is None or row.status != "done" or not row.file_path:
        raise ApiError(404, "not_found", "Subtitle not found.")
    path = subtitle_sidecars(resolve_repo_path(row.file_path)).get(lang)
    if path is None:
        raise ApiError(404, "not_found", "Subtitle not found.")
    return PlainTextResponse(read_vtt(path), media_type="text/vtt; charset=utf-8")
