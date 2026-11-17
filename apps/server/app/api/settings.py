"""Settings and diagnostics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import settings as app_settings
from app.db import get_session
from app.schemas import DiagnosticsOut, SettingsIn, SettingsOut
from app.services import settings as settings_service
from app.services.diagnostics import collect_runtime_diagnostics

router = APIRouter(tags=["settings"])


def _current(session: Session) -> SettingsOut:
    values = settings_service.get_all_settings(session)
    return SettingsOut(
        max_concurrent=int(values["max_concurrent"]),
        proxy_url=values["proxy_url"],
        cookies_path=values["cookies_path"],
        downloads_dir=values["downloads_dir"],
    )


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)) -> SettingsOut:
    return _current(session)


@router.put("/settings")
def put_settings(body: SettingsIn, session: Session = Depends(get_session)) -> SettingsOut:
    try:
        settings_service.set_settings_batch(
            session,
            {
                "max_concurrent": str(body.max_concurrent),
                "proxy_url": body.proxy_url.strip(),
                "cookies_path": body.cookies_path.strip(),
                "downloads_dir": body.downloads_dir.strip(),
            },
        )
    except ValueError as exc:
        raise ApiError(422, "invalid_settings", str(exc)) from exc
    return _current(session)


@router.post("/settings/reset")
def reset(session: Session = Depends(get_session)) -> SettingsOut:
    settings_service.reset_settings(session)
    return _current(session)


@router.get("/diagnostics")
def diagnostics() -> DiagnosticsOut:
    diag = collect_runtime_diagnostics(workers_enabled=app_settings.workers_enabled)
    return DiagnosticsOut.model_validate(diag, from_attributes=True)
