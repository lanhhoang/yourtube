"""Serve the built Svelte app: real files by path, ``index.html`` for app paths."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse, Response

from app.config import settings

spa_router = APIRouter(include_in_schema=False)

_NOT_BUILT = "Web app not built. Run `pnpm build`."


@spa_router.get("/{path:path}")
def spa(path: str) -> Response:
    dist = settings.web_dist_dir.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return PlainTextResponse(_NOT_BUILT, status_code=404)
    if path:
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return FileResponse(candidate)
        if "." in path.rsplit("/", 1)[-1]:
            return PlainTextResponse("Not found.", status_code=404)
    return FileResponse(index)
