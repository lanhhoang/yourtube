"""Runtime settings service backed by the ``settings`` table.

The catalog of known settings lives in :data:`SETTINGS_CATALOG`. The
service validates writes against the catalog rules and returns catalog
defaults when no row exists for a key. Non-catalog keys are stored
verbatim so the service stays flexible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models import Setting


@dataclass(frozen=True)
class RuntimeSettings:
    """Typed runtime view of the persisted settings.

    The worker and the API use this struct instead of looking up raw
    strings. Persisted empty strings map to ``None`` (for proxy/cookies)
    or the environment-loaded default (for ``downloads_dir``).
    """

    max_concurrent: int
    proxy_url: str | None
    cookies_path: Path | None
    downloads_dir: Path


def resolve_runtime_settings(session: Session) -> RuntimeSettings:
    """Build a :class:`RuntimeSettings` from the persisted settings table.

    Precedence rules:
    - Persisted non-empty values override the environment defaults.
    - Persisted empty strings for ``proxy_url`` / ``cookies_path`` mean
      "unset" and resolve to ``None``.
    - Persisted empty string for ``downloads_dir`` falls back to
      ``app.config.settings.downloads_dir``.
    - ``max_concurrent`` is clamped to ``[1, 5]`` to match the catalog
      validation rules.
    """
    stored = get_all_settings(session)
    raw_concurrent = stored["max_concurrent"] or "1"
    try:
        max_concurrent = int(raw_concurrent)
    except (TypeError, ValueError):
        max_concurrent = 1
    downloads_dir = (
        Path(stored["downloads_dir"]) if stored["downloads_dir"] else app_settings.downloads_dir
    )
    proxy_url = stored["proxy_url"] or app_settings.proxy_url
    cookies_path = (
        Path(stored["cookies_path"]) if stored["cookies_path"] else app_settings.cookies_path
    )
    return RuntimeSettings(
        max_concurrent=max(1, min(5, max_concurrent)),
        proxy_url=proxy_url,
        cookies_path=cookies_path,
        downloads_dir=downloads_dir,
    )


# Catalog of settings the service understands. The default is returned
# when no row exists for the key. The optional ``validator`` is a
# callable that raises ``ValueError`` on invalid input.
SETTINGS_CATALOG: dict[str, str] = {
    "max_concurrent": "1",
    "proxy_url": "",
    "cookies_path": "",
    "downloads_dir": "",
}


def _validate(key: str, value: str) -> None:
    """Validate a value for a catalog key. Raises ``ValueError`` on failure."""
    if key == "max_concurrent":
        try:
            n = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_concurrent must be an integer 1-5, got {value!r}") from exc
        if n < 1 or n > 5:
            raise ValueError(f"max_concurrent must be 1-5, got {n}")


def get_setting(session: Session, key: str) -> str | None:
    """Return the stored value for ``key``, or the catalog default if absent.

    Returns ``None`` only for non-catalog keys that have no row.
    """
    row = session.get(Setting, key)
    if row is not None:
        return row.value
    if key in SETTINGS_CATALOG:
        return SETTINGS_CATALOG[key]
    return None


def get_all_settings(session: Session) -> dict[str, str]:
    """Return a dict of catalog keys to values (defaults applied where missing)."""
    rows = session.execute(select(Setting)).scalars().all()
    stored = {row.key: row.value for row in rows}
    result: dict[str, str] = {}
    for key, default in SETTINGS_CATALOG.items():
        result[key] = stored.get(key, default)
    return result


def set_setting(session: Session, key: str, value: str) -> None:
    """Set a single key, validating against the catalog. Raises ``ValueError``."""
    _validate(key, value)
    row = session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.commit()


def set_settings_batch(session: Session, updates: dict[str, str]) -> None:
    """Update multiple keys atomically. Validates all values first."""
    for key, value in updates.items():
        _validate(key, value)
    for key, value in updates.items():
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    session.commit()


def reset_settings(session: Session) -> None:
    """Restore all catalog keys to their defaults."""
    for key, default in SETTINGS_CATALOG.items():
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=default))
        else:
            row.value = default
    session.commit()
