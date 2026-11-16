"""JSON API under ``/api``.

Later phases include their routers **before** the catch-all at the bottom.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import ApiError

api_router = APIRouter(prefix="/api")

# Feature routers are included here, above the catch-all.


@api_router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
def api_not_found(path: str) -> None:
    raise ApiError(404, "not_found", "No such API endpoint.")
