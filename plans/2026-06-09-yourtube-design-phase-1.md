# Phase 1: Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a bootable FastAPI skeleton with SQLModel, Pydantic config, SQLite DB, and CI baseline. No business logic yet — just enough to prove the app starts and `/health` returns 200.

**Architecture:** FastAPI with lifespan that runs SQLModel migrations on startup. Single `/health` endpoint. CI runs ruff + ty + pytest. No services, no templates, no static files yet.

**Tech Stack:** Python 3.12, FastAPI, SQLModel (Pydantic + SQLAlchemy), Pydantic Settings, uv, ruff, ty, pytest

---

## File Structure (this phase)

```
yourtube/
├── pyproject.toml
├── uv.lock
├── .env.example
├── .github/workflows/ci.yml
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan + /health
│   ├── config.py            # Pydantic BaseSettings
│   ├── db.py                # SQLModel engine + schema migrator
│   ├── models.py            # Download, Setting, SchemaVersion
│   ├── routes/__init__.py
│   ├── services/__init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_health.py
```

---

### Task 1: Create pyproject.toml and package markers

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/routes/__init__.py`
- Create: `app/services/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "yourtube"
version = "0.1.0"
description = "Self-hosted YouTube video downloader"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlmodel>=0.0.22",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "yt-dlp>=2024.12.0",
    "curl-cffi>=0.7.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "ty>=0.11.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ty]
python-version = "3.12"
```

- [ ] **Step 2: Create package marker files**

All four are empty:
```python
# app/__init__.py
```
```python
# app/routes/__init__.py
```
```python
# app/services/__init__.py
```
```python
# tests/__init__.py
```

- [ ] **Step 3: Install deps and verify**

```bash
uv sync
uv run python -c "import fastapi; import sqlmodel; import yt_dlp; print('OK')"
```
Expected: `OK` printed with no errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock app/__init__.py app/routes/__init__.py app/services/__init__.py tests/__init__.py
git commit -m "chore: scaffold project with pyproject.toml and package markers"
```

---

### Task 2: Create Config

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Create config.py**

```python
"""Environment-based configuration via Pydantic BaseSettings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YT_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path.home() / ".local" / "share" / "yourtube"
    downloads_dir: Path = Path.home() / "Downloads"
    cookies_path: Path | None = None
    proxy_url: str | None = None
    log_level: str = "INFO"
    workers: int = 1


settings = Settings()
```

- [ ] **Step 2: Write a quick sanity test**

```python
# tests/test_config.py
from app.config import settings


def test_settings_loaded():
    assert settings.host == "127.0.0.1" or settings.host == "0.0.0.0"
    assert settings.log_level in ("INFO", "DEBUG", "WARNING")
```

- [ ] **Step 3: Run test**

```bash
uv run pytest tests/test_config.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "chore: add Pydantic settings configuration"
```

---

### Task 3: Create Database Layer

**Files:**
- Create: `app/db.py`

- [ ] **Step 1: Create app/db.py**

```python
"""SQLModel engine, session factory, and schema migrator."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _get_engine_url() -> str:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "yourtube.db"
    return f"sqlite:///{db_path}"


engine = create_engine(
    _get_engine_url(),
    echo=False,
    connect_args={"check_same_thread": False},
)


def get_session() -> Session:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session


SCHEMA_VERSION = 3


def run_migrations() -> None:
    """Create tables, set pragmas, record schema version."""
    SQLModel.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
        conn.commit()

    _record_version()


def _record_version() -> None:
    from sqlmodel import select

    from app.models import SchemaVersion

    with Session(engine) as session:
        current = session.exec(
            select(SchemaVersion).order_by(SchemaVersion.version.desc())
        ).first()
        if current is None or current.version < SCHEMA_VERSION:
            session.add(SchemaVersion(version=SCHEMA_VERSION))
            session.commit()
```

- [ ] **Step 2: Write a test**

```python
# tests/test_db.py
from app.db import engine
from sqlmodel import SQLModel


def test_engine_created():
    assert engine is not None


def test_tables_created(db_engine):
    """Verify tables exist after create_all."""
    import sqlalchemy.inspection as insp
    inspector = insp.inspect(db_engine)
    tables = inspector.get_table_names()
    assert "downloads" in tables
    assert "settings" in tables
    assert "schema_version" in tables
```

- [ ] **Step 3: Verify the conftest works**

The tests above use `db_engine` fixture that creates an in-memory SQLite. We need that fixture in conftest. Since the full conftest with all fixtures is used across all phases, let's put the minimal version now:

- [ ] **Step 4: Create tests/conftest.py**

```python
# tests/conftest.py
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_db.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/db.py tests/test_db.py tests/conftest.py
git commit -m "chore: add SQLModel database layer with migrations"
```

---

### Task 4: Create SQLModel Models

**Files:**
- Create: `app/models.py`

- [ ] **Step 1: Create app/models.py**

