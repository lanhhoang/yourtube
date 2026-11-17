"""API tests for POST /api/sources."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services import downloader


def _post(client: TestClient, urls: str):
    return client.post("/api/sources", json={"urls": urls})


def test_sources_endpoint_video(client: TestClient, monkeypatch) -> None:
    info = {
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
    monkeypatch.setattr(downloader, "extract_flat_info", lambda url, **kw: info)
    r = _post(client, "https://e.test/v")
    assert r.status_code == 200
    assert r.json()["kind"] == "video" and r.json()["video"]["best_short_side"] == 720
    assert r.json()["video"]["picker"]["video_streams"][0]["width"] == 1280


def test_sources_endpoint_single_failure_is_502(client: TestClient, monkeypatch) -> None:
    def boom(url, **kw):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(downloader, "extract_flat_info", boom)
    r = _post(client, "https://e.test/v")
    assert r.status_code == 502
    assert r.json()["error"]["code"] and r.json()["error"]["message"]


def test_sources_endpoint_no_urls_422(client: TestClient) -> None:
    r = _post(client, "hello")
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_urls"
