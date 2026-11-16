"""Uniform ``{"error": {"code", "message"}}`` bodies for ``/api`` routes."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """An error a route raises on purpose, with a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _body(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def _validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid request."
    first = errors[0]
    loc = [str(part) for part in first["loc"]]
    if loc and loc[0] in {"body", "query", "path"}:
        loc = loc[1:]
    msg = str(first["msg"])
    return f"{'.'.join(loc)}: {msg}" if loc else msg


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> Response:
        return _body(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if not _is_api(request):
            return await http_exception_handler(request, exc)
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _body(exc.status_code, f"http_{exc.status_code}", message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> Response:
        if not _is_api(request):
            return await request_validation_exception_handler(request, exc)
        return _body(422, "invalid_request", _validation_message(exc))
