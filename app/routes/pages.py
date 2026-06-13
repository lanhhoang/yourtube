"""Server-rendered page routes and browser-facing HTML routes.

Page routes render full Jinja pages with useful initial state from the
existing services. Browser-facing HTMX routes return HTML fragments for
lookup, enqueue, queue refreshes, library actions, and settings
changes. The existing Phase 3A JSON API in ``app.routes.api`` stays
intact as the backend contract.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.datastructures import FormData, UploadFile

from app.config import settings
from app.db import get_session
from app.schemas import DownloadCreate
from app.services.diagnostics import collect_runtime_diagnostics
from app.services.downloader import (
    build_stream_picker_payload,
    extract_info,
    normalize_formats,
)
from app.services.library import delete_from_library, get_library, search_library
from app.services.queue import (
    cancel_job,
    enqueue_download,
    get_active_jobs,
    get_completed_jobs_after,
    get_latest_completion_cursor,
)
from app.services.settings import (
    get_all_settings,
    reset_settings,
    resolve_runtime_settings,
    set_settings_batch,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


def _form_str(form: FormData, key: str) -> str | None:
    """Return a string form value or ``None`` for missing/non-string entries."""
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


# --- Page routes -----------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/home.html")


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    latest_finished_at, latest_id = get_latest_completion_cursor(session)
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": [],
            "after_finished_at": latest_finished_at.isoformat() if latest_finished_at else "",
            "after_id": latest_id,
        },
    )


@router.get("/library", response_class=HTMLResponse)
def library_page(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        request,
        "pages/library.html",
        {"rows": rows, "query": q},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {
            "settings_values": get_all_settings(session),
            "runtime_status": collect_runtime_diagnostics(workers_enabled=settings.workers_enabled),
        },
    )


# --- HTMX fragment routes --------------------------------------------------


@router.get("/queue/rows", response_class=HTMLResponse)
def queue_rows(
    request: Request,
    after_finished_at: str = Query(default=""),
    after_id: int = Query(default=0),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    cursor_dt = datetime.fromisoformat(after_finished_at) if after_finished_at else None
    return templates.TemplateResponse(
        request,
        "partials/queue_rows.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": get_completed_jobs_after(
                session,
                after_finished_at=cursor_dt,
                after_id=after_id,
            ),
        },
    )


@router.get("/library/rows", response_class=HTMLResponse)
def library_rows(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        request,
        "partials/library_rows.html",
        {"rows": rows, "query": q},
    )


# --- HTMX mutation routes --------------------------------------------------


@router.post("/info/form", response_class=HTMLResponse)
def info_form(
    request: Request,
    url: str = Form(...),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runtime = resolve_runtime_settings(session)
    raw = extract_info(
        url,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
    formats = normalize_formats(raw)
    return templates.TemplateResponse(
        request,
        "partials/info_result.html",
        {
            "url": url,
            "title": raw.get("title", ""),
            "uploader": raw.get("uploader"),
            "duration": raw.get("duration"),
            "thumbnail": raw.get("thumbnail"),
            "formats": formats,
            "picker_payload": build_stream_picker_payload(formats),
        },
    )


@router.post("/downloads/form", response_class=HTMLResponse)
async def downloads_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    duration_raw = _form_str(form, "duration")
    payload = DownloadCreate(
        url=_form_str(form, "url") or "",
        title=_form_str(form, "title"),
        uploader=_form_str(form, "uploader"),
        duration=int(duration_raw) if duration_raw else None,
        thumbnail=_form_str(form, "thumbnail"),
        video_format_id=_form_str(form, "video_format_id"),
        audio_format_id=_form_str(form, "audio_format_id"),
        output_template=_form_str(form, "output_template"),
        audio_bitrate=_form_str(form, "audio_bitrate"),
        subtitles=form.get("subtitles") == "on",
    )
    enqueue_download(session, payload)
    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": "Added to queue.", "target_id": "info-status"},
    )


@router.post("/queue/cancel/{job_id}", response_class=HTMLResponse)
def queue_cancel(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    cancel_job(session, job_id)
    return templates.TemplateResponse(
        request,
        "partials/queue_rows.html",
        {"rows": get_active_jobs(session), "completed_rows": []},
    )


@router.delete("/library/delete/{job_id}", response_class=HTMLResponse)
def library_delete(
    job_id: int,
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    delete_from_library(session, job_id)
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        request,
        "partials/library_rows.html",
        {"rows": rows, "query": q},
    )


@router.put("/settings/form", response_class=HTMLResponse)
async def settings_form_put(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    set_settings_batch(
        session,
        {
            "max_concurrent": str(form["max_concurrent"]),
            "proxy_url": str(form.get("proxy_url", "")),
            "cookies_path": str(form.get("cookies_path", "")),
            "downloads_dir": str(form.get("downloads_dir", "")),
        },
    )
    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": "Settings saved.", "target_id": "settings-status"},
    )


@router.post("/settings/reset", response_class=HTMLResponse)
def settings_reset(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    reset_settings(session)
    return templates.TemplateResponse(
        request,
        "partials/settings_form.html",
        {"settings_values": get_all_settings(session)},
    )
