"""API tests for POST /api/lookup."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.services import downloader

INFO = {
    "title": "V",
    "webpage_url": "https://e.test/v",
    "formats": [
        {
            "format_id": "v",
            "ext": "mp4",
            "width": 1280,
            "height": 720,
            "vcodec": "avc1",
            "acodec": "none",
        }
    ],
}


def _post(client: TestClient, **body: Any):
    return client.post("/api/lookup", json={"url": "https://e.test/v", **body})


def test_lookup_returns_details(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(downloader, "extract_info", lambda url, **kw: INFO)
    r = _post(client)
    assert r.status_code == 200
    assert r.json()["best_short_side"] == 720
    assert r.json()["title"] == "V"


def test_lookup_uses_noplaylist(client: TestClient, monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake(url, **kw):
        seen.update(kw)
        return INFO

    monkeypatch.setattr(downloader, "extract_info", fake)
    assert _post(client).status_code == 200
    assert seen["noplaylist"] is True


def test_lookup_failure_is_502_with_friendly_message(client: TestClient, monkeypatch) -> None:
    def boom(url, **kw):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(downloader, "extract_info", boom)
    r = _post(client)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "http_forbidden"


def test_lookup_playlist_url_is_422(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        downloader, "extract_info", lambda url, **kw: {"_type": "playlist", "entries": []}
    )
    r = _post(client)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "not_a_video"


def test_lookup_passes_proxy_only_when_asked(client: TestClient, monkeypatch) -> None:
    seen: list[Any] = []

    def fake(url, **kw):
        seen.append(kw["proxy"])
        return INFO

    monkeypatch.setattr(downloader, "extract_info", fake)
    put = client.put("/api/settings", json={"max_concurrent": 1, "proxy_url": "http://p:1"})
    assert put.status_code == 200
    _post(client)
    _post(client, use_proxy=True)
    assert seen == [None, "http://p:1"]
