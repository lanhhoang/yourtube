from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.errors import ApiError, install_error_handlers


class Body(BaseModel):
    jobs: list[dict[str, str]]


@pytest.fixture()
def mini() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    router = APIRouter(prefix="/api")

    @router.get("/busy")
    def busy() -> None:
        raise ApiError(409, "busy", "Busy.")

    @router.get("/nope")
    def nope() -> None:
        raise HTTPException(403, "Nope.")

    @router.get("/odd")
    def odd() -> None:
        raise HTTPException(500, {"x": 1})

    @router.post("/body")
    def body(b: Body) -> None: ...

    app.include_router(router)

    @app.get("/old")
    def old() -> None:
        raise HTTPException(404, "Old.")

    return TestClient(app)


def test_unknown_api_path_returns_error_body(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "No such API endpoint."}}


def test_old_routes_keep_default_errors(client):
    r = client.get("/downloads/999999/file")
    assert r.status_code == 404 and "error" not in r.json()


def test_api_error_body(mini):
    r = mini.get("/api/busy")
    assert r.status_code == 409
    assert r.json() == {"error": {"code": "busy", "message": "Busy."}}


def test_http_exception_body(mini):
    r = mini.get("/api/nope")
    assert r.status_code == 403
    assert r.json() == {"error": {"code": "http_403", "message": "Nope."}}
    assert mini.get("/api/odd").json()["error"] == {
        "code": "http_500",
        "message": "Request failed.",
    }


def test_validation_error_body(mini):
    r = mini.post("/api/body", json={"jobs": [{"url": "x"}, 5]})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_request"
    assert err["message"].startswith("jobs.1: ")
    r = mini.post("/api/body", json={})
    assert r.json()["error"]["message"] == "jobs: Field required"


def test_non_api_paths_keep_defaults(mini):
    assert mini.get("/old").json() == {"detail": "Old."}
