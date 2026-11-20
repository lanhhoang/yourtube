"""VAPID keys and Web Push subscription storage."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db import SessionLocal
from app.models import Download, PushSubscription
from app.services.queue import BatchSummary, claim_batch_summary

logger = logging.getLogger(__name__)

_VAPID_FILE = "vapid.json"
_lock = threading.Lock()
_keys_cache: dict[tuple[str, str | None, str | None], VapidKeys] = {}


@dataclass(frozen=True)
class VapidKeys:
    """Base64url (no padding) VAPID key pair."""

    private_key: str
    public_key: str


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _generate() -> VapidKeys:
    v = Vapid01()
    v.generate_keys()
    private = _b64url(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    public = _b64url(
        v.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    return VapidKeys(private_key=private, public_key=public)


def _write_private(path: Path, keys: VapidKeys) -> None:
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"private_key": keys.private_key, "public_key": keys.public_key}, fh)
    os.replace(tmp, path)


def load_vapid_keys(data_dir: Path, s: Settings) -> VapidKeys:
    """Return the VAPID keys: env overrides, else ``vapid.json``, else generate."""
    cache_key = (str(data_dir), s.vapid_private_key, s.vapid_public_key)
    with _lock:
        cached = _keys_cache.get(cache_key)
        if cached is not None:
            return cached
        if s.vapid_private_key and s.vapid_public_key:
            keys = VapidKeys(s.vapid_private_key, s.vapid_public_key)
        else:
            path = data_dir / _VAPID_FILE
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                keys = VapidKeys(data["private_key"], data["public_key"])
            else:
                data_dir.mkdir(parents=True, exist_ok=True)
                keys = _generate()
                _write_private(path, keys)
        _keys_cache[cache_key] = keys
        return keys


def upsert_subscription(
    session: Session, endpoint: str, p256dh: str, auth: str, user_agent: str | None
) -> None:
    row = session.scalars(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).first()
    if row is None:
        session.add(
            PushSubscription(endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=user_agent)
        )
    else:
        row.p256dh = p256dh
        row.auth = auth
        row.user_agent = user_agent
    session.commit()


def delete_subscription(session: Session, endpoint: str) -> bool:
    result = session.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint))
    session.commit()
    return bool(result.rowcount)


def list_subscriptions(session: Session) -> list[PushSubscription]:
    return list(session.scalars(select(PushSubscription).order_by(PushSubscription.id)))


_BODY_MAX = 200


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    tag: str
    url: str


def _cut(text: str) -> str:
    return text if len(text) <= _BODY_MAX else text[: _BODY_MAX - 1] + "\u2026"


def job_message(row: Download) -> PushMessage | None:
    title = row.title or row.url
    if row.status == "done":
        return PushMessage("Downloaded", _cut(title), f"job-{row.id}", f"/#/watch/{row.id}")
    if row.status == "error":
        return PushMessage(
            "Download failed",
            _cut(f"{title}: {row.error_message}"),
            f"job-{row.id}",
            "/#/queue",
        )
    return None


def batch_message(s: BatchSummary) -> PushMessage:
    parts = [
        f"{n} {label}"
        for n, label in ((s.done, "downloaded"), (s.failed, "failed"), (s.cancelled, "cancelled"))
        if n
    ]
    body = ", ".join(parts) or "0 downloaded"
    return PushMessage(s.name, body, f"batch-{s.batch_id}", "/#/queue")


def send_to_all(
    session: Session,
    message: PushMessage,
    *,
    send: Callable[..., Any] | None = None,
    timeout: float = 10,
) -> None:
    send = send or webpush
    keys = load_vapid_keys(settings.data_dir, settings)
    data = json.dumps(
        {"title": message.title, "body": message.body, "tag": message.tag, "url": message.url}
    )
    for sub in list_subscriptions(session):
        endpoint = sub.endpoint
        try:
            send(
                subscription_info={
                    "endpoint": endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=data,
                vapid_private_key=keys.private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=86400,
                timeout=timeout,
            )
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                delete_subscription(session, endpoint)
            else:
                logger.warning("push to %s failed: %s", urlsplit(endpoint).netloc, exc)
        except Exception:  # noqa: BLE001 - one bad endpoint must not stop the rest
            logger.warning("push to %s failed", urlsplit(endpoint).netloc, exc_info=True)


def notify_settled(job_id: int) -> None:
    """Push for a settled job, or for its batch once the batch settles. Never raises."""
    try:
        with SessionLocal() as session:
            row = session.get(Download, job_id)
            if row is None:
                return
            if row.batch_id is None:
                message = job_message(row)
            else:
                batch_id = row.batch_id
                session.rollback()
                summary = claim_batch_summary(session, batch_id)
                message = batch_message(summary) if summary else None
            if message is not None:
                send_to_all(session, message)
    except Exception:  # noqa: BLE001
        logger.exception("push notification failed for job %s", job_id)
