"""Integration tests for the queue and library HTML partial routes."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_queue_rows_partial_renders_editorial_entries(db_session_visible) -> None:
    first = Download(url="https://example.com/a", title="First", status="queued", progress=0.0)
    second = Download(url="https://example.com/b", title="Second", status="active", progress=42.5)
    db_session_visible.add_all([first, second])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert "<tbody" not in response.text
    assert 'class="queue-entry"' in response.text
    assert 'hx-post="/queue/cancel/' in response.text


def test_library_rows_partial_renders_archive_entries(db_session_visible) -> None:
    row = Download(
        url="https://example.com/done",
        title="Saved clip",
        uploader="Uploader",
        status="done",
        progress=100.0,
    )
    db_session_visible.add(row)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/library/rows")

    assert response.status_code == 200
    assert 'class="library-entry"' in response.text
    assert "Saved clip" in response.text
    assert 'hx-delete="/library/delete/' in response.text


def test_library_rows_partial_links_to_pages_file_route(db_session_visible) -> None:
    row = Download(
        url="https://example.com/done",
        title="Done",
        status="done",
        progress=100.0,
        file_path="/tmp/done.mp4",
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get("/library/rows")

    assert response.status_code == 200
    assert f'href="/downloads/{row.id}/file"' in response.text
    assert f'href="/api/downloads/{row.id}/file"' not in response.text


def test_library_rows_partial_filters_by_query(db_session_visible) -> None:
    keep = Download(url="https://example.com/keep", title="Keep me", status="done", progress=100.0)
    skip = Download(url="https://example.com/skip", title="Skip me", status="done", progress=100.0)
    db_session_visible.add_all([keep, skip])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/library/rows", params={"q": "Keep"})

    assert response.status_code == 200
    assert 'class="library-entry"' in response.text
    assert "Keep me" in response.text
    assert "Skip me" not in response.text
    assert "?q=Keep" in response.text


def test_library_delete_preserves_active_filter(db_session_visible) -> None:
    keep = Download(url="https://example.com/keep", title="Keep me", status="done", progress=100.0)
    skip = Download(url="https://example.com/skip", title="Skip me", status="done", progress=100.0)
    db_session_visible.add_all([keep, skip])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.request("DELETE", f"/library/delete/{skip.id}", params={"q": "Keep"})

    assert response.status_code == 200
    assert "Keep me" in response.text
    assert "Skip me" not in response.text


def test_partials_render_explicit_empty_states() -> None:
    with TestClient(app) as client:
        queue = client.get("/queue/rows")
        library = client.get("/library/rows")

    assert "No queued or active downloads." in queue.text
    assert 'class="empty-state"' in queue.text
    assert "No completed downloads yet." in library.text
    assert 'class="empty-state"' in library.text


def test_queue_rows_partial_exposes_completion_markers(db_session_visible) -> None:
    done = Download(
        url="https://example.com/done",
        title="Done row",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 11, 30, 0),
    )
    db_session_visible.add(done)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert f'data-completed-job-id="{done.id}"' in response.text
    assert 'data-completed-job-title="Done row"' in response.text
    assert "data-completed-finished-at" not in response.text
    assert "data-completed-cursor-id" not in response.text
