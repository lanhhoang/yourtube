"""Integration tests for ``POST /api/info``.

The endpoint proxies ``extract_info`` and normalises the result into
``InfoResponse``. These tests monkeypatch ``app.routes.api.extract_info``
to avoid hitting the network.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient

from app.main import app
from app.services.settings import set_settings_batch


def test_fetch_info_returns_normalized_formats(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Example uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [{"format_id": "18", "ext": "mp4", "resolution": "360p"}],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.api.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/api/info", json={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Example title"
    assert payload["formats"][0]["format_id"] == "18"
    assert payload["formats"][0]["ext"] == "mp4"


def test_fetch_info_uses_saved_proxy_and_cookies_when_opted_in(
    monkeypatch, db_session_visible, tmp_path
) -> None:
    cookies_path = tmp_path / "cookies.txt"
    set_settings_batch(
        db_session_visible,
        {
            "proxy_url": "http://proxy.internal:8080",
            "cookies_path": str(cookies_path),
        },
    )
    captured: dict[str, str | None] = {}

    def fake_extract_info(url: str, **kwargs):
        captured["url"] = url
        captured["proxy"] = kwargs.get("proxy")
        captured["cookies_file"] = kwargs.get("cookies_file")
        return {
            "url": url,
            "title": "Example title",
            "formats": [],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.api.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post(
            "/api/info",
            json={"url": "https://example.com/watch?v=1", "proxy": True, "cookies": True},
        )

    assert response.status_code == 200
    assert captured["proxy"] == "http://proxy.internal:8080"
    assert captured["cookies_file"] == str(cookies_path)


def test_info_lookup_uses_configured_js_runtime(monkeypatch) -> None:
    """Phase 5: ``/api/info`` must pass an explicit ``js_runtimes`` config to yt-dlp.

    Without it, the YouTube extractor cannot solve JS challenges on
    hosts that do not ship Node.js by default. The test drops a
    monkeypatched ``FakeYDL`` into ``yt_dlp.YoutubeDL`` and asserts the
    options the API handed it.
    """
    captured: dict[str, object] = {}

    class FakeYDL:
        def __init__(self, options):
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            return {"url": url, "title": "Video", "formats": []}

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDL)

    with TestClient(app) as client:
        response = client.post(
            "/api/info",
            json={"url": "https://example.com/v", "proxy": False, "cookies": False},
        )

    assert response.status_code == 200
    options = cast(dict[str, Any], captured["options"])
    assert options["js_runtimes"] == {"node": {"path": "node"}}
