"""Unit tests for ``app.services.settings.resolve_runtime_settings``.

The runtime resolver converts the persisted string-valued settings table
into typed runtime values the worker can consume directly: ``int`` for
concurrency, ``Path`` for filesystem paths, and ``str | None`` for the
proxy URL. Persisted empty strings mean "unset" and fall back to the
environment-loaded defaults from ``app.config.settings``.
"""

from __future__ import annotations

from pathlib import Path

from app.services import settings as settings_service
from app.services.settings import resolve_runtime_settings, set_settings_batch


def test_resolve_runtime_settings_prefers_saved_download_dir(db_session, tmp_path: Path) -> None:
    saved_dir = tmp_path / "saved-downloads"
    set_settings_batch(db_session, {"downloads_dir": str(saved_dir)})

    resolved = resolve_runtime_settings(db_session)

    assert resolved.downloads_dir == saved_dir


def test_resolve_runtime_settings_turns_blank_values_into_runtime_defaults(db_session) -> None:
    resolved = resolve_runtime_settings(db_session)

    assert resolved.max_concurrent == 1
    assert resolved.proxy_url is None
    assert resolved.cookies_path is None


def test_resolve_runtime_settings_uses_saved_proxy_and_cookies(db_session, tmp_path: Path) -> None:
    cookies_path = tmp_path / "cookies.txt"
    set_settings_batch(
        db_session,
        {
            "proxy_url": "http://proxy.internal:8080",
            "cookies_path": str(cookies_path),
            "max_concurrent": "3",
        },
    )

    resolved = resolve_runtime_settings(db_session)

    assert resolved.max_concurrent == 3
    assert resolved.proxy_url == "http://proxy.internal:8080"
    assert resolved.cookies_path == cookies_path


def test_resolve_runtime_settings_falls_back_to_env_proxy_and_cookies(
    monkeypatch, db_session, tmp_path: Path
) -> None:
    env_cookies = tmp_path / "env-cookies.txt"
    monkeypatch.setattr(settings_service.app_settings, "proxy_url", "http://env-proxy:8080")
    monkeypatch.setattr(settings_service.app_settings, "cookies_path", env_cookies)

    resolved = resolve_runtime_settings(db_session)

    assert resolved.proxy_url == "http://env-proxy:8080"
    assert resolved.cookies_path == env_cookies