```python
"""SQLModel definitions: DB tables (table=True) + request/response schemas (table=False)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


# ── Database tables ───────────────────────────────────────────


class Download(SQLModel, table=True):
    __tablename__ = "downloads"

    id: int | None = Field(default=None, primary_key=True)

    # Source
    url: str = Field(max_length=2048, nullable=False)

    # Metadata (populated by /api/info before enqueue)
    title: str | None = Field(default=None, max_length=1024)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    uploader: str | None = Field(default=None, max_length=512)
    duration: int | None = None

    # Format selection — user-picked streams
    video_format_id: str | None = Field(default=None, max_length=32)
    audio_format_id: str | None = Field(default=None, max_length=32)
    format_choice: str = Field(default="video", max_length=16)
    subtitles_enabled: bool = Field(default=False)
    subtitle_languages: str | None = None

    # Queue state
    status: str = Field(default="queued", max_length=32, index=True)
    progress: float = Field(default=0.0)
    error: str | None = None
    cancel_requested: bool = Field(default=False)

    # File output (populated on completion)
    file_path: str | None = Field(default=None, max_length=2048)
    file_size: int | None = None
    media_format: str | None = Field(default=None, max_length=16)
    resolution_height: int | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True, max_length=128)
    value: str = Field(nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SchemaVersion(SQLModel, table=True):
    __tablename__ = "schema_version"

    version: int = Field(primary_key=True)
    applied_at: datetime = Field(default_factory=datetime.utcnow)


# ── Request schemas (Pydantic only, no table) ───────────────


class InfoRequest(SQLModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1)


class DownloadCreate(SQLModel):
    """Request body for POST /api/downloads."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    title: str | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None
    duration: int | None = None

    # Explicit video + audio stream IDs
    video_format_id: str | None = None
    audio_format_id: str | None = None
    format_choice: str = Field(default="video")
    subtitles_enabled: bool = False
    subtitle_languages: list[str] = Field(default_factory=list)


# ── Response schemas ──────────────────────────────────────────


class FormatInfo(SQLModel):
    """One yt-dlp format entry, returned by /api/info."""

    id: str
    ext: str
    kind: str  # "video" | "audio" | "combined"
    height: int | None = None
    width: int | None = None
    vcodec: str | None = None
    acodec: str | None = None
    tbr: float | None = None
    abr: float | None = None
    filesize: int | None = None
    filesize_approx: int | None = None


class InfoResponse(SQLModel):
    title: str | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None
    duration: int | None = None
    formats: list[FormatInfo] = Field(default_factory=list)


class DownloadResponse(SQLModel):
    id: int
    url: str
    title: str | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None
    duration: int | None = None
    status: str
    progress: float = 0.0
    error: str | None = None
    file_size: int | None = None
    media_format: str | None = None
    resolution_height: int | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class ErrorResponse(SQLModel):
    error: str
    code: str
    details: dict[str, Any] | None = None


class CookiesValidateResponse(SQLModel):
    valid: bool
    message: str
```

- [ ] **Step 2: Write a model test**

```python
# tests/test_models.py
from datetime import datetime
from app.models import Download, Setting, SchemaVersion


def test_download_defaults():
    d = Download(url="https://youtube.com/watch?v=test")
    assert d.status == "queued"
    assert d.progress == 0.0
    assert d.cancel_requested is False
    assert d.format_choice == "video"
    assert d.id is None


def test_download_with_format_ids():
    d = Download(url="https://youtube.com/watch?v=test", video_format_id="137", audio_format_id="140")
    assert d.video_format_id == "137"
    assert d.audio_format_id == "140"


def test_setting_create():
    s = Setting(key="max_concurrent", value="2")
    assert s.key == "max_concurrent"
    assert s.value == "2"


def test_schema_version():
    sv = SchemaVersion(version=1)
    assert sv.version == 1
    assert sv.applied_at is not None
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add SQLModel data models (Download, Setting, SchemaVersion, schemas)"
```

---

### Task 5: Create Minimal Bootable App

**Files:**
- Create: `app/main.py`
- Create: `app/routes/pages.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Create app/main.py (minimal — just lifespan + health)**

```python
"""Minimal FastAPI application entry point — bootable skeleton with migrations."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="YourTube", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Create test**

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Verify it boots**

```bash
uv run pytest tests/test_health.py -v
```
Expected: PASS

- [ ] **Step 4: Start server and test manually**

```bash
uv run uvicorn app.main:app --port 8000 &
sleep 1
curl http://localhost:8000/health
# kill %1
```
Expected: `{"status":"ok"}`

- [ ] **Step 5: Create .env.example**

```env
YT_HOST=127.0.0.1
YT_PORT=8000
YT_DATA_DIR=~/.local/share/yourtube
YT_DOWNLOADS_DIR=~/Downloads
YT_COOKIES_PATH=
YT_PROXY_URL=
YT_LOG_LEVEL=INFO
YT_WORKERS=1
```

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_health.py .env.example
git commit -m "feat: add minimal FastAPI app with /health endpoint and migrations"
```

---

### Task 6: Create CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    name: Lint and test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Sync dependencies
        run: uv sync --all-extras

      - name: Lint with ruff
        run: uv run ruff check .

      - name: Type-check with ty
        run: uv run ty check app

      - name: Run tests with coverage
        run: uv run pytest --cov=app --cov-fail-under=80
```

- [ ] **Step 2: Verify CI commands pass locally**

```bash
uv run ruff check .
uv run ty check app
uv run pytest --cov=app --cov-fail-under=80
```
Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add CI workflow (ruff + ty + pytest with coverage)"
```

---

## Self-Review (Phase 1)

**Spec coverage:**
- ✓ pyproject.toml with uv, ruff, ty, pytest
- ✓ SQLModel engine + session + migrations
- ✓ All data models (Download, Setting, SchemaVersion) and request/response schemas
- ✓ Minimal FastAPI app that boots and serves /health
- ✓ CI workflow

**Placeholder scan:** No TBD, TODO, or incomplete sections.

**Type consistency:** All imports match between files. `models.py` defines types used by `db.py` migration code.

---

## End of Phase 1

Deliverable: `uv run uvicorn app.main:app` boots on port 8000, `/health` returns `{"status":"ok"}`. CI passes. No business logic yet.
