"""JSON API routes for the YourTube web app.

Phase 3A contract: every UI-facing backend endpoint lives here. The
routes are thin: they translate HTTP into service calls and map the
service results into the Pydantic response models defined in
``app.schemas``. ORM rows are never returned directly.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Download
from app.schemas import (
    DownloadCreate,
    DownloadResponse,
    InfoRequest,
    InfoResponse,
    MutationOkResponse,
    SettingsResponse,
)
from app.services.downloader import extract_info, normalize_formats
from app.services.library import delete_from_library
from app.services.queue import cancel_job, enqueue_download
from app.services.settings import (
    SETTINGS_CATALOG,
    get_all_settings,
    reset_settings,
    resolve_runtime_settings,
    set_settings_batch,
)

router = APIRouter(prefix="/api")


@router.post("/info", response_model=InfoResponse)
def fetch_info(body: InfoRequest, session: Session = Depends(get_session)) -> InfoResponse:
    """Return format metadata for a YouTube URL.

    The proxy and cookies are only sent when the caller opted in via
    the request body, even if the user has saved values in settings.
    """
    runtime = resolve_runtime_settings(session)
    raw = extract_info(
        body.url,
        proxy=runtime.proxy_url if body.proxy else None,
        cookies_file=str(runtime.cookies_path) if body.cookies and runtime.cookies_path else None,
    )
    return InfoResponse(
        url=raw.get("url") or body.url,
        title=raw.get("title", ""),
        uploader=raw.get("uploader"),
        duration=raw.get("duration"),
        thumbnail=raw.get("thumbnail"),
        formats=normalize_formats(raw),
        captions=raw.get("captions") or {},
    )


@router.post("/downloads", response_model=DownloadResponse, status_code=201)
def create_download(
    body: DownloadCreate,
    session: Session = Depends(get_session),
) -> DownloadResponse:
    """Enqueue a new download job and return its initial state."""
    row = enqueue_download(session, body)
    return DownloadResponse.model_validate(row)


@router.post("/downloads/{job_id}/cancel", response_model=DownloadResponse)
def cancel_download(job_id: int, session: Session = Depends(get_session)) -> DownloadResponse:
    """Request cancellation of a queued or active job."""
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "download_not_found", "message": f"Download {job_id} not found."},
        )
    changed = cancel_job(session, job_id)
    if not changed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "download_not_cancellable",
                "message": f"Download {job_id} is already finished.",
            },
        )
    session.refresh(row)
    return DownloadResponse.model_validate(row)


@router.get("/downloads/{job_id}/file")
def download_file(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    """Stream the completed file for a ``done`` job.

    Returns 404 when the row is missing, 409 when the job is not yet
    ready, and 404 when the on-disk file has been moved or deleted.
    """
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "download_not_found", "message": f"Download {job_id} not found."},
        )
    if row.status != "done" or not row.file_path:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "download_not_ready",
                "message": f"Download {job_id} is not ready.",
            },
        )
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "download_file_missing",
                "message": f"File for download {job_id} is missing.",
            },
        )
    return FileResponse(path)


@router.get("/settings", response_model=SettingsResponse)
def read_settings(session: Session = Depends(get_session)) -> SettingsResponse:
    """Return the current persisted settings (catalog defaults applied)."""
    return SettingsResponse(**get_all_settings(session))


@router.put("/settings", response_model=MutationOkResponse)
def update_settings(
    body: dict[str, str | None] = Body(...),
    session: Session = Depends(get_session),
) -> MutationOkResponse:
    """Persist a subset of settings.

    The body is read as a raw mapping (not a Pydantic model) so unknown
    keys are surfaced with a stable error code instead of being silently
    dropped. ``None`` values are filtered out so the caller can send a
    partial update.
    """
    updates = {key: value for key, value in body.items() if value is not None}
    invalid = sorted(set(updates) - set(SETTINGS_CATALOG))
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_settings_key",
                "message": f"Unknown settings key: {invalid[0]}",
            },
        )
    set_settings_batch(session, updates)
    return MutationOkResponse()


@router.post("/settings/reset", response_model=MutationOkResponse)
def reset_settings_route(session: Session = Depends(get_session)) -> MutationOkResponse:
    """Restore all catalog settings to their defaults."""
    reset_settings(session)
    return MutationOkResponse()


@router.delete("/library/{job_id}", response_model=MutationOkResponse)
def delete_library_entry(
    job_id: int, session: Session = Depends(get_session)
) -> MutationOkResponse:
    """Delete a completed download from the library (and its file)."""
    deleted, reason = delete_from_library(session, job_id)
    if deleted:
        return MutationOkResponse()
    if reason == "not_found":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "library_entry_not_found",
                "message": f"Library entry {job_id} not found.",
            },
        )
    if reason == "not_done":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "library_entry_not_done",
                "message": f"Library entry {job_id} is not complete.",
            },
        )
    raise HTTPException(
        status_code=500,
        detail={
            "code": "library_delete_failed",
            "message": f"Could not delete library entry {job_id}.",
        },
    )
