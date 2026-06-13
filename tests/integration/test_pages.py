"""Integration tests for the server-rendered page routes."""

from __future__ import annotations

import json
import re

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
    assert "Download with editorial calm." in home.text
    assert queue.status_code == 200
    assert "Queue ledger" in queue.text
    assert library.status_code == 200
    assert "Archive library" in library.text
    assert settings.status_code == 200
    assert "Control settings" in settings.text


def test_queue_and_library_pages_render_initial_rows(db_session_visible) -> None:
    queued = Download(
        url="https://example.com/q", title="Queued row", status="queued", progress=0.0
    )
    done = Download(url="https://example.com/d", title="Done row", status="done", progress=100.0)
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


def test_pages_extend_editorial_shell_and_load_local_assets() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        htmx = client.get("/static/vendor/htmx.min.js")
        alpine = client.get("/static/vendor/alpine.min.js")
        css = client.get("/static/css/app.css")
        favicon = client.get("/static/assets/favicon.svg")

    assert response.status_code == 200
    assert "/static/css/app.css" in response.text
    assert "/static/vendor/htmx.min.js" in response.text
    assert "/static/vendor/alpine.min.js" in response.text
    assert "/static/assets/favicon.svg" in response.text
    assert "Playfair Display" in response.text
    assert "Work Sans" in response.text
    assert 'class="site-header"' in response.text
    assert 'class="site-nav"' in response.text
    assert css.status_code == 200
    assert "--bg:" in css.text
    assert htmx.status_code == 200
    assert alpine.status_code == 200
    assert favicon.status_code == 200


def test_pages_load_local_alpine_asset() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        alpine = client.get("/static/vendor/alpine.min.js")

    assert response.status_code == 200
    assert "/static/vendor/alpine.min.js" in response.text
    assert alpine.status_code == 200


def test_home_page_renders_landing_first_editorial_sections() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Download with editorial calm." in response.text
    assert 'id="info-form"' in response.text
    assert 'id="info-result"' in response.text
    assert 'hx-post="/info/form"' in response.text
    assert "Recent workflow" in response.text


def test_queue_page_renders_ledger_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert "Queue ledger" in response.text
    assert 'id="queue-rows"' in response.text
    assert 'hx-get="/queue/rows"' in response.text
    assert 'hx-trigger="load, every 2s"' in response.text
    assert "Queued and active downloads update automatically." in response.text


def test_library_page_renders_archive_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/library")

    assert response.status_code == 200
    assert "Archive library" in response.text
    assert 'id="library-search-form"' in response.text
    assert 'id="library-rows"' in response.text
    assert 'hx-get="/library/rows"' in response.text


def test_settings_page_renders_editorial_control_room() -> None:
    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert "Control settings" in response.text
    assert 'id="settings-form"' in response.text
    assert 'id="settings-status"' in response.text
    assert 'hx-put="/settings/form"' in response.text
    assert "takes effect after restart" in response.text


def test_info_lookup_fragment_renders_editorial_media_card(monkeypatch) -> None:
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
    assert 'class="media-card"' in response.text
    assert "Example title" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert 'name="output_template"' in response.text
    assert 'name="audio_bitrate"' in response.text
    assert 'name="subtitles"' in response.text


def test_info_lookup_fragment_renders_stream_picker_markup(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {
                    "format_id": "401",
                    "ext": "mp4",
                    "container": "mp4_dash",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "height": 2160,
                    "resolution": "2160p",
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "container": "m4a_dash",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "audio_channels": 2,
                },
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "container": "mp4",
                    "vcodec": "avc1.42001E",
                    "acodec": "mp4a.40.2",
                    "resolution": "360p",
                },
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    match = re.search(r"x-data='([^']+)'", response.text)
    assert match is not None
    x_data = match.group(1)
    assert x_data.startswith("streamPicker(")
    assert x_data.endswith(")")
    payload = json.loads(x_data.removeprefix("streamPicker(").removesuffix(")"))
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert "Expected container" in response.text
    assert payload["video_streams"][0]["format_id"] == "401"
    assert payload["audio_streams"][0]["format_id"] == "140"
    assert payload["has_muxed_streams"] is True
    assert payload["expected_container_by_pair"]["401|140"] == "mp4"
    assert all(row["format_id"] != "18" for row in payload["video_streams"])
    assert all(row["format_id"] != "18" for row in payload["audio_streams"])
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert ':value="selectedVideoId"' in response.text
    assert ':value="selectedAudioId"' in response.text
    assert 'name="title"' in response.text
    assert 'name="uploader"' in response.text
    assert 'name="duration"' in response.text
    assert 'name="thumbnail"' in response.text
    assert 'name="output_template"' in response.text
    assert 'name="audio_bitrate"' in response.text
    assert 'name="subtitles"' in response.text
    assert "x-cloak" in response.text
    assert "Default format selection remains available" in response.text


def test_settings_reset_returns_updated_form(db_session_visible) -> None:
    set_settings_batch(db_session_visible, {"max_concurrent": "4"})

    with TestClient(app) as client:
        response = client.post("/settings/reset")

    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'id="settings-form"' in response.text
    assert 'value="1"' in response.text


def test_settings_page_renders_runtime_status(monkeypatch) -> None:
    class _FakeStatus:
        def __init__(self) -> None:
            self.level = "warning"
            self.messages = ["Node.js runtime missing."]
            self.js_runtime_ready = False
            self.workers_enabled = True

    monkeypatch.setattr(
        "app.routes.pages.collect_runtime_diagnostics", lambda *, workers_enabled: _FakeStatus()
    )

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'class="status-card status-card-warning"' in response.text
    assert "Node.js runtime missing." in response.text
