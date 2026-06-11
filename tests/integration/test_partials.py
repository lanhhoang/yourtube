"""Integration tests for the queue and library HTML partial routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_queue_rows_partial_renders_fragment_only_html(db_session_visible) -> None:
    first = Download(url="https://example.com/a", title="First", status="queued", progress=0.0)
    second = Download(url="https://example.com/b", title="Second", status="active", progress=42.5)
    db_session_visible.add_all([first, second])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert "<tbody" not in response.text
    assert response.text.index("First") < response.text.index("Second")
    assert 'hx-post="/queue/cancel/' in response.text


def test_library_rows_partial_filters_by_query(db_session_visible) -> None:
    keep = Download(url="https://example.com/keep", title="Keep me", status="done", progress=100.0)
    skip = Download(url="https://example.com/skip", title="Skip me", status="done", progress=100.0)
    db_session_visible.add_all([keep, skip])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/library/rows", params={"q": "Keep"})

    assert response.status_code == 200
    assert "Keep me" in response.text
    assert "Skip me" not in response.text
    assert 'hx-delete="/library/delete/' in response.text


def test_partials_render_explicit_empty_states() -> None:
    with TestClient(app) as client:
        queue = client.get("/queue/rows")
        library = client.get("/library/rows")

    assert "No queued or active downloads." in queue.text
    assert "No completed downloads yet." in library.text
