"""API tests for push subscriptions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PushSubscription
from app.services import push


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    push._keys_cache.clear()


def _body(auth: str = "a1") -> dict:
    return {"endpoint": "https://push.example/abc?x=1", "keys": {"p256dh": "pk", "auth": auth}}


def test_key_is_stable(client: TestClient) -> None:
    a = client.get("/api/push/key")
    assert a.status_code == 200
    assert a.json() == client.get("/api/push/key").json()
    assert a.json()["public_key"]


def test_upsert_twice_one_row(client: TestClient, db_session_visible: Session) -> None:
    assert client.post("/api/push/subscriptions", json=_body("a1")).status_code == 204
    assert client.post("/api/push/subscriptions", json=_body("a2")).status_code == 204
    rows = db_session_visible.scalars(select(PushSubscription)).all()
    assert len(rows) == 1
    assert rows[0].endpoint == "https://push.example/abc?x=1"
    assert rows[0].auth == "a2"


def test_rejects_http_endpoint(client: TestClient) -> None:
    body = _body()
    body["endpoint"] = "http://push.example/abc"
    assert client.post("/api/push/subscriptions", json=body).status_code == 422


def test_rejects_empty_keys(client: TestClient) -> None:
    body = _body("")
    assert client.post("/api/push/subscriptions", json=body).status_code == 422


def test_delete(client: TestClient, db_session_visible: Session) -> None:
    client.post("/api/push/subscriptions", json=_body())
    r = client.request("DELETE", "/api/push/subscriptions", json={"endpoint": _body()["endpoint"]})
    assert r.status_code == 204
    db_session_visible.expire_all()
    assert db_session_visible.scalars(select(PushSubscription)).all() == []
    r = client.request("DELETE", "/api/push/subscriptions", json={"endpoint": "https://x/y"})
    assert r.status_code == 204
