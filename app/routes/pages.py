"""Server-rendered page routes and browser-facing HTML routes.

Page routes render full Jinja pages with useful initial state from the
existing services. Browser-facing HTMX routes return HTML fragments for
lookup, enqueue, queue refreshes, library actions, settings
changes, and downloaded file delivery.
"""

from __future__ import annotations

from itertools import zip_longest
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.datastructures import FormData, UploadFile

from app.config import settings
from app.db import get_session
from app.models import Download
from app.schemas import DownloadCreate
from app.services.batch_preview import (
    expand_playlist_entries,
    parse_source_urls,
    resolve_batch_preview,
)
from app.services.diagnostics import collect_runtime_diagnostics
from app.services.downloader import (
    build_stream_picker_payload,
    extract_flat_info,
    extract_info,
    normalize_formats,
)
from app.services.library import delete_from_library, get_library, search_library
from app.services.queue import (
    cancel_job,
    enqueue_download,
    get_active_jobs,
    get_recent_completed_jobs,
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


def _form_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


# --- Page routes -----------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/home.html")


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": get_recent_completed_jobs(session),
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
def queue_rows(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "partials/queue_rows.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": get_recent_completed_jobs(session),
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


@router.get("/downloads/{job_id}/file")
def download_file(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    """Stream the completed file for a ``done`` job.

    Returns 404 when the row is missing, 409 when the job is not yet
    ready, and 404 when the on-disk file has been moved or deleted.
    """
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Download not found.")
    if row.status != "done" or not row.file_path:
        raise HTTPException(status_code=409, detail="Download is not ready.")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is missing.")
    return FileResponse(path)


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


@router.post("/info/batch/form", response_class=HTMLResponse)
def info_batch_form(
    request: Request,
    sources: str = Form(...),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runtime = resolve_runtime_settings(session)
    proxy_url = runtime.proxy_url if proxy else None
    cookies_file = str(runtime.cookies_path) if cookies and runtime.cookies_path else None
    result = resolve_batch_preview(
        sources,
        extract_info=extract_info,
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=proxy_url,
            cookies_file=cookies_file,
        ),
        proxy=proxy_url,
        cookies_file=cookies_file,
    )
    return templates.TemplateResponse(
        request,
        "partials/batch_result.html",
        {"result": result},
    )


@router.post("/downloads/form", response_class=HTMLResponse)
async def downloads_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    duration_raw = _form_str(form, "duration")
    target_id = _form_str(form, "target_id")
    if target_id != "batch-status":
        target_id = "info-status"
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
        {"message": "Added to queue.", "target_id": target_id},
    )


@router.post("/downloads/batch/form", response_class=HTMLResponse)
async def downloads_batch_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    raw_sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(raw_sources)

    if urls:
        for url in urls:
            enqueue_download(session, DownloadCreate(url=url))
        return templates.TemplateResponse(
            request,
            "partials/status_message.html",
            {"message": f"Added {len(urls)} items to queue.", "target_id": "batch-status"},
        )

    queued_count = 0
    for url, title, uploader, duration, thumbnail, video_id, audio_id in zip_longest(
        _form_values(form, "url"),
        _form_values(form, "title"),
        _form_values(form, "uploader"),
        _form_values(form, "duration"),
        _form_values(form, "thumbnail"),
        _form_values(form, "video_format_id"),
        _form_values(form, "audio_format_id"),
        fillvalue="",
    ):
        if not url:
            continue
        enqueue_download(
            session,
            DownloadCreate(
                url=url,
                title=title or None,
                uploader=uploader or None,
                duration=int(duration) if duration else None,
                thumbnail=thumbnail or None,
                video_format_id=video_id or None,
                audio_format_id=audio_id or None,
            ),
        )
        queued_count += 1

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": f"Added {queued_count} items to queue.", "target_id": "batch-status"},
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
