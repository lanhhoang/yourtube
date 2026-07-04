"""Integration tests for the server-rendered page routes."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

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


def test_home_page_renders_batch_enqueue_panel() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="batch-form"' in response.text
    assert 'name="sources"' in response.text
    assert 'hx-post="/info/batch/form"' in response.text
    assert 'id="batch-result"' in response.text


def test_batch_enqueue_route_creates_one_queued_download_per_unique_url(
    db_session_visible,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data={
                "sources": "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b",
            },
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert all(row.status == "queued" for row in rows)
    assert "Added 2 items to queue." in response.text


def test_batch_enqueue_route_accepts_comma_separated_sources(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data={
                "sources": "https://example.com/a,https://example.com/b",
            },
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item(
    db_session_visible,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data={
                "url": ["https://example.com/a", "https://example.com/b"],
                "title": ["Title A", "Title B"],
                "uploader": ["Uploader A", "Uploader B"],
                "duration": ["12", "24"],
                "thumbnail": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
            },
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert rows[0].title == "Title A"
    assert rows[0].uploader == "Uploader A"
    assert rows[0].duration == 12
    assert rows[0].thumbnail == "https://example.com/a.jpg"
    assert rows[1].title == "Title B"
    assert rows[1].uploader == "Uploader B"
    assert rows[1].duration == 24
    assert rows[1].thumbnail == "https://example.com/b.jpg"
    assert "Added 2 items to queue." in response.text


def test_batch_lookup_fragment_renders_ready_and_error_cards(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        assert raw == "https://example.com/good\nhttps://example.com/bad"
        return BatchPreviewResult(
            items=[
                BatchPreviewItem(
                    source_url="https://example.com/good",
                    status="ready",
                    title="Good title",
                    uploader="Uploader",
                    duration=15,
                    thumbnail="https://example.com/thumb.jpg",
                    error_code=None,
                    error_message=None,
                ),
                BatchPreviewItem(
                    source_url="https://example.com/bad",
                    status="error",
                    title=None,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    error_code="http_forbidden",
                    error_message="The server returned a 403 Forbidden response.",
                ),
            ],
            valid_count=1,
            invalid_count=1,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post(
            "/info/batch/form",
            data={"sources": "https://example.com/good\nhttps://example.com/bad"},
        )

    assert response.status_code == 200
    assert "Batch preview" in response.text
    assert "1 ready / 1 failed" in response.text
    assert "Good title" in response.text
    assert "403 Forbidden" in response.text
    assert 'hx-post="/downloads/form"' in response.text
    assert 'hx-target="#batch-status"' in response.text
    assert 'name="url"' in response.text
    assert 'name="title"' in response.text
    assert 'name="uploader"' in response.text
    assert 'name="duration"' in response.text
    assert 'name="thumbnail"' in response.text
    assert 'name="target_id"' in response.text


def test_batch_lookup_fragment_renders_enqueue_all_form(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        assert raw == "https://example.com/good"
        return BatchPreviewResult(
            items=[
                BatchPreviewItem(
                    source_url="https://example.com/good",
                    status="ready",
                    title="Good title",
                    uploader="Uploader",
                    duration=15,
                    thumbnail="https://example.com/thumb.jpg",
                    error_code=None,
                    error_message=None,
                )
            ],
            valid_count=1,
            invalid_count=0,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert 'id="batch-enqueue-form"' in response.text
    assert 'hx-post="/downloads/batch/form"' in response.text
    assert 'hx-target="#batch-status"' in response.text
    assert 'name="url" value="https://example.com/good"' in response.text
    assert 'name="title" value="Good title"' in response.text
    assert "Enqueue all valid" in response.text


def test_batch_preview_card_enqueue_posts_metadata_to_queue(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/form",
            data={
                "url": "https://example.com/good",
                "title": "Good title",
                "uploader": "Uploader",
                "duration": "15",
                "thumbnail": "https://example.com/thumb.jpg",
                "target_id": "batch-status",
            },
        )

    assert response.status_code == 200
    assert 'id="batch-status"' in response.text
    assert 'id="info-status"' not in response.text
    row = db_session_visible.query(Download).one()
    assert row.url == "https://example.com/good"
    assert row.title == "Good title"
    assert row.uploader == "Uploader"
    assert row.duration == 15
    assert row.thumbnail == "https://example.com/thumb.jpg"


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


def test_queue_page_renders_notification_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'x-data="queueNotifications()"' in response.text
    assert 'id="toast-region"' in response.text


def test_queue_page_renders_recent_completions(db_session_visible) -> None:
    done = Download(
        url="https://example.com/done",
        title="Already finished",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 9, 15, 0),
    )
    db_session_visible.add(done)
    db_session_visible.commit()
    db_session_visible.refresh(done)

    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert f'data-completed-job-id="{done.id}"' in response.text


def test_queue_page_notification_script_seeds_silently_and_dedupes() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'sessionStorage.getItem("yt-seen-completed-jobs")' in response.text
    assert "scan(this.$root, { silent: true })" in response.text
    assert "dismiss(jobId)" in response.text
    assert "queue-after-finished-at" not in response.text
    assert "hx-include" not in response.text


def test_download_file_serves_completed_job(db_session_visible, tmp_path: Path) -> None:
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"data")
    row = Download(
        url="https://example.com/done",
        status="done",
        progress=100.0,
        file_path=str(file_path),
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/downloads/{row.id}/file")

    assert response.status_code == 200
    assert response.content == b"data"


def test_download_file_rejects_non_done_job(db_session_visible) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/downloads/{row.id}/file")

    assert response.status_code == 409


def test_download_file_returns_404_for_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.get("/downloads/9999/file")

    assert response.status_code == 404
