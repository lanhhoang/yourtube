"""VAPID keys and Web Push subscription storage."""

from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PushSubscription

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
