"""API tests for settings and diagnostics endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Setting


def test_settings_roundtrip(client: TestClient, db_session_visible: Session) -> None:
    body = {
        "max_concurrent": 3,
        "proxy_url": " http://p:1 ",
        "cookies_path": "/c.txt",
        "downloads_dir": "/d",
    }
    r = client.put("/api/settings", json=body)
    assert r.status_code == 200
    got = client.get("/api/settings").json()
    assert got == {**body, "proxy_url": "http://p:1"}


def test_settings_rejects_out_of_range(client: TestClient) -> None:
    r = client.put("/api/settings", json={"max_concurrent": 9})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_settings_ignores_stale_playlist_page_size(
    client: TestClient, db_session_visible: Session
) -> None:
    db_session_visible.add(Setting(key="playlist_page_size", value="30"))
    db_session_visible.commit()
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "playlist_page_size" not in r.json()


def test_settings_reset_restores_defaults(client: TestClient, db_session_visible: Session) -> None:
    client.put("/api/settings", json={"max_concurrent": 4, "proxy_url": "http://p"})
    r = client.post("/api/settings/reset")
    assert r.status_code == 200
    assert r.json() == {
        "max_concurrent": 1,
        "proxy_url": "",
        "cookies_path": "",
        "downloads_dir": "",
    }


def test_diagnostics_shape(client: TestClient) -> None:
    r = client.get("/api/diagnostics")
    assert r.status_code == 200
    assert set(r.json()) == {"level", "messages", "js_runtime_ready", "workers_enabled"}
