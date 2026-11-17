"""Library endpoints: list, search, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db import get_session
from app.schemas import JobOut
from app.services.library import delete_from_library, get_library, search_library

router = APIRouter(tags=["library"])

_DELETE_ERRORS = {
    "not_found": (404, "Download not found."),
    "not_done": (409, "Only finished downloads can be deleted."),
    "delete_failed": (500, "The file couldn't be deleted."),
}


@router.get("/library")
def list_library(q: str = "", session: Session = Depends(get_session)) -> list[JobOut]:
    query = q.strip()
    rows = search_library(session, query) if query else get_library(session)
    return [JobOut.from_row(r) for r in rows]


@router.delete("/library/{job_id}", status_code=204, response_class=Response)
def delete_job(job_id: int, session: Session = Depends(get_session)) -> Response:
    ok, reason = delete_from_library(session, job_id)
    if not ok:
        status, message = _DELETE_ERRORS[reason]
        raise ApiError(status, reason, message)
    return Response(status_code=204)
