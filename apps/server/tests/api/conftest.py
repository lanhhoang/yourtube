"""Shared fixtures for API tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

INDEX = '<!doctype html><div id="app"></div>'
JS = "console.log('a');"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake built web app with a secret file next to (outside) ``dist``."""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX)
    (root / "assets" / "a.js").write_text(JS)
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(settings, "web_dist_dir", root)
    return root


@pytest.fixture()
def client_no_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "web_dist_dir", tmp_path / "missing")
    with TestClient(app) as c:
        yield c
