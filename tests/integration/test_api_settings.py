"""Integration tests for ``/api/settings``."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.settings import set_setting


def test_get_settings_returns_catalog_values() -> None:
    with TestClient(app) as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["max_concurrent"] == "1"
    assert payload["proxy_url"] == ""
    assert payload["cookies_path"] == ""
    assert payload["downloads_dir"] == ""


def test_update_settings_rejects_unknown_keys() -> None:
    with TestClient(app) as client:
        response = client.put("/api/settings", json={"made_up": "value"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_settings_key"


def test_update_settings_persists_known_keys(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/settings",
            json={"max_concurrent": "3", "proxy_url": "http://proxy:8080"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    verify = client.get("/api/settings")
    assert verify.status_code == 200
    body = verify.json()
    assert body["max_concurrent"] == "3"
    assert body["proxy_url"] == "http://proxy:8080"


def test_reset_settings_restores_defaults(db_session_visible) -> None:
    set_setting(db_session_visible, "max_concurrent", "4")

    with TestClient(app) as client:
        response = client.post("/api/settings/reset")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
