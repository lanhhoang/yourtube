"""Tests for push message building and sending."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pywebpush import WebPushException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Download, PushSubscription
from app.services import push
from app.services.push import PushMessage, batch_message, job_message, send_to_all
from app.services.queue import BatchSummary


@pytest.fixture(autouse=True)
def _keys(monkeypatch) -> None:
    push._keys_cache.clear()
    monkeypatch.setattr(push, "load_vapid_keys", lambda *_a, **_k: push.VapidKeys("priv", "pub"))


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _recorder(calls: list[dict], fail: dict | None = None):
    def send(**kwargs):
        calls.append({**kwargs, "vapid_claims": dict(kwargs["vapid_claims"])})
        exc = (fail or {}).get(kwargs["subscription_info"]["endpoint"])
        if exc is not None:
            raise exc

    return send


def _row(**kw) -> Download:
    return Download(id=kw.pop("id", 7), url="https://example.com/v", **kw)


def test_job_messages() -> None:
    done = job_message(_row(status="done", title="T"))
    assert done == PushMessage("Downloaded", "T", "job-7", "/#/watch/7")
    err = job_message(_row(status="error", error_message="boom"))
    assert err == PushMessage("Download failed", "https://example.com/v: boom", "job-7", "/#/queue")
    assert job_message(_row(status="cancelled")) is None


def test_body_cut_to_200() -> None:
    msg = job_message(_row(status="error", title="T", error_message="x" * 500))
    assert msg is not None
    assert len(msg.body) == 200
    assert msg.body.endswith("…")


def test_batch_message() -> None:
    s = BatchSummary("b1", "Mix", 12, 1, 0, None)
    assert batch_message(s) == PushMessage("Mix", "12 downloaded, 1 failed", "batch-b1", "/#/queue")
    assert batch_message(BatchSummary("b1", "Mix", 0, 0, 0, None)).body == "0 downloaded"


def _subs(session: Session, *endpoints: str) -> None:
    for e in endpoints:
        session.add(PushSubscription(endpoint=e, p256dh="p", auth="a"))
    session.commit()


APPLE = "https://web.push.apple.com/a"
FCM = "https://fcm.googleapis.com/b"


def test_two_services_get_own_claims_and_ttl(db_session: Session) -> None:
    _subs(db_session, APPLE, FCM)
    calls: list[dict] = []
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls))
    assert len(calls) == 2
    assert calls[0]["vapid_claims"] is not calls[1]["vapid_claims"]
    assert all(c["ttl"] == 86400 for c in calls)
    assert all(c["timeout"] == 10 for c in calls)
    assert all(c["vapid_claims"] == {"sub": settings.vapid_subject} for c in calls)
    assert all(c["vapid_private_key"] for c in calls)
    assert json.loads(calls[0]["data"]) == {"title": "t", "body": "b", "tag": "tag", "url": "/u"}


def test_custom_timeout_passed(db_session: Session) -> None:
    _subs(db_session, APPLE)
    calls: list[dict] = []
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls), timeout=3)
    assert calls[0]["timeout"] == 3


def test_404_deletes_subscription(db_session: Session) -> None:
    _subs(db_session, APPLE, FCM)
    calls: list[dict] = []
    fail = {APPLE: WebPushException("nf", response=_Resp(404))}
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls, fail))
    assert len(calls) == 2
    assert [s.endpoint for s in push.list_subscriptions(db_session)] == [FCM]


def test_500_keeps_subscription_and_sends_others(db_session: Session) -> None:
    _subs(db_session, APPLE, FCM)
    calls: list[dict] = []
    fail = {APPLE: WebPushException("err", response=_Resp(500))}
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls, fail))
    assert [c["subscription_info"]["endpoint"] for c in calls] == [APPLE, FCM]
    assert len(push.list_subscriptions(db_session)) == 2


def test_dead_endpoint_deleted(db_session: Session) -> None:
    _subs(db_session, APPLE, FCM)
    calls: list[dict] = []
    fail = {APPLE: WebPushException("gone", response=_Resp(410))}
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls, fail))
    assert [c["subscription_info"]["endpoint"] for c in calls] == [APPLE, FCM]
    left = [s.endpoint for s in push.list_subscriptions(db_session)]
    assert left == [FCM]


def test_unreachable_keeps_subscription(db_session: Session) -> None:
    _subs(db_session, APPLE, FCM)
    calls: list[dict] = []
    fail = {APPLE: requests.Timeout("slow")}
    send_to_all(db_session, PushMessage("t", "b", "tag", "/u"), send=_recorder(calls, fail))
    assert len(calls) == 2
    assert len(push.list_subscriptions(db_session)) == 2


# --- notify_settled / stale loop -------------------------------------------


def _fake_webpush(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(push, "webpush", _recorder(calls))
    return calls


def test_stale_loop_notifies_failed(monkeypatch, db_session_visible: Session) -> None:
    import time

    calls = _fake_webpush(monkeypatch)
    _subs(db_session_visible, APPLE)
    row = Download(
        url="https://example.com/stale",
        title="Stale one",
        status="active",
        claimed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
    )
    db_session_visible.add(row)
    db_session_visible.commit()

    from app.main import WorkerPool

    pool = WorkerPool(stale_check_interval_seconds=0.05, stale_timeout_minutes=1)
    pool.start(1)
    try:
        for _ in range(100):
            if calls:
                break
            time.sleep(0.05)
    finally:
        pool.stop()
    assert len(calls) == 1
    assert json.loads(calls[0]["data"])["title"] == "Download failed"
