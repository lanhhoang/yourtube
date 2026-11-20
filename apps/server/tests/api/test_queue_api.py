"""API tests for the queue endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Download


def _add(session: Session, status: str, **fields: object) -> int:
    row = Download(url="https://example.com/x", title=f"job-{status}", status=status, **fields)
    session.add(row)
    session.commit()
    return row.id


def _status(session: Session, job_id: int) -> str | None:
    session.expire_all()
    row = session.get(Download, job_id)
    return row.status if row else None


def test_queue_lists_active_failed_completed(
    client: TestClient, db_session_visible: Session
) -> None:
    queued_audio = _add(db_session_visible, "queued", audio_format_id="140")
    active = _add(db_session_visible, "active", progress=12.0)
    failed = _add(
        db_session_visible,
        "error",
        error_code="x",
        error_message="Nope",
        finished_at=datetime(2026, 1, 1),
    )
    done = _add(
        db_session_visible,
        "done",
        finished_at=datetime(2026, 1, 2),
        resolution_height=None,
    )
    body = client.get("/api/queue").json()
    assert [j["id"] for j in body["active"]] == [queued_audio, active]
    assert [j["id"] for j in body["failed"]] == [failed]
    assert [j["id"] for j in body["completed"]] == [done]
    assert body["active"][0]["media_kind"] == "audio"
    assert body["active"][1]["media_kind"] == "video"
    assert body["active"][1]["progress"] == 12.0
    assert body["failed"][0]["error_message"] == "Nope"
    assert body["completed"][0]["media_kind"] == "audio"


def test_cancel_queued_returns_204(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "queued")
    r = client.post(f"/api/downloads/{job}/cancel")
    assert r.status_code == 204
    assert _status(db_session_visible, job) == "cancelled"


def test_cancel_done_returns_409_error_body(
    client: TestClient, db_session_visible: Session
) -> None:
    job = _add(db_session_visible, "done")
    r = client.post(f"/api/downloads/{job}/cancel")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_cancellable"


def test_retry_endpoint_requeues(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "error", error_code="x", error_message="y", progress=30.0)
    r = client.post(f"/api/downloads/{job}/retry")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["error_message"] is None


def test_retry_done_job_conflicts(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "done")
    r = client.post(f"/api/downloads/{job}/retry")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_failed"
    assert _status(db_session_visible, job) == "done"


def test_retry_twice_second_conflicts(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "error")
    assert client.post(f"/api/downloads/{job}/retry").status_code == 200
    assert client.post(f"/api/downloads/{job}/retry").status_code == 409


def test_dismiss_failed_job_returns_204(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "error")
    assert client.post(f"/api/downloads/{job}/dismiss").status_code == 204
    assert _status(db_session_visible, job) is None


def test_dismiss_done_job_conflicts(client: TestClient, db_session_visible: Session) -> None:
    job = _add(db_session_visible, "done")
    r = client.post(f"/api/downloads/{job}/dismiss")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_failed"
    assert _status(db_session_visible, job) == "done"


def test_dismiss_failed_endpoint(client: TestClient, db_session_visible: Session) -> None:
    _add(db_session_visible, "error")
    _add(db_session_visible, "error")
    r = client.post("/api/queue/dismiss-failed")
    assert r.status_code == 200
    assert r.json() == {"dismissed": 2}
    assert client.get("/api/queue").json()["failed"] == []
    assert client.post("/api/queue/dismiss-failed").json() == {"dismissed": 0}


def test_retry_missing_404(client: TestClient) -> None:
    r = client.post("/api/downloads/999999/retry")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_dismiss_missing_404(client: TestClient) -> None:
    r = client.post("/api/downloads/999999/dismiss")
    assert r.status_code == 404


def test_cancel_last_queued_of_batch_sends_summary(
    monkeypatch, client: TestClient, db_session_visible: Session
) -> None:
    import json

    from app.models import PushSubscription
    from app.services import push

    sent: list[dict] = []
    monkeypatch.setattr(push, "webpush", lambda **kw: sent.append(json.loads(kw["data"])))
    monkeypatch.setattr(push, "load_vapid_keys", lambda *_a: push.VapidKeys("p", "q"))
    db_session_visible.add(
        PushSubscription(endpoint="https://web.push.apple.com/x", p256dh="p", auth="a")
    )
    _add(db_session_visible, "done", batch_id="b1", playlist_title="Mix")
    last = _add(db_session_visible, "queued", batch_id="b1", playlist_title="Mix")
    assert client.post(f"/api/downloads/{last}/cancel").status_code == 204
    assert len(sent) == 1
    assert sent[0]["title"] == "Mix"
    assert sent[0]["body"] == "1 downloaded, 1 cancelled"


def test_queue_lists_settled_batches(client: TestClient, db_session_visible: Session) -> None:
    from app.services.queue import claim_batch_summary

    _add(
        db_session_visible,
        "done",
        batch_id="b1",
        playlist_title="Mix",
        finished_at=datetime(2026, 1, 1),
    )
    _add(
        db_session_visible,
        "error",
        batch_id="b1",
        playlist_title="Mix",
        finished_at=datetime(2026, 1, 2),
    )
    assert claim_batch_summary(db_session_visible, "b1") is not None
    batches = client.get("/api/queue").json()["batches"]
    assert len(batches) == 1
    assert batches[0]["batch_id"] == "b1"
    assert batches[0]["name"] == "Mix"
    assert (batches[0]["done"], batches[0]["failed"], batches[0]["cancelled"]) == (1, 1, 0)
