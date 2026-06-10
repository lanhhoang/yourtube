"""Unit tests for ``app.services.settings``.

These tests run against a per-test SQLite session (``db_session`` fixture
in ``tests/conftest.py``) that is rolled back after the test, so each test
sees a clean state.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.settings import (
    get_all_settings,
    get_setting,
    reset_settings,
    set_setting,
    set_settings_batch,
)

# Catalog of settings managed by the service. ``reset_settings`` uses
# this to restore defaults.
DEFAULT_CATALOG: dict[str, str] = {
    "max_concurrent": "1",
    "proxy_url": "",
    "cookies_path": "",
    "downloads_dir": "",
}


def test_get_setting_returns_default_when_no_row(db_session: Session) -> None:
    """``get_setting`` returns the catalog default when no row exists."""
    assert get_setting(db_session, "max_concurrent") == "1"


def test_get_setting_returns_stored_value_after_set(db_session: Session) -> None:
    """Round-trip: a value set via ``set_setting`` is returned by ``get_setting``."""
    set_setting(db_session, "max_concurrent", "3")
    assert get_setting(db_session, "max_concurrent") == "3"


def test_get_all_settings_returns_catalog_defaults_when_empty(db_session: Session) -> None:
    """``get_all_settings`` returns all catalog keys with defaults when table is empty."""
    all_settings = get_all_settings(db_session)
    for key, default in DEFAULT_CATALOG.items():
        assert all_settings[key] == default


def test_set_setting_with_non_catalog_key_is_allowed(db_session: Session) -> None:
    """Non-catalog keys are stored verbatim (no validation, no default)."""
    set_setting(db_session, "future_feature", "anything")
    assert get_setting(db_session, "future_feature") == "anything"


@pytest.mark.parametrize("value", ["0", "6", "abc", "1.5", "-1"])
def test_max_concurrent_rejects_invalid_values(db_session: Session, value: str) -> None:
    """Invalid ``max_concurrent`` values raise ``ValueError``."""
    with pytest.raises(ValueError):
        set_setting(db_session, "max_concurrent", value)


@pytest.mark.parametrize("value", ["1", "2", "3", "4", "5"])
def test_max_concurrent_accepts_valid_values(db_session: Session, value: str) -> None:
    """Valid ``max_concurrent`` values are accepted and round-tripped."""
    set_setting(db_session, "max_concurrent", value)
    assert get_setting(db_session, "max_concurrent") == value


def test_set_settings_batch_updates_multiple_keys_atomically(db_session: Session) -> None:
    """``set_settings_batch`` updates every key in a single call."""
    set_settings_batch(db_session, {"max_concurrent": "2", "proxy_url": "http://proxy:8080"})
    assert get_setting(db_session, "max_concurrent") == "2"
    assert get_setting(db_session, "proxy_url") == "http://proxy:8080"


def test_set_settings_batch_validates_each_value(db_session: Session) -> None:
    """If any value in the batch is invalid, none are persisted."""
    with pytest.raises(ValueError):
        set_settings_batch(db_session, {"max_concurrent": "99", "proxy_url": "ok"})
    # After the failed batch, the previously-stored value (or default) is preserved.


def test_reset_settings_restores_catalog_defaults(db_session: Session) -> None:
    """``reset_settings`` writes all catalog keys back to their defaults."""
    set_setting(db_session, "max_concurrent", "4")
    set_setting(db_session, "proxy_url", "http://proxy:8080")
    reset_settings(db_session)
    all_settings = get_all_settings(db_session)
    for key, default in DEFAULT_CATALOG.items():
        assert all_settings[key] == default
