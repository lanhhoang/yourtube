"""Server-rendered page routes and browser-facing HTML routes.

Page routes render full Jinja pages with useful initial state from the
existing services. Browser-facing HTMX routes return HTML fragments for
lookup, enqueue, queue refreshes, library actions, and settings
changes. The existing Phase 3A JSON API in ``app.routes.api`` stays
intact as the backend contract.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.library import get_library, search_library
from app.services.queue import get_active_jobs
from app.services.settings import get_all_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/home.html")


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {"rows": get_active_jobs(session)},
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
        {"settings_values": get_all_settings(session)},
    )
