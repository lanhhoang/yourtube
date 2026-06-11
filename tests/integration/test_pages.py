"""Integration tests for the server-rendered page routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download
from app.services.settings import set_settings_batch


def test_home_queue_library_and_settings_pages_render() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        queue = client.get("/queue")
        library = client.get("/library")
        settings = client.get("/settings")

    assert home.status_code == 200
    assert "Download a video" in home.text
    assert queue.status_code == 200
    assert "Active Queue" in queue.text
    assert library.status_code == 200
    assert "Library" in library.text
    assert settings.status_code == 200
    assert "Settings" in settings.text


def test_queue_and_library_pages_render_initial_rows(db_session_visible) -> None:
    queued = Download(
        url="https://example.com/q", title="Queued row", status="queued", progress=0.0
    )
    done = Download(
        url="https://example.com/d", title="Done row", status="done", progress=100.0
    )
    db_session_visible.add_all([queued, done])
    db_session_visible.commit()

    with TestClient(app) as client:
        queue = client.get("/queue")
        library = client.get("/library")

    assert "Queued row" in queue.text
    assert "Done row" in library.text


def test_settings_page_renders_persisted_values(db_session_visible) -> None:
    set_settings_batch(
        db_session_visible,
        {
            "max_concurrent": "3",
            "proxy_url": "http://proxy.internal:8080",
            "cookies_path": "/tmp/cookies.txt",
            "downloads_dir": "/tmp/downloads",
        },
    )

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'value="3"' in response.text
    assert 'value="http://proxy.internal:8080"' in response.text
    assert 'value="/tmp/cookies.txt"' in response.text
    assert 'value="/tmp/downloads"' in response.text


def test_pages_extend_index_layout_and_load_local_htmx() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        htmx = client.get("/static/vendor/htmx.min.js")

    assert response.status_code == 200
    assert '/static/vendor/htmx.min.js' in response.text
    assert 'hx-' in response.text
    assert htmx.status_code == 200


def test_home_page_exposes_lookup_and_enqueue_hooks() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="info-form"' in response.text
    assert 'id="info-result"' in response.text
    assert 'hx-post="/info/form"' in response.text


def test_library_page_exposes_search_hooks() -> None:
    with TestClient(app) as client:
        response = client.get("/library")

    assert response.status_code == 200
    assert 'id="library-search-form"' in response.text
    assert 'hx-get="/library/rows"' in response.text
    assert 'id="library-rows"' in response.text


def test_settings_page_exposes_form_and_restart_notice() -> None:
    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'id="settings-form"' in response.text
    assert 'hx-put="/settings/form"' in response.text
    assert "takes effect after restart" in response.text


def test_info_lookup_fragment_renders_enqueue_form(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [{"format_id": "18", "ext": "mp4", "resolution": "360p"}],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert 'id="enqueue-form"' in response.text
    assert "Example title" in response.text


def test_settings_reset_returns_updated_form(db_session_visible) -> None:
    set_settings_batch(db_session_visible, {"max_concurrent": "4"})

    with TestClient(app) as client:
        response = client.post("/settings/reset")

    assert response.status_code == 200
    assert 'value="1"' in response.text
