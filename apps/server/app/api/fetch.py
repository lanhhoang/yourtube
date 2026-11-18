"""Fetch endpoints: what a pasted URL turns out to be."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db import get_session
from app.schemas import LookupRequest, SourcesRequest, SourcesResult, VideoDetails
from app.services import downloader
from app.services.error_mapper import friendly_ytdlp_error
from app.services.settings import resolve_runtime_settings
from app.services.sources import NotAVideoError, list_sources, lookup_video

router = APIRouter(tags=["fetch"])


@router.post("/sources")
def sources(body: SourcesRequest, session: Session = Depends(get_session)) -> SourcesResult:
    runtime = resolve_runtime_settings(session)
    try:
        return list_sources(
            body.urls,
            extract_flat=lambda *a, **k: downloader.extract_flat_info(*a, **k),
            extract_full=lambda *a, **k: downloader.extract_info(*a, **k),
            proxy=runtime.proxy_url if body.use_proxy else None,
            cookies_file=(
                str(runtime.cookies_path) if body.use_cookies and runtime.cookies_path else None
            ),
        )
    except ValueError as exc:
        raise ApiError(422, "no_urls", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        code, message = friendly_ytdlp_error(str(exc))
        raise ApiError(502, code, message) from exc


@router.post("/lookup")
def lookup(body: LookupRequest, session: Session = Depends(get_session)) -> VideoDetails:
    runtime = resolve_runtime_settings(session)
    try:
        return lookup_video(
            body.url,
            extract_full=lambda *a, **k: downloader.extract_info(*a, **k),
            proxy=runtime.proxy_url if body.use_proxy else None,
            cookies_file=(
                str(runtime.cookies_path) if body.use_cookies and runtime.cookies_path else None
            ),
        )
    except NotAVideoError as exc:
        raise ApiError(422, "not_a_video", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        code, message = friendly_ytdlp_error(str(exc))
        raise ApiError(502, code, message) from exc
