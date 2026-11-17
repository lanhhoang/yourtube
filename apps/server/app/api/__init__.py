"""JSON API under ``/api``.

Later phases include their routers **before** the catch-all at the bottom.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import jobs, library, settings
from app.api.errors import ApiError

api_router = APIRouter(prefix="/api")

# Feature routers are included here, above the catch-all.
api_router.include_router(jobs.router)
api_router.include_router(library.router)
api_router.include_router(settings.router)


@api_router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
def api_not_found(path: str = "") -> None:
    raise ApiError(404, "not_found", "No such API endpoint.")


# A router prefix can't match bare "/api", so give it the same answer explicitly.
api_router.add_api_route(
    "",
    api_not_found,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
