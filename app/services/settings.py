"""Runtime settings service backed by the ``settings`` table.

The catalog of known settings lives in :data:`SETTINGS_CATALOG`. The
service validates writes against the catalog rules and returns catalog
defaults when no row exists for a key. Non-catalog keys are stored
verbatim so the service stays flexible.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting

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
