"""Tests for VAPID key loading."""

from __future__ import annotations

import base64
import stat
import threading
from pathlib import Path

import pytest
from py_vapid import Vapid01

from app.config import Settings
from app.services import push


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    push._keys_cache.clear()


def _settings(private: str | None = None, public: str | None = None) -> Settings:
    return Settings(vapid_private_key=private, vapid_public_key=public)


def _b64d(v: str) -> bytes:
    return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))


def test_generates_file_once_with_mode_600(tmp_path: Path) -> None:
    s = _settings()
    a = push.load_vapid_keys(tmp_path, s)
    f = tmp_path / "vapid.json"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    push._keys_cache.clear()
    assert push.load_vapid_keys(tmp_path, s) == a


def test_key_formats(tmp_path: Path) -> None:
    k = push.load_vapid_keys(tmp_path, _settings())
    pub = _b64d(k.public_key)
    assert len(pub) == 65 and pub[0] == 0x04
    assert "=" not in k.private_key + k.public_key
    assert len(_b64d(k.private_key)) == 32
    Vapid01.from_string(k.private_key)


def test_env_overrides_skip_file(tmp_path: Path) -> None:
    s = _settings("priv", "pub")
    k = push.load_vapid_keys(tmp_path, s)
    assert (k.private_key, k.public_key) == ("priv", "pub")
    assert not (tmp_path / "vapid.json").exists()


def test_threads_get_same_keys(tmp_path: Path) -> None:
    s = _settings()
    out: list[push.VapidKeys] = []

    def run() -> None:
        out.append(push.load_vapid_keys(tmp_path, s))

    ts = [threading.Thread(target=run) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(out) == 8 and len(set(out)) == 1
