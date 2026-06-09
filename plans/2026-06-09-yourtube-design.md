# YourTube Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted YouTube video downloader web app having quick download flow with a rich format picker, persistent library with queue/progress/cancellation, and rich settings.

**Architecture:** FastAPI + htmx + SQLite (single table for queue + library) + yt-dlp Python library + curl_cffi. User picks a specific video stream and audio stream from a format table; backend downloads them separately via yt-dlp and muxes them into a single MP4 with ffmpeg. In-process worker pool polls SQLite jobs table for atomic claim.

**Tech Stack:**

- [Python 3.12](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://pydantic.dev/docs/validation/latest/get-started/) (via [SQLModel](https://sqlmodel.tiangolo.com/))
- [SQLModel](https://sqlmodel.tiangolo.com/) — combines Pydantic + SQLAlchemy
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [curl-cffi](https://github.com/yifeikong/curl_cffi)
- [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/)
- [htmx](https://htmx.org/)
- [uvicorn](https://www.uvicorn.org/)
- [ffmpeg](https://ffmpeg.org/) (system binary)

**Dev:**

- [uv](https://docs.astral.sh/uv/)
- [ruff](https://docs.astral.sh/ruff/)
- [ty](https://docs.astral.sh/ty/) (Astral's type checker)
- [pytest](https://docs.pytest.org/en/stable/)

---

## File Structure

```
yourtube/
├── pyproject.toml                  # Project metadata, deps, tool config
├── uv.lock                         # Locked deps (uv)
├── Dockerfile                      # Container build (python:3.12-slim + ffmpeg + uv)
├── docker-compose.yml              # Single service: app + volumes
├── .env.example                    # Sample env vars
├── .github/workflows/ci.yml        # CI: ruff + ty + pytest
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, lifespan, worker pool
│   ├── config.py                   # Pydantic BaseSettings
│   ├── db.py                       # SQLModel engine, session, schema migrator
│   ├── models.py                   # SQLModel: Download, Setting, SchemaVersion, request/response schemas
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py                # GET /, /queue, /library, /settings, /health
│   │   └── api.py                  # /api/info, /api/downloads/*, /api/settings/*
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── downloader.py           # yt-dlp wrapper: build_format_selector, run_download
│   │   ├── queue.py                # Worker pool, claim/release, cancellation, stale detection
│   │   ├── library.py              # File listing, search, sort, delete
│   │   ├── settings.py             # Settings CRUD, validation, key registry
│   │   └── error_mapper.py         # yt-dlp stderr → (user_message, code)
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── sidebar.html
│   │   │   └── format_toggle.html
│   │   ├── pages/
│   │   │   ├── home.html
│   │   │   ├── queue.html
│   │   │   ├── library.html
│   │   │   └── settings.html
│   │   └── partials/
│   │       ├── queue_rows.html
│   │       ├── queue_row.html
│   │       ├── library_rows.html
│   │       ├── library_row.html
│   │       ├── settings_form.html
│   │       └── toast.html
│   │
│   └── static/
│       └── css/
│           └── app.css
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── test_downloader_format.py       # build_format_selector tests
    │   ├── test_downloader_progress.py
    │   ├── test_queue_claim.py
    │   ├── test_queue_cancel.py
    │   ├── test_queue_stale.py
    │   ├── test_library.py
    │   ├── test_settings.py
    │   ├── test_cookies.py
    │   ├── test_friendly_errors.py
    │   ├── test_filename_template.py
    │   └── test_models.py
    └── integration/
        ├── test_api_info.py                # NEW: full format list response
        ├── test_api_downloads_create.py    # NEW: video_format_id + audio_format_id
        ├── test_api_downloads_active.py
        ├── test_api_downloads_library.py
        ├── test_api_downloads_cancel.py
        ├── test_api_downloads_delete.py
        ├── test_api_downloads_file.py
        ├── test_api_settings_get.py
        ├── test_api_settings_put.py
        ├── test_api_settings_reset.py
        ├── test_pages.py
        └── test_startup_recovery.py
```

---

## Task 1: Project Scaffold (SQLModel, no separate schemas.py)

**Files:**

- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/db.py`
- Create: `app/models.py` (SQLModel only — combines ORM + Pydantic)
- Create: `app/routes/__init__.py`
- Create: `app/services/__init__.py`
- Create: `.env.example`

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

All three are empty:

```python
# app/__init__.py
```

```python
# app/routes/__init__.py
```

```python
# app/services/__init__.py
```

- [ ] **Step 3: Create app/config.py**

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

- [ ] **Step 4: Create app/db.py**

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
    from app.models import SchemaVersion  # noqa: F401 — register tables

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

- [ ] **Step 5: Create app/models.py (SQLModel — DB models + request/response schemas)**

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

    # Format selection — user-picked streams (NEW: video+audio split)
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

    # NEW: explicit video + audio stream IDs
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


class SettingsResponse(SQLModel):
    settings: dict[str, str]


class CookiesValidateResponse(SQLModel):
    valid: bool
    message: str
```

- [ ] **Step 6: Create .env.example**

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

- [ ] **Step 7: Install deps and verify import**

Run:

```bash
uv sync
uv run python -c "from app.config import settings; from app.db import engine; from app.models import Download, FormatInfo, DownloadCreate; print('OK')"
```

Expected: `OK` printed with no errors.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: scaffold yourtube project (SQLModel, Pydantic, no separate schemas)"
```

---

## Task 2: Error Mapper Service

**Files:**

- Create: `app/services/error_mapper.py`
- Create: `tests/unit/test_friendly_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_friendly_errors.py
import pytest
from app.services.error_mapper import friendly_ytdlp_error


def test_private_video():
    msg, code = friendly_ytdlp_error("Sign in to confirm your age\nThis video is private")
    assert "cookies" in msg.lower()
    assert code == "VIDEO_PRIVATE"


def test_age_restricted():
    msg, code = friendly_ytdlp_error("confirm your age")
    assert "cookies" in msg.lower()
    assert code == "AGE_RESTRICTED"


def test_geo_blocked():
    msg, code = friendly_ytdlp_error("This video is not available in your country")
    assert "region" in msg.lower()
    assert code == "VIDEO_GEOBLOCKED"


def test_video_removed():
    msg, code = friendly_ytdlp_error("Video unavailable. This video has been removed by the uploader")
    assert "unavailable" in msg.lower() or "removed" in msg.lower()
    assert code == "VIDEO_REMOVED"


def test_http_403():
    msg, code = friendly_ytdlp_error("ERROR: HTTP Error 403: Forbidden")
    assert "access denied" in msg.lower()
    assert code == "INFO_FETCH_FAILED"


def test_timeout():
    msg, code = friendly_ytdlp_error("ERROR: timed out")
    assert "timed out" in msg.lower()
    assert code == "NETWORK_TIMEOUT"


def test_disk_full():
    msg, code = friendly_ytdlp_error("OSError: [Errno 28] No space left on device")
    assert "disk full" in msg.lower()
    assert code == "DISK_FULL"


def test_permission_denied():
    msg, code = friendly_ytdlp_error("Permission denied: '/downloads/test.mp4'")
    assert "permission denied" in msg.lower()
    assert code == "PERMISSION_DENIED"


def test_generic_fallback():
    msg, code = friendly_ytdlp_error("Some unknown yt-dlp error occurred")
    assert "unknown" in msg
    assert code == "INFO_FETCH_FAILED"


def test_long_error_truncated():
    long_err = "x" * 500
    msg, code = friendly_ytdlp_error(long_err)
    assert len(msg) <= 205
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_friendly_errors.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/error_mapper.py
from __future__ import annotations


def friendly_ytdlp_error(stderr: str) -> tuple[str, str]:
    """Map yt-dlp error output to (user_message, error_code)."""
    s = stderr.lower()

    if "private video" in s or "sign in" in s:
        return "This video is private. Add cookies in Settings.", "VIDEO_PRIVATE"
    if "age-restricted" in s or "confirm your age" in s:
        return "Age-restricted. Add cookies in Settings to download.", "AGE_RESTRICTED"
    if "not available in your country" in s or "geo" in s:
        return "Not available in your region.", "VIDEO_GEOBLOCKED"
    if "video unavailable" in s or "removed" in s or " 404" in s:
        return "Video unavailable or removed.", "VIDEO_REMOVED"
    if "http error 403" in s:
        return "Access denied. YouTube may be blocking this client.", "INFO_FETCH_FAILED"
    if "timed out" in s:
        return "Request timed out. Try again.", "NETWORK_TIMEOUT"
    if "no space" in s or "enospc" in s:
        return "Disk full. Free space and retry.", "DISK_FULL"
    if "permission denied" in s:
        return "Cannot write to downloads folder.", "PERMISSION_DENIED"

    last = stderr.strip().splitlines()[-1] if stderr.strip() else "Unknown error"
    truncated = (last[:200] + "\u2026") if len(last) > 200 else last
    return truncated, "INFO_FETCH_FAILED"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_friendly_errors.py -v`
Expected: PASS (10/10)

- [ ] **Step 5: Commit**

```bash
git add app/services/error_mapper.py tests/unit/test_friendly_errors.py
git commit -m "feat: add yt-dlp error mapping service"
```

---

## Task 3: Settings Service

**Files:**

- Create: `app/services/settings.py`
- Create: `tests/unit/test_settings.py`
- Create: `tests/conftest.py` (shared fixtures)

- [ ] **Step 1: Create tests/conftest.py**

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app


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


def _override_session(db_engine):
    def _gen():
        with Session(db_engine) as s:
            yield s

    return _gen


@pytest.fixture
def client(db_engine):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = _override_session(db_engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ytdlp(monkeypatch):
    from unittest.mock import MagicMock

    fake = MagicMock()
    fake.extract_info.return_value = SAMPLE_VIDEO_INFO
    fake.download.return_value = None
    monkeypatch.setattr("yt_dlp.YoutubeDL", lambda *a, **kw: fake)
    return fake


SAMPLE_VIDEO_INFO = {
    "id": "dQw4w9WgXcQ",
    "title": "Test Video",
    "uploader": "Test Channel",
    "duration": 213,
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "formats": [
        # video-only streams
        {"format_id": "137", "ext": "mp4",  "height": 1080, "width": 1920, "vcodec": "avc1.640028", "acodec": "none",  "tbr": 3000, "filesize_approx": 500_000_000},
        {"format_id": "248", "ext": "webm", "height": 1080, "width": 1920, "vcodec": "vp9",        "acodec": "none",  "tbr": 2200, "filesize_approx": 350_000_000},
        {"format_id": "22",  "ext": "mp4",  "height": 720,  "width": 1280, "vcodec": "avc1.64001F", "acodec": "aac",   "tbr": 1500, "filesize_approx": 200_000_000},
        # audio-only streams
        {"format_id": "140", "ext": "m4a",  "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "filesize_approx": 5_000_000},
        {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus",      "abr": 160, "filesize_approx": 6_500_000},
    ],
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_settings.py
import pytest
from app.services.settings import (
    DEFAULTS,
    get_setting,
    set_setting,
    get_all_settings,
    reset_settings,
    validate_cookies_path,
)


def test_defaults_returned_when_no_rows(db_session):
    all_s = get_all_settings(db_session)
    for k, v in DEFAULTS.items():
        assert all_s[k] == v, f"{k}: expected {v!r}, got {all_s[k]!r}"


def test_set_and_get(db_session):
    set_setting(db_session, "max_concurrent", "4")
    assert get_setting(db_session, "max_concurrent") == "4"


def test_set_overrides_default(db_session):
    set_setting(db_session, "default_quality", "1080")
    assert get_setting(db_session, "default_quality") == "1080"


def test_get_missing_key_returns_default(db_session):
    assert get_setting(db_session, "nonexistent") is None


def test_set_validates_max_concurrent_range(db_session):
    with pytest.raises(ValueError, match="max_concurrent must be between 1 and 8"):
        set_setting(db_session, "max_concurrent", "99")


def test_set_validates_default_format(db_session):
    with pytest.raises(ValueError, match="default_format must be 'video' or 'audio'"):
        set_setting(db_session, "default_format", "gif")


def test_set_validates_quality(db_session):
    with pytest.raises(ValueError, match="Invalid quality"):
        set_setting(db_session, "default_quality", "4k")


def test_reset_clears_all_rows(db_session):
    set_setting(db_session, "max_concurrent", "8")
    reset_settings(db_session)
    assert get_setting(db_session, "max_concurrent") == "2"


def test_validate_cookies_path_missing(tmp_path):
    p = tmp_path / "nonexistent.txt"
    valid, msg = validate_cookies_path(str(p))
    assert not valid
    assert "not found" in msg


def test_validate_cookies_path_valid(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\t*\tvalue\n")
    valid, msg = validate_cookies_path(str(p))
    assert valid
```

- [ ] **Step 3: Implement settings service**

```python
# app/services/settings.py
"""Settings CRUD, validation, defaults registry."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.models import Setting

DEFAULTS: dict[str, str] = {
    "downloads_dir": "",
    "max_concurrent": "2",
    "default_format": "video",
    "default_quality": "best",
    "filename_template": "%(title)s [%(id)s].%(ext)s",
    "subtitle_languages": '["en"]',
    "cookies_path": "",
    "proxy_url": "",
    "embed_thumbnail": "false",
    "embed_metadata": "true",
    "audio_bitrate": "192",
    "extra_ytdlp_args": "[]",
}


def get_all_settings(session: Session) -> dict[str, str]:
    rows = session.exec(select(Setting)).all()
    stored = {r.key: r.value for r in rows}
    return {**DEFAULTS, **stored}


def get_setting(session: Session, key: str) -> str | None:
    row = session.exec(select(Setting).where(Setting.key == key)).first()
    return row.value if row else DEFAULTS.get(key)


def set_setting(session: Session, key: str, value: str) -> None:
    _validate(key, value)
    row = session.exec(select(Setting).where(Setting.key == key)).first()
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


def set_settings_batch(session: Session, updates: dict[str, str]) -> None:
    for k, v in updates.items():
        _validate(k, v)
    for k, v in updates.items():
        set_setting(session, k, v)
    session.commit()


def reset_settings(session: Session) -> None:
    for row in session.exec(select(Setting)).all():
        session.delete(row)
    session.commit()


def validate_cookies_path(path: str) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"File not found: {path}"
    if not p.is_file():
        return False, "Path is not a file"
    try:
        text = p.read_text(encoding="utf-8")
        if not text.strip().startswith("# Netscape HTTP Cookie File"):
            return False, "File does not appear to be a Netscape-format cookies.txt"
        return True, "Valid cookies.txt"
    except Exception as e:
        return False, f"Cannot read file: {e}"


def _validate(key: str, value: str) -> None:
    if key == "max_concurrent":
        try:
            v = int(value)
            if not 1 <= v <= 8:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ValueError(f"max_concurrent must be between 1 and 8, got {value!r}") from e

    if key == "default_format" and value not in ("video", "audio"):
        raise ValueError(f"default_format must be 'video' or 'audio', got {value!r}")

    if key == "default_quality" and value not in ("best", "1080", "720", "480", "worst"):
        raise ValueError(f"Invalid quality: {value!r}")

    if key in ("subtitle_languages", "extra_ytdlp_args"):
        try:
            json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"{key} must be valid JSON: {e}") from e

    if key == "audio_bitrate":
        try:
            v = int(value)
            if not 64 <= v <= 320:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ValueError(f"audio_bitrate must be 64-320, got {value!r}") from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: PASS (10/10)

- [ ] **Step 5: Commit**

```bash
git add app/services/settings.py tests/unit/test_settings.py tests/conftest.py
git commit -m "feat: add settings service with validation"
```

---

## Task 4: Downloader Service (NEW: video+audio split, mux to MP4)

**Files:**

- Create: `app/services/downloader.py`
- Create: `tests/unit/test_downloader_format.py`
- Create: `tests/unit/test_downloader_progress.py`
- Create: `tests/unit/test_filename_template.py`

- [ ] **Step 1: Write the format selector tests**

```python
# tests/unit/test_downloader_format.py
import pytest
from app.services.downloader import (
    build_format_selector,
    classify_format,
    KIND_VIDEO,
    KIND_AUDIO,
    KIND_COMBINED,
)


def test_video_plus_audio_returns_combined_selector():
    fmt = build_format_selector(video_id="137", audio_id="140")
    assert fmt == "137+140"


def test_video_only_returns_video_selector():
    fmt = build_format_selector(video_id="137", audio_id=None)
    assert fmt == "137/b"


def test_audio_only_returns_audio_selector():
    fmt = build_format_selector(video_id=None, audio_id="140")
    assert fmt == "140/b"


def test_neither_raises():
    with pytest.raises(ValueError, match="at least one"):
        build_format_selector(video_id=None, audio_id=None)


def test_classify_video_only():
    kind = classify_format({"vcodec": "h264", "acodec": "none"})
    assert kind == KIND_VIDEO


def test_classify_audio_only():
    kind = classify_format({"vcodec": "none", "acodec": "aac"})
    assert kind == KIND_AUDIO


def test_classify_combined():
    kind = classify_format({"vcodec": "h264", "acodec": "aac"})
    assert kind == KIND_COMBINED


def test_classify_missing_codecs():
    kind = classify_format({})
    assert kind == KIND_COMBINED
```

- [ ] **Step 2: Write the progress hook tests**

```python
# tests/unit/test_downloader_progress.py
import pytest
from app.services.downloader import YtdlpProgress


def test_progress_stores_percent():
    p = YtdlpProgress()
    p({"status": "downloading", "_percent_str": "\x1b[0;32m45.5%\x1b[0m"})
    assert p.percent == 45.5


def test_progress_ignores_non_downloading():
    p = YtdlpProgress()
    p({"status": "finished"})
    assert p.percent == 0.0


def test_progress_empty_percent():
    p = YtdlpProgress()
    p({"status": "downloading"})
    assert p.percent == 0.0


def test_progress_malformed_percent():
    p = YtdlpProgress()
    p({"status": "downloading", "_percent_str": "abc%"})
    assert p.percent == 0.0


def test_progress_stores_filename():
    p = YtdlpProgress()
    p({"status": "finished", "filename": "/downloads/test.mp4"})
    assert p.filename == "/downloads/test.mp4"


def test_cancel_flag_raises():
    p = YtdlpProgress()
    p.cancel = True
    with pytest.raises(p.Cancelled):
        p({"status": "downloading", "_percent_str": "10%"})
```

- [ ] **Step 3: Write the filename template tests**

```python
# tests/unit/test_filename_template.py
import pytest
from app.services.downloader import sanitize_filename


def test_simple_title():
    assert sanitize_filename("Hello World") == "Hello World"


def test_strips_path_separators():
    assert "/" not in sanitize_filename("A/B Video")
    assert "\\" not in sanitize_filename("A\\B Video")


def test_strips_windows_invalid_chars():
    invalid = '<>:"|?*'
    result = sanitize_filename(f"Bad{invalid}Chars")
    for c in invalid:
        assert c not in result


def test_truncates_long():
    long_title = "a" * 300
    result = sanitize_filename(long_title)
    assert len(result) <= 100


def test_empty_fallback():
    assert sanitize_filename("") == "video"
```

- [ ] **Step 4: Implement the downloader service (with separate video+audio + mux)**

```python
# app/services/downloader.py
"""yt-dlp wrapper: format selector, progress hook, separate video+audio download + mux to MP4."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yt_dlp

KIND_VIDEO = "video"
KIND_AUDIO = "audio"
KIND_COMBINED = "combined"


def classify_format(fmt: dict) -> str:
    """Classify a yt-dlp format entry as video-only, audio-only, or combined."""
    vcodec = fmt.get("vcodec", "none")
    acodec = fmt.get("acodec", "none")
    if vcodec and vcodec != "none" and (not acodec or acodec == "none"):
        return KIND_VIDEO
    if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
        return KIND_AUDIO
    return KIND_COMBINED


def build_format_selector(video_id: str | None, audio_id: str | None) -> str:
    """Build a yt-dlp -f selector string.

    Examples:
      - video + audio:  "137+140"   (downloads both streams, yt-dlp muxes)
      - video only:     "137/b"
      - audio only:     "140/b"
    """
    if video_id and audio_id:
        return f"{video_id}+{audio_id}"
    if video_id:
        return f"{video_id}/b"
    if audio_id:
        return f"{audio_id}/b"
    raise ValueError("build_format_selector requires at least one of video_id, audio_id")


class YtdlpProgress:
    """Tracks yt-dlp download progress via the Python callback hook."""

    class Cancelled(Exception):
        pass

    def __init__(self) -> None:
        self.percent: float = 0.0
        self.filename: str | None = None
        self.cancel: bool = False

    def __call__(self, d: dict[str, Any]) -> None:
        if self.cancel:
            raise self.Cancelled("Download cancelled by user")

        if d.get("status") == "downloading":
            raw = d.get("_percent_str", "")
            if raw:
                cleaned = re.sub(r"\x1b[^m]*m", "", raw).strip().rstrip("%")
                try:
                    self.percent = float(cleaned)
                except (ValueError, TypeError):
                    self.percent = 0.0

        elif d.get("status") == "finished":
            self.filename = d.get("filename")
            self.percent = 100.0


def sanitize_filename(title: str) -> str:
    """Remove characters unsafe for file systems, truncate to 100 chars."""
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = title.strip()
    if not title:
        return "video"
    return title[:100]


def extract_info(url: str) -> dict[str, Any]:
    """Fetch video metadata from YouTube (no download)."""
    ydl_opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def run_download(
    url: str,
    video_format_id: str | None,
    audio_format_id: str | None,
    output_template: str,
    output_dir: str,
    audio_bitrate: str = "192",
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hook: YtdlpProgress | None = None,
) -> str | None:
    """Download the chosen video+audio streams and mux into a single MP4.

    When the format selector is "video_id+audio_id", yt-dlp downloads the two
    streams to temp files, then runs ffmpeg to merge them into the final MP4
    (because merge_output_format="mp4" is set).
    """
    format_selector = build_format_selector(video_format_id, audio_format_id)

    ydl_opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": str(Path(output_dir) / output_template),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",  # force mux to MP4 container
        "writethumbnail": False,
        "embedsubs": subtitles,
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    # Audio-only → extract to mp3
    if video_format_id is None and audio_format_id is not None:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_bitrate,
            }
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return progress_hook.filename if progress_hook else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py tests/unit/test_filename_template.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py tests/unit/test_filename_template.py
git commit -m "feat: add downloader service (video+audio split, mux to MP4, progress hook)"
```

---

## Task 5: Queue Service (with SQLModel + new columns)

**Files:**

- Create: `app/services/queue.py`
- Create: `tests/unit/test_queue_claim.py`
- Create: `tests/unit/test_queue_cancel.py`
- Create: `tests/unit/test_queue_stale.py`

- [ ] **Step 1: Write the queue claim tests**

```python
# tests/unit/test_queue_claim.py
import pytest
from app.models import Download
from app.services.queue import claim_next, release_job, get_active_jobs


def test_claim_returns_queued_job(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="queued",
        video_format_id="137",
        audio_format_id="140",
    )
    db_session.add(d)
    db_session.commit()

    job = claim_next(db_session)
    assert job is not None
    assert job.status == "active"
    assert job.started_at is not None


def test_claim_skips_non_queued(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done")
    db_session.add(d)
    db_session.commit()

    job = claim_next(db_session)
    assert job is None


def test_claim_returns_oldest_first(db_session):
    for i in range(3):
        db_session.add(Download(url=f"https://youtube.com/watch?v={i}", status="queued"))
    db_session.commit()

    job1 = claim_next(db_session)
    job2 = claim_next(db_session)
    job3 = claim_next(db_session)

    assert {job1.id, job2.id, job3.id} == {1, 2, 3}


def test_claim_atomic_no_double_claim(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="queued")
    db_session.add(d)
    db_session.commit()

    job1 = claim_next(db_session)
    job2 = claim_next(db_session)

    assert job1 is not None
    assert job2 is None


def test_release_marks_done(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="active")
    db_session.add(d)
    db_session.commit()

    release_job(db_session, d.id, status="done", file_path="/downloads/test.mp4", file_size=12345)
    db_session.refresh(d)
    assert d.status == "done"
    assert d.file_path == "/downloads/test.mp4"
    assert d.file_size == 12345
    assert d.completed_at is not None


def test_get_active_jobs(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="queued"))
    db_session.add(Download(url="https://youtube.com/2", status="active"))
    db_session.add(Download(url="https://youtube.com/3", status="done"))
    db_session.commit()

    active = get_active_jobs(db_session)
    assert len(active) == 2
```

- [ ] **Step 2: Write the cancellation tests**

```python
# tests/unit/test_queue_cancel.py
import pytest
from app.models import Download
from app.services.queue import cancel_job, request_cancel


def test_cancel_queued_job_immediate(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="queued")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    db_session.refresh(d)
    assert result is True
    assert d.status == "cancelled"


def test_cancel_active_job_sets_flag(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="active")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    db_session.refresh(d)
    assert result is True
    assert d.cancel_requested is True
    assert d.status == "active"


def test_cancel_done_job_unchanged(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done")
    db_session.add(d)
    db_session.commit()

    result = cancel_job(db_session, d.id)
    assert result is False


def test_cancel_nonexistent_job(db_session):
    result = cancel_job(db_session, 999)
    assert result is False
```

- [ ] **Step 3: Write the stale detection tests**

```python
# tests/unit/test_queue_stale.py
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from app.models import Download
from app.services.queue import detect_stale_jobs


@freeze_time("2026-06-09 12:00:00")
def test_stale_older_than_10min(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="active",
        updated_at=datetime(2026, 6, 9, 11, 45, 0),
    )
    db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 1


@freeze_time("2026-06-09 12:00:00")
def test_not_stale_within_timeout(db_session):
    d = Download(
        url="https://youtube.com/watch?v=test",
        status="active",
        updated_at=datetime(2026, 6, 9, 11, 55, 0),
    )
    db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 0


@freeze_time("2026-06-09 12:00:00")
def test_stale_ignores_non_active(db_session):
    for status in ("queued", "done", "error", "cancelled"):
        d = Download(
            url="https://youtube.com/watch?v=test",
            status=status,
            updated_at=datetime(2026, 6, 8, 12, 0, 0),
        )
        db_session.add(d)
    db_session.commit()

    count = detect_stale_jobs(db_session, timeout_minutes=10)
    assert count == 0
```

- [ ] **Step 4: Implement the queue service**

```python
# app/services/queue.py
"""SQLite-backed download queue: worker claim, cancellation, staleness, requeue on startup."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import Download


def claim_next(session: Session) -> Download | None:
    """Atomically claim the oldest queued job. Returns the claimed Download or None."""
    rows = session.exec(
        select(Download)
        .where(Download.status == "queued", Download.cancel_requested == False)  # noqa: E712
        .order_by(Download.id.asc())
        .limit(1)
    ).all()
    if not rows:
        return None
    job = rows[0]
    job.status = "active"
    job.started_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def release_job(
    session: Session,
    job_id: int,
    status: str,
    file_path: str | None = None,
    file_size: int | None = None,
    media_format: str | None = None,
    resolution_height: int | None = None,
    error: str | None = None,
) -> None:
    """Mark a job as done/error/cancelled and record output metadata."""
    job = session.get(Download, job_id)
    if not job:
        return
    job.status = status
    job.updated_at = datetime.utcnow()
    if status == "done":
        job.completed_at = datetime.utcnow()
        job.file_path = file_path
        job.file_size = file_size
        job.media_format = media_format
        job.resolution_height = resolution_height
        job.progress = 100.0
    elif status == "error":
        job.error = error
    session.add(job)
    session.commit()


def get_active_jobs(session: Session) -> list[Download]:
    return list(
        session.exec(
            select(Download)
            .where(Download.status.in_(["queued", "fetching_info", "active"]))
            .order_by(Download.created_at.asc())
        ).all()
    )


def cancel_job(session: Session, job_id: int) -> bool:
    """Cancel a job. Returns True if cancellation initiated, False if already terminal."""
    job = session.get(Download, job_id)
    if not job:
        return False
    if job.status in ("done", "error", "cancelled"):
        return False
    if job.status == "queued":
        job.status = "cancelled"
    else:
        job.cancel_requested = True
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    return True


def request_cancel(session: Session, job_id: int) -> bool:
    """Set cancel_requested flag for active jobs."""
    job = session.get(Download, job_id)
    if not job or job.status == "done":
        return False
    job.cancel_requested = True
    session.add(job)
    session.commit()
    return True


def detect_stale_jobs(session: Session, timeout_minutes: int = 10) -> int:
    """Mark jobs stuck in 'active' for too long as 'error'."""
    threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    stale = list(
        session.exec(
            select(Download).where(
                Download.status == "active",
                Download.updated_at < threshold,
            )
        ).all()
    )
    for job in stale:
        job.status = "error"
        job.error = "Download stalled (no progress for 10+ min)"
        job.updated_at = datetime.utcnow()
        session.add(job)
    session.commit()
    return len(stale)


def requeue_active_on_startup(session: Session) -> int:
    """Re-queue any jobs left active from a previous (crashed) run."""
    stuck = list(
        session.exec(select(Download).where(Download.status == "active")).all()
    )
    for job in stuck:
        job.status = "queued"
        job.error = "Re-queued after server restart"
        job.updated_at = datetime.utcnow()
        session.add(job)
    session.commit()
    return len(stuck)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add app/services/queue.py tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py
git commit -m "feat: add queue service (claim, release, cancel, stale detection, requeue)"
```

---

## Task 6: Library Service

**Files:**

- Create: `app/services/library.py`
- Create: `tests/unit/test_library.py`

- [ ] **Step 1: Write the library tests**

```python
# tests/unit/test_library.py
import pytest
from datetime import datetime
from pathlib import Path
from app.models import Download
from app.services.library import (
    get_library,
    search_library,
    delete_from_library,
    get_file_path,
    format_size,
)


def test_get_library_returns_done_only(db_session):
    for i in range(3):
        db_session.add(Download(
            url=f"https://youtube.com/watch?v={i}",
            status="done" if i < 2 else "error",
            title=f"Video {i}",
        ))
    db_session.commit()

    items = get_library(db_session)
    assert len(items) == 2


def test_get_library_newest_first(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Old", created_at=datetime(2024, 1, 1)))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="New", created_at=datetime(2025, 1, 1)))
    db_session.commit()

    items = get_library(db_session)
    assert items[0].title == "New"


def test_search_library_filters_by_title(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Rick Astley Never Gonna"))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="Something Else"))
    db_session.commit()

    items = search_library(db_session, "rick")
    assert len(items) == 1
    assert "Rick" in items[0].title


def test_search_library_filters_by_uploader(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="done", title="Video", uploader="ChannelName"))
    db_session.add(Download(url="https://youtube.com/2", status="done", title="Other", uploader="OtherChannel"))
    db_session.commit()

    items = search_library(db_session, "channel")
    assert len(items) == 1


def test_delete_removes_from_library(db_session, tmp_path):
    fp = tmp_path / "test.mp4"
    fp.write_text("fake video content")

    d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp))
    db_session.add(d)
    db_session.commit()
    job_id = d.id

    success, msg = delete_from_library(db_session, job_id)
    assert success
    assert not fp.exists()


def test_delete_missing_file_ok(db_session):
    d = Download(url="https://youtube.com/watch?v=test", status="done", file_path="/nonexistent/test.mp4")
    db_session.add(d)
    db_session.commit()

    success, _ = delete_from_library(db_session, d.id)
    assert success


def test_format_size():
    assert format_size(None) == "—"
    assert format_size(500) == "500.0 B"
    assert format_size(1500) == "1.5 KB"
    assert format_size(1_500_000) == "1.4 MB"
    assert format_size(1_500_000_000) == "1.4 GB"
```

- [ ] **Step 2: Implement the library service**

```python
# app/services/library.py
"""File library management: list, search, sort, delete."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import Download


def get_library(session: Session) -> list[Download]:
    """Return all terminal downloads (done, error, cancelled), newest first."""
    return list(
        session.exec(
            select(Download)
            .where(Download.status.in_(["done", "error", "cancelled"]))
            .order_by(Download.created_at.desc())
        ).all()
    )


def search_library(
    session: Session,
    q: str = "",
    sort_by: str = "date",
) -> list[Download]:
    """Search library by title/uploader/url, then sort."""
    stmt = select(Download).where(
        Download.status.in_(["done", "error", "cancelled"])
    )

    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Download.title.ilike(term),
                Download.uploader.ilike(term),
                Download.url.ilike(term),
            )
        )

    if sort_by == "name":
        stmt = stmt.order_by(Download.title.asc())
    elif sort_by == "size":
        stmt = stmt.order_by(Download.file_size.desc().nullslast())
    else:
        stmt = stmt.order_by(Download.created_at.desc())

    return list(session.exec(stmt).all())


def delete_from_library(session: Session, job_id: int) -> tuple[bool, str]:
    """Delete a download row and remove file from disk."""
    job = session.get(Download, job_id)
    if not job:
        return False, "Job not found"

    if job.file_path:
        try:
            Path(job.file_path).unlink(missing_ok=True)
        except OSError:
            pass

    session.delete(job)
    session.commit()
    return True, "Deleted"


def get_file_path(job: Download) -> Path | None:
    if not job.file_path:
        return None
    p = Path(job.file_path)
    return p if p.exists() else None


def format_size(size: int | None) -> str:
    if size is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} TB"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_library.py -v`
Expected: PASS (all)

- [ ] **Step 4: Commit**

```bash
git add app/services/library.py tests/unit/test_library.py
git commit -m "feat: add library service (list, search, delete, file path helpers)"
```

---

## Task 7: App Main + Pages Routes

**Files:**

- Create: `app/main.py`
- Create: `app/routes/pages.py`
- Create: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the pages integration tests**

```python
# tests/integration/test_pages.py
def test_home_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_queue_page(client):
    r = client.get("/queue")
    assert r.status_code == 200


def test_library_page(client):
    r = client.get("/library")
    assert r.status_code == 200


def test_settings_page(client):
    r = client.get("/settings")
    assert r.status_code == 200


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

- [ ] **Step 2: Implement app/main.py**

```python
"""FastAPI application entry point with lifespan and worker pool bootstrap."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import settings
from app.db import engine, run_migrations
from app.routes import pages, api

logger = logging.getLogger("yourtube.app")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ── Worker pool (started in lifespan) ──────────────────────────


class WorkerPool:
    """Manages N daemon threads that poll the downloads table for work."""

    def __init__(self) -> None:
        self.max_workers: int = 2
        self._threads: list[threading.Thread] = []
        self._stop: threading.Event = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        t = threading.Thread(target=self._stale_loop, name="stale-checker", daemon=True)
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def _worker_loop(self) -> None:
        from app.services.queue import claim_next, release_job

        while not self._stop.is_set():
            try:
                with Session(engine) as session:
                    job = claim_next(session)
                if job is None:
                    self._stop.wait(2)
                    continue
                self._run_job(job)
            except Exception:
                logger.exception("Worker error")
                self._stop.wait(2)

    def _run_job(self, job) -> None:
        from app.services.downloader import YtdlpProgress, run_download
        from app.services.queue import release_job
        from app.services.settings import get_setting
        from app.services.error_mapper import friendly_ytdlp_error

        progress = YtdlpProgress()
        try:
            with Session(engine) as session:
                output_dir = get_setting(session, "downloads_dir") or str(settings.downloads_dir)
                output_template = get_setting(session, "filename_template")
                audio_bitrate = get_setting(session, "audio_bitrate")
                proxy = get_setting(session, "proxy_url") or None
                cookies = get_setting(session, "cookies_path") or None
                subtitles = get_setting(session, "embed_metadata") == "true"

            final = run_download(
                url=job.url,
                video_format_id=job.video_format_id,
                audio_format_id=job.audio_format_id,
                output_template=output_template,
                output_dir=output_dir,
                audio_bitrate=audio_bitrate,
                proxy=proxy,
                cookies_file=cookies,
                subtitles=subtitles,
                progress_hook=progress,
            )

            with Session(engine) as session:
                release_job(
                    session,
                    job.id,
                    status="done",
                    file_path=final,
                    file_size=Path(final).stat().st_size if final and Path(final).exists() else None,
                    media_format="mp4" if final else None,
                )
        except YtdlpProgress.Cancelled:
            with Session(engine) as session:
                release_job(session, job.id, status="cancelled")
        except Exception as e:
            msg, _ = friendly_ytdlp_error(str(e))
            with Session(engine) as session:
                release_job(session, job.id, status="error", error=msg)

    def _stale_loop(self) -> None:
        from app.services.queue import detect_stale_jobs

        while not self._stop.is_set():
            self._stop.wait(60)
            try:
                with Session(engine) as session:
                    count = detect_stale_jobs(session)
                if count:
                    logger.warning("Marked %d stale jobs as errored", count)
            except Exception:
                logger.exception("Stale detection error")


pool = WorkerPool()


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    from app.services.queue import requeue_active_on_startup
    from app.services.settings import get_setting

    with Session(engine) as session:
        count = requeue_active_on_startup(session)
        if count:
            logger.info("Re-queued %d in-progress jobs", count)
        pool.max_workers = int(get_setting(session, "max_concurrent") or 2)

    pool.start()
    yield
    pool.stop()


# ── App factory ───────────────────────────────────────────────


app = FastAPI(title="YourTube", version="0.1.0", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
```

- [ ] **Step 3: Implement app/routes/pages.py**

```python
"""HTML page routes (full page rendering, not htmx partials)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.db import get_session
from app.main import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("pages/home.html", {"request": request})


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request):
    return templates.TemplateResponse("pages/queue.html", {"request": request})


@router.get("/library", response_class=HTMLResponse)
async def library_page(request: Request):
    return templates.TemplateResponse("pages/library.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("pages/settings.html", {"request": request})


@router.get("/health")
async def health(db: Session = Depends(get_session)):
    try:
        db.exec(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: add app entry point, page routes, and worker pool"
```

---

## Task 8: API Routes (NEW: /api/info returns all formats, video+audio split)

**Files:**

- Create: `app/routes/api.py`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads_create.py`
- Create: `tests/integration/test_api_downloads_active.py`
- Create: `tests/integration/test_api_downloads_library.py`
- Create: `tests/integration/test_api_downloads_cancel.py`
- Create: `tests/integration/test_api_downloads_delete.py`
- Create: `tests/integration/test_api_downloads_file.py`
- Create: `tests/integration/test_api_settings_get.py`
- Create: `tests/integration/test_api_settings_put.py`
- Create: `tests/integration/test_api_settings_reset.py`
- Create: `tests/integration/test_startup_recovery.py`

- [ ] **Step 1: Write the API info tests (NEW: all formats returned)**

```python
# tests/integration/test_api_info.py
import pytest
from tests.conftest import SAMPLE_VIDEO_INFO


def test_info_returns_metadata(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Test Video"
    assert data["uploader"] == "Test Channel"
    assert data["duration"] == 213
    assert len(data["formats"]) == len(SAMPLE_VIDEO_INFO["formats"])


def test_info_formats_have_all_fields(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    fmt = r.json()["formats"][0]
    for key in ("id", "ext", "kind", "vcodec", "acodec", "tbr", "filesize_approx"):
        assert key in fmt, f"missing field: {key}"


def test_info_formats_have_kind_classified(client, mock_ytdlp):
    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"})
    formats = r.json()["formats"]
    kinds = {f["kind"] for f in formats}
    assert "video" in kinds
    assert "audio" in kinds


def test_info_without_url(client):
    r = client.post("/api/info", json={})
    assert r.status_code == 422


def test_info_handles_ytdlp_error(client, monkeypatch):
    import yt_dlp

    def failing_ydl(*a, **kw):
        raise ValueError("Something went wrong")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", failing_ydl)

    r = client.post("/api/info", json={"url": "https://youtube.com/watch?v=bad"})
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
```

- [ ] **Step 2: Write the downloads create tests (NEW: video_format_id + audio_format_id)**

```python
# tests/integration/test_api_downloads_create.py
import pytest


def test_create_download_with_video_and_audio(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "video_format_id": "137",
        "audio_format_id": "140",
    })
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["status"] == "queued"


def test_create_audio_only_download(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "format_choice": "audio",
        "audio_format_id": "140",
    })
    assert r.status_code == 200


def test_create_download_without_url(client):
    r = client.post("/api/downloads", json={"video_format_id": "137"})
    assert r.status_code == 422


def test_create_download_with_metadata(client):
    r = client.post("/api/downloads", json={
        "url": "https://youtube.com/watch?v=test",
        "title": "My Video",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "uploader": "SomeChannel",
        "duration": 213,
        "video_format_id": "137",
        "audio_format_id": "140",
    })
    assert r.status_code == 200
```

- [ ] **Step 3: Write the downloads active queue tests**

```python
# tests/integration/test_api_downloads_active.py
import pytest


def test_active_returns_queued_and_active(client):
    client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=1", "video_format_id": "137", "audio_format_id": "140"})
    client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=2", "video_format_id": "137", "audio_format_id": "140"})

    r = client.get("/api/downloads/active")
    assert r.status_code == 200
    assert "youtube.com" in r.text


def test_active_empty_when_no_jobs(client):
    r = client.get("/api/downloads/active")
    assert r.status_code == 200
```

- [ ] **Step 4: Write the downloads library tests**

```python
# tests/integration/test_api_downloads_library.py
import pytest
from app.models import Download


def test_library_returns_done_items(client, db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        session.add(Download(url="https://youtube.com/watch?v=test", status="done", title="Test Video"))
        session.commit()

    r = client.get("/api/downloads/library")
    assert r.status_code == 200
    assert "Test Video" in r.text


def test_library_search(client, db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        session.add(Download(url="https://youtube.com/1", status="done", title="Rick Astley"))
        session.add(Download(url="https://youtube.com/2", status="done", title="Nothing Else"))
        session.commit()

    r = client.get("/api/downloads/library?q=rick")
    assert "Rick" in r.text
    assert "Nothing" not in r.text
```

- [ ] **Step 5: Write the cancel/delete/file tests**

```python
# tests/integration/test_api_downloads_cancel.py
import pytest


def test_cancel_queued_job(client):
    r = client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=test"})
    job_id = r.json()["id"]

    r = client.post(f"/api/downloads/{job_id}/cancel")
    assert r.status_code == 200


def test_cancel_nonexistent_job(client):
    r = client.post("/api/downloads/99999/cancel")
    assert r.status_code == 404


# tests/integration/test_api_downloads_delete.py
def test_delete_done_job(client, db_engine, tmp_path):
    from sqlmodel import Session

    fp = tmp_path / "test.mp4"
    fp.write_text("data")

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp))
        session.add(d)
        session.commit()
        job_id = d.id

    r = client.delete(f"/api/downloads/{job_id}")
    assert r.status_code == 204
    assert not fp.exists()


def test_delete_nonexistent(client):
    r = client.delete("/api/downloads/99999")
    assert r.status_code == 404


# tests/integration/test_api_downloads_file.py
def test_download_file(client, db_engine, tmp_path):
    from sqlmodel import Session

    fp = tmp_path / "test.mp4"
    fp.write_bytes(b"fake mp4 bytes")

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="done", file_path=str(fp), title="My Video")
        session.add(d)
        session.commit()
        job_id = d.id

    r = client.get(f"/api/downloads/{job_id}/file")
    assert r.status_code == 200
    assert r.content == b"fake mp4 bytes"


def test_download_not_ready(client):
    r = client.post("/api/downloads", json={"url": "https://youtube.com/watch?v=test"})
    job_id = r.json()["id"]

    r = client.get(f"/api/downloads/{job_id}/file")
    assert r.status_code in (404, 409)
```

- [ ] **Step 6: Write the settings API tests**

```python
# tests/integration/test_api_settings_get.py
def test_get_settings(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "max_concurrent" in data
    assert data["default_format"] == "video"


# tests/integration/test_api_settings_put.py
def test_update_setting(client):
    r = client.put("/api/settings", json={"max_concurrent": "4"})
    assert r.status_code == 200
    assert r.json()["max_concurrent"] == "4"


def test_update_invalid_setting(client):
    r = client.put("/api/settings", json={"max_concurrent": "99"})
    assert r.status_code == 400


# tests/integration/test_api_settings_reset.py
def test_reset_settings(client):
    client.put("/api/settings", json={"max_concurrent": "8"})
    r = client.post("/api/settings/reset")
    assert r.status_code == 200
    assert r.json()["max_concurrent"] == "2"
```

- [ ] **Step 7: Write the startup recovery test**

```python
# tests/integration/test_startup_recovery.py
from app.models import Download
from app.services.queue import requeue_active_on_startup


def test_requeue_active_jobs(db_session):
    db_session.add(Download(url="https://youtube.com/1", status="active"))
    db_session.add(Download(url="https://youtube.com/2", status="active"))
    db_session.add(Download(url="https://youtube.com/3", status="queued"))
    db_session.commit()

    count = requeue_active_on_startup(db_session)
    assert count == 2
```

- [ ] **Step 8: Implement app/routes/api.py (NEW: all formats, video+audio IDs)**

```python
# app/routes/api.py
"""JSON and htmx partial API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlmodel import Session

from app.db import get_session
from app.main import templates
from app.models import (
    CookiesValidateResponse,
    Download,
    DownloadCreate,
    DownloadResponse,
    FormatInfo,
    InfoRequest,
    InfoResponse,
)
from app.services.downloader import (
    classify_format,
    extract_info,
    sanitize_filename,
)
from app.services.error_mapper import friendly_ytdlp_error
from app.services.library import delete_from_library, get_library, search_library
from app.services.queue import cancel_job, get_active_jobs
from app.services.settings import (
    get_all_settings,
    get_setting,
    reset_settings,
    set_settings_batch,
    validate_cookies_path,
)

router = APIRouter()


# ── Info (NEW: returns ALL formats with full details) ──────


@router.post("/info", response_model=InfoResponse)
async def fetch_info(body: InfoRequest, db: Session = Depends(get_session)):
    try:
        info = extract_info(str(body.url))
    except Exception as e:
        msg, code = friendly_ytdlp_error(str(e))
        raise HTTPException(status_code=400, detail={"error": msg, "code": code}) from e

    formats: list[FormatInfo] = []
    for f in info.get("formats", []):
        formats.append(
            FormatInfo(
                id=f.get("format_id", ""),
                ext=f.get("ext", ""),
                kind=classify_format(f),
                height=f.get("height"),
                width=f.get("width"),
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                tbr=f.get("tbr"),
                abr=f.get("abr"),
                filesize=f.get("filesize"),
                filesize_approx=f.get("filesize_approx"),
            )
        )

    return InfoResponse(
        title=info.get("title"),
        thumbnail_url=info.get("thumbnail"),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        formats=formats,
    )


# ── Downloads CRUD ───────────────────────────────────────


@router.post("/downloads")
async def create_download(body: DownloadCreate, db: Session = Depends(get_session)):
    if body.format_choice == "video" and not (body.video_format_id or body.audio_format_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "Pick at least a video or audio format", "code": "NO_FORMAT_SELECTED"},
        )

    row = Download(
        url=str(body.url),
        title=body.title,
        thumbnail_url=body.thumbnail_url,
        uploader=body.uploader,
        duration=body.duration,
        video_format_id=body.video_format_id,
        audio_format_id=body.audio_format_id,
        format_choice=body.format_choice,
        subtitles_enabled=body.subtitles_enabled,
        subtitle_languages=",".join(body.subtitle_languages) if body.subtitle_languages else None,
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status}


@router.get("/downloads/active", response_class=HTMLResponse)
async def list_active(request: Request, db: Session = Depends(get_session)):
    jobs = get_active_jobs(db)
    return templates.TemplateResponse(
        "partials/queue_rows.html",
        {"request": request, "jobs": jobs},
    )


@router.get("/downloads/library", response_class=HTMLResponse)
async def list_library(
    request: Request,
    q: str = Query(""),
    sort: str = Query("date"),
    db: Session = Depends(get_session),
):
    items = search_library(db, q=q, sort_by=sort) if q else get_library(db)
    return templates.TemplateResponse(
        "partials/library_rows.html",
        {"request": request, "items": items},
    )


@router.get("/downloads/{job_id}", response_model=DownloadResponse)
async def get_download(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    return _to_response(job)


@router.post("/downloads/{job_id}/cancel")
async def cancel_download(job_id: int, db: Session = Depends(get_session)):
    ok = cancel_job(db, job_id)
    if not ok:
        job = db.get(Download, job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
        raise HTTPException(status_code=409, detail={"error": "Job already finished", "code": "ALREADY_DONE"})
    return {"status": "cancelled"}


@router.delete("/downloads/{job_id}", status_code=204)
async def delete_download(job_id: int, db: Session = Depends(get_session)):
    ok, _ = delete_from_library(db, job_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})


@router.get("/downloads/{job_id}/file")
async def serve_file(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    if job.status != "done" or not job.file_path:
        raise HTTPException(status_code=409, detail={"error": "File not ready", "code": "FILE_NOT_READY"})

    fp = Path(job.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail={"error": "File missing on disk", "code": "FILE_NOT_FOUND"})

    filename = f"{sanitize_filename(job.title or 'video')}.{job.media_format or 'mp4'}"
    return FileResponse(
        path=str(fp),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/downloads/{job_id}/preview")
async def preview_file(job_id: int, db: Session = Depends(get_session)):
    job = db.get(Download, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found", "code": "JOB_NOT_FOUND"})
    if not job.file_path:
        raise HTTPException(status_code=409, detail={"error": "File not ready", "code": "FILE_NOT_READY"})

    fp = Path(job.file_path)
    if not fp.exists():
        raise HTTPException(status_code=404, detail={"error": "File missing on disk", "code": "FILE_NOT_FOUND"})

    return FileResponse(str(fp), media_type="video/mp4")


# ── Settings ─────────────────────────────────────────────


@router.get("/settings")
async def get_settings(db: Session = Depends(get_session)):
    return get_all_settings(db)


@router.put("/settings")
async def update_settings(body: dict[str, str], db: Session = Depends(get_session)):
    try:
        set_settings_batch(db, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": "VALIDATION_FAILED"}) from e
    return get_all_settings(db)


@router.post("/settings/reset")
async def reset_settings_route(db: Session = Depends(get_session)):
    reset_settings(db)
    return get_all_settings(db)


@router.get("/settings/cookies/validate")
async def validate_cookies(db: Session = Depends(get_session)):
    path = get_setting(db, "cookies_path")
    if not path:
        return CookiesValidateResponse(valid=False, message="No cookies path configured")
    valid, msg = validate_cookies_path(path)
    return CookiesValidateResponse(valid=valid, message=msg)


# ── Helpers ───────────────────────────────────────────────


def _to_response(job: Download) -> DownloadResponse:
    return DownloadResponse(
        id=job.id or 0,
        url=job.url,
        title=job.title,
        thumbnail_url=job.thumbnail_url,
        uploader=job.uploader,
        duration=job.duration,
        status=job.status,
        progress=job.progress,
        error=job.error,
        file_size=job.file_size,
        media_format=job.media_format,
        resolution_height=job.resolution_height,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
```

- [ ] **Step 9: Run all integration tests**

Run: `uv run pytest tests/integration/ -v`
Expected: PASS (all)

- [ ] **Step 10: Commit**

```bash
git add app/routes/api.py tests/integration/
git commit -m "feat: add API routes with full format picker and video+audio split"
```

---

## Task 9: Frontend CSS (UPDATED: format picker styles)

**Files:**

- Create: `app/static/css/app.css`

- [ ] **Step 1: Write the CSS**

```css
/* app/static/css/app.css — design tokens, layout, format picker */
:root {
  --bg: #fafafa;
  --surface: #ffffff;
  --border: #e5e5e5;
  --text: #1a1a1a;
  --text-muted: #6b7280;
  --accent: #dc2626;
  --accent-hover: #b91c1c;
  --sidebar-w: 200px;
  --radius: 8px;
  --status-active: #2563eb;
  --status-queued: #ca8a04;
  --status-done: #16a34a;
  --status-error: #dc2626;
  --status-cancelled: #6b7280;
}

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
body {
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  color: var(--text);
  background: var(--bg);
  min-height: 100vh;
}
a {
  color: var(--accent);
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}

/* Layout */
.app-layout {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
}
.sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-brand {
  font-size: 18px;
  font-weight: 700;
  padding: 8px 12px;
  margin-bottom: 16px;
}
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sidebar-nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  color: var(--text-muted);
  font-weight: 500;
  text-decoration: none;
  transition: all 0.15s;
}
.sidebar-nav a:hover,
.sidebar-nav a.active {
  background: #f3f4f6;
  color: var(--text);
  text-decoration: none;
}
.sidebar-nav a.active {
  color: var(--accent);
}
.sidebar-spacer {
  flex: 1;
}
.sidebar-footer {
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px 12px;
}

.content-area {
  padding: 32px;
  max-width: 1100px;
  width: 100%;
}

.page-header {
  margin-bottom: 24px;
}
.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}
.page-header p {
  color: var(--text-muted);
  margin-top: 4px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 8px;
}
.card:hover {
  border-color: #d1d5db;
}

.url-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.url-bar textarea {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  min-height: 48px;
  outline: none;
  transition: border-color 0.15s;
}
.url-bar textarea:focus {
  border-color: var(--accent);
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn:hover {
  opacity: 0.9;
}
.btn-primary {
  background: var(--accent);
  color: #fff;
}
.btn-primary:hover {
  background: var(--accent-hover);
}
.btn-ghost {
  background: #f3f4f6;
  color: var(--text);
}
.btn-danger {
  background: #fef2f2;
  color: var(--status-error);
}
.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pill-group {
  display: inline-flex;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.pill {
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.pill.active {
  background: var(--text);
  color: #fff;
}
.pill:not(.active):hover {
  color: var(--text);
}

/* ── Format picker (NEW) ────────────────────────────────────── */

.video-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
}
.video-card-header {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.video-card-thumb {
  width: 160px;
  min-width: 160px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--border);
  flex-shrink: 0;
}
.video-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-card-meta {
  flex: 1;
  min-width: 0;
}
.video-card-title {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 4px;
}
.video-card-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.format-tables {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.format-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.format-table th,
.format-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.format-table th {
  background: #f9fafb;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.format-table tr:last-child td {
  border-bottom: none;
}
.format-table tr.selected {
  background: #fef2f2;
}
.format-table tr:hover {
  background: #f9fafb;
  cursor: pointer;
}
.format-table tr.selected:hover {
  background: #fee2e2;
}

.format-table .col-quality {
  width: 60px;
}
.format-table .col-codec {
  width: 80px;
}
.format-table .col-bitrate {
  width: 70px;
}
.format-table .col-size {
  width: 80px;
  text-align: right;
}
.format-table .col-radio {
  width: 30px;
  text-align: center;
}

.format-picker-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.format-picker-summary {
  font-size: 12px;
  color: var(--text-muted);
}

.progress-wrap {
  width: 100%;
}
.progress-bg {
  background: #e5e7eb;
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
}
.progress-fill {
  background: linear-gradient(90deg, var(--status-active), #60a5fa);
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}
.progress-text {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.badge-active {
  background: #eff6ff;
  color: var(--status-active);
}
.badge-queued {
  background: #fef3c7;
  color: var(--status-queued);
}
.badge-done {
  background: #f0fdf4;
  color: var(--status-done);
}
.badge-error {
  background: #fef2f2;
  color: var(--status-error);
}
.badge-cancelled {
  background: #f3f4f6;
  color: var(--status-cancelled);
}

.queue-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.queue-row-info {
  flex: 1;
  min-width: 0;
}
.queue-row-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.queue-row-url {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.lib-row-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.lib-row-icon {
  width: 40px;
  height: 40px;
  background: var(--border);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.lib-row-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lib-row-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.lib-row-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.settings-form {
  max-width: 560px;
}
.setting-group {
  margin-bottom: 20px;
}
.setting-label {
  font-size: 14px;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}
.setting-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.setting-input {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--surface);
  outline: none;
  width: 100%;
  max-width: 400px;
  transition: border-color 0.15s;
}
.setting-input:focus {
  border-color: var(--accent);
}
.setting-input-short {
  max-width: 120px;
}
.setting-select {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--surface);
  cursor: pointer;
  outline: none;
}
.setting-textarea {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-family: monospace;
  background: var(--surface);
  outline: none;
  width: 100%;
  resize: vertical;
  transition: border-color 0.15s;
}
.setting-textarea:focus {
  border-color: var(--accent);
}
.setting-actions {
  display: flex;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}
.modal-overlay.active {
  display: flex;
}
.modal-content {
  background: #1a1a1a;
  border-radius: 12px;
  overflow: hidden;
  width: 90vw;
  max-width: 960px;
  position: relative;
}
.modal-close {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  font-size: 18px;
  cursor: pointer;
  z-index: 10;
}
.modal-content video {
  width: 100%;
  display: block;
  max-height: 80vh;
}

.toast {
  position: fixed;
  top: 16px;
  right: 16px;
  padding: 12px 20px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  z-index: 2000;
  opacity: 0;
  transform: translateY(-8px);
  transition: all 0.3s;
  pointer-events: none;
}
.toast.show {
  opacity: 1;
  transform: translateY(0);
}
.toast-success {
  background: #f0fdf4;
  color: var(--status-done);
  border: 1px solid #bbf7d0;
}
.toast-error {
  background: #fef2f2;
  color: var(--status-error);
  border: 1px solid #fecaca;
}

.empty {
  text-align: center;
  padding: 48px 0;
  color: var(--text-muted);
}

.files-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}
.files-bar input {
  flex: 1;
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--surface);
  outline: none;
}
.files-bar input:focus {
  border-color: var(--accent);
}
.files-bar select {
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--surface);
  cursor: pointer;
  outline: none;
}

@media (max-width: 900px) {
  .format-tables {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    display: none;
  }
  .content-area {
    padding: 16px;
  }
  .video-card-header {
    flex-direction: column;
  }
  .video-card-thumb {
    width: 100%;
    min-width: unset;
    height: 180px;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/app.css
git commit -m "feat: add app CSS (design tokens, format picker, responsive)"
```

---

## Task 10: Frontend Templates (NEW: format picker UI)

**Files:**

- Create: `app/templates/base.html`
- Create: `app/templates/components/sidebar.html`
- Create: `app/templates/components/format_toggle.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `app/templates/partials/queue_rows.html`
- Create: `app/templates/partials/library_rows.html`
- Create: `app/templates/partials/toast.html`

- [ ] **Step 1: Create base.html + sidebar**

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>YourTube</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <link rel="stylesheet" href="/static/css/app.css" />
  </head>
  <body>
    <div class="app-layout">
      {% include "components/sidebar.html" %}
      <main class="content-area">{% block content %}{% endblock %}</main>
    </div>
    <div id="toast-container" hx-swap-oob="true"></div>
    <script>
      function parseUrls(text) {
        return [
          ...new Set(
            text
              .split(/[\s,]+/)
              .map((u) => u.trim())
              .filter((u) => u.startsWith("http")),
          ),
        ];
      }
    </script>
  </body>
</html>
```

```html
<!-- app/templates/components/sidebar.html -->
<nav class="sidebar">
  <div class="sidebar-brand">YourTube</div>
  <div class="sidebar-nav">
    <a href="/" class="{% if request.url.path == '/' %}active{% endif %}"
      >🏠 Home</a
    >
    <a
      href="/queue"
      class="{% if request.url.path == '/queue' %}active{% endif %}"
      >⏳ Queue</a
    >
    <a
      href="/library"
      class="{% if request.url.path == '/library' %}active{% endif %}"
      >📚 Library</a
    >
    <a
      href="/settings"
      class="{% if request.url.path == '/settings' %}active{% endif %}"
      >⚙ Settings</a
    >
  </div>
  <div class="sidebar-spacer"></div>
  <div class="sidebar-footer">v0.1.0</div>
</nav>
```

- [ ] **Step 2: Create home page (NEW: format picker)**

```html
<!-- app/templates/pages/home.html -->
{% extends "base.html" %} {% block content %}
<div class="page-header">
  <h1>Download</h1>
  <p>Paste YouTube URLs to fetch available formats</p>
</div>

<div class="url-bar">
  <textarea
    id="urls"
    placeholder="Paste one or more YouTube URLs..."
    rows="2"
  ></textarea>
</div>

<div
  class="controls"
  style="display:flex;gap:10px;align-items:center;margin-bottom:20px;"
>
  {% include "components/format_toggle.html" %}
  <button class="btn btn-primary" id="fetch-btn" onclick="fetchUrls()">
    Fetch
  </button>
</div>

<div id="cards"></div>
{% endblock %}

<script>
  let currentFormat = "video";

  function prettyCodec(c) {
    if (!c || c === "none") return "—";
    const c2 = c.toLowerCase();
    if (c2.startsWith("avc1") || c2 === "h264") return "H.264";
    if (c2.startsWith("vp9") || c2 === "vp09") return "VP9";
    if (c2.startsWith("av01")) return "AV1";
    if (c2 === "opus") return "Opus";
    if (c2.startsWith("mp4a")) return "AAC";
    return c;
  }

  function prettySize(bytes) {
    if (!bytes) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0,
      n = bytes;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }
    return `${n.toFixed(1)} ${units[i]}`;
  }

  function setFormat(btn) {
    document
      .querySelectorAll(".pill")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFormat = btn.dataset.format;
  }

  async function fetchUrls() {
    const urls = parseUrls(document.getElementById("urls").value);
    if (!urls.length) return;

    const btn = document.getElementById("fetch-btn");
    const container = document.getElementById("cards");
    btn.disabled = true;
    btn.textContent = "Fetching...";
    container.innerHTML = "";

    for (const url of urls) {
      const card = document.createElement("div");
      card.className = "video-card";
      card.dataset.url = url;
      card.innerHTML = `
      <div class="video-card-header">
        <div class="video-card-thumb" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted);">⏳</div>
        <div class="video-card-meta">
          <div class="video-card-title">${url}</div>
          <div class="video-card-sub">Fetching metadata...</div>
        </div>
      </div>
    `;
      container.appendChild(card);

      try {
        const res = await fetch("/api/info", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        const data = await res.json();

        if (data.detail && data.detail.error) {
          card.innerHTML = `
          <div class="video-card-header" style="border-left:3px solid var(--status-error);">
            <div class="video-card-meta">
              <div class="video-card-title" style="color:var(--status-error);">⚠ ${data.detail.error}</div>
              <div class="video-card-sub" style="word-break:break-all;">${url}</div>
            </div>
          </div>
        `;
          continue;
        }

        renderFormatPicker(card, data, currentFormat);
      } catch (err) {
        card.innerHTML = `<div class="video-card-meta" style="color:var(--status-error);">Network error: ${err.message}</div>`;
      }
    }
    btn.disabled = false;
    btn.textContent = "Fetch";
  }

  function escHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function renderFormatPicker(card, info, formatChoice) {
    const videoStreams = info.formats.filter(
      (f) => f.kind === "video" || f.kind === "combined",
    );
    const audioStreams = info.formats.filter((f) => f.kind === "audio");

    const defaultVideoId = videoStreams[0]?.id;
    const defaultAudioId = audioStreams[0]?.id;

    card.dataset.videoId = defaultVideoId || "";
    card.dataset.audioId = formatChoice === "audio" ? "" : defaultAudioId || "";
    card.dataset.formatChoice = formatChoice;
    card.dataset.title = info.title || "";
    card.dataset.thumbnail = info.thumbnail_url || "";
    card.dataset.uploader = info.uploader || "";
    card.dataset.duration = info.duration || "";

    const fmtDuration = (s) => {
      if (!s) return "";
      return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    };

    const videoRows = videoStreams
      .map((f) => {
        const size = f.filesize || f.filesize_approx || 0;
        const quality = f.height
          ? f.height >= 2160
            ? "4K"
            : f.height >= 1440
              ? "1440p"
              : f.height >= 1080
                ? "1080p"
                : f.height >= 720
                  ? "720p"
                  : f.height >= 480
                    ? "480p"
                    : `${f.height}p`
          : "—";
        return `<tr data-fmt-id="${f.id}" data-kind="video" onclick="selectFormat(this)">
      <td class="col-radio"><input type="radio" name="v-${card.dataset.url}" value="${f.id}" ${f.id === defaultVideoId ? "checked" : ""}></td>
      <td class="col-quality">${quality}</td>
      <td>${f.height || "—"}p</td>
      <td>${f.ext.toUpperCase()}</td>
      <td class="col-codec">${prettyCodec(f.vcodec)}</td>
      <td class="col-bitrate">${f.tbr ? Math.round(f.tbr) + " kbps" : "—"}</td>
      <td class="col-size">${prettySize(size)}</td>
    </tr>`;
      })
      .join("");

    const audioRows = audioStreams
      .map((f) => {
        const size = f.filesize || f.filesize_approx || 0;
        return `<tr data-fmt-id="${f.id}" data-kind="audio" onclick="selectFormat(this)">
      <td class="col-radio"><input type="radio" name="a-${card.dataset.url}" value="${f.id}" ${f.id === defaultAudioId ? "checked" : ""}></td>
      <td>${f.ext.toUpperCase()}</td>
      <td class="col-codec">${prettyCodec(f.acodec)}</td>
      <td class="col-bitrate">${f.abr ? Math.round(f.abr) + " kbps" : "—"}</td>
      <td class="col-size">${prettySize(size)}</td>
    </tr>`;
      })
      .join("");

    card.innerHTML = `
    <div class="video-card-header">
      <div class="video-card-thumb">
        <img src="${info.thumbnail_url || ""}" alt="" onerror="this.parentElement.innerHTML='<div style=\\'display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);background:var(--border)\\'>📺</div>'">
      </div>
      <div class="video-card-meta">
        <div class="video-card-title">${escHtml(info.title || "Untitled")}</div>
        <div class="video-card-sub">${escHtml(info.uploader || "")}${info.duration ? " · " + fmtDuration(info.duration) : ""}</div>
      </div>
    </div>
    <div class="format-tables">
      <div>
        <h3 style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">Video Stream</h3>
        <table class="format-table">
          <thead><tr>
            <th class="col-radio"></th>
            <th class="col-quality">Quality</th>
            <th>Resolution</th>
            <th>Container</th>
            <th class="col-codec">Video Codec</th>
            <th class="col-bitrate">Bitrate</th>
            <th class="col-size">Size</th>
          </tr></thead>
          <tbody>${videoRows || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No video streams</td></tr>'}</tbody>
        </table>
      </div>
      <div>
        <h3 style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">Audio Stream</h3>
        <table class="format-table">
          <thead><tr>
            <th class="col-radio"></th>
            <th>Container</th>
            <th class="col-codec">Audio Codec</th>
            <th class="col-bitrate">Bitrate</th>
            <th class="col-size">Size</th>
          </tr></thead>
          <tbody>${audioRows || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No audio streams</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    <div class="format-picker-actions">
      <div class="format-picker-summary" id="summary-${card.dataset.url}">Pick a combination above</div>
      <button class="btn btn-primary" onclick="enqueue(this)" ${formatChoice === "audio" ? 'data-audio-only="1"' : ""}>
        ${formatChoice === "audio" ? "Download Audio" : "Download Selected"}
      </button>
    </div>
  `;

    const defaultV = card.querySelector(`tr[data-fmt-id="${defaultVideoId}"]`);
    if (defaultV) defaultV.classList.add("selected");
    const defaultA = card.querySelector(`tr[data-fmt-id="${defaultAudioId}"]`);
    if (defaultA) defaultA.classList.add("selected");
  }

  function selectFormat(row) {
    const card = row.closest(".video-card");
    const kind = row.dataset.kind;
    const fmtId = row.dataset.fmtId;

    row.parentElement
      .querySelectorAll("tr")
      .forEach((r) => r.classList.remove("selected"));
    row.classList.add("selected");

    if (kind === "video") card.dataset.videoId = fmtId;
    else card.dataset.audioId = fmtId;

    row.querySelector("input[type=radio]").checked = true;
  }

  async function enqueue(btn) {
    const card = btn.closest(".video-card");
    const isAudioOnly = btn.dataset.audioOnly === "1";

    const payload = {
      url: card.dataset.url,
      title: card.dataset.title,
      thumbnail_url: card.dataset.thumbnail,
      uploader: card.dataset.uploader,
      duration: parseInt(card.dataset.duration) || null,
      format_choice: isAudioOnly ? "audio" : "video",
      video_format_id: isAudioOnly ? null : card.dataset.videoId,
      audio_format_id: card.dataset.audioId || null,
    };

    btn.disabled = true;
    btn.textContent = "...";

    try {
      const res = await fetch("/api/downloads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.id) {
        btn.textContent = "✓ Queued";
        btn.style.background = "var(--status-done)";
        card.querySelector(".format-picker-actions").innerHTML =
          '<a href="/queue" class="btn btn-ghost btn-sm">View in Queue →</a>';
      } else {
        btn.textContent = "Error";
        btn.style.background = "var(--status-error)";
      }
    } catch {
      btn.textContent = "Error";
      btn.style.background = "var(--status-error)";
    }
  }
</script>
```

```html
<!-- app/templates/components/format_toggle.html -->
<div class="pill-group">
  <button class="pill active" data-format="video" onclick="setFormat(this)">
    MP4
  </button>
  <button class="pill" data-format="audio" onclick="setFormat(this)">
    MP3
  </button>
</div>
```

- [ ] **Step 3: Create queue page + partials**

```html
<!-- app/templates/pages/queue.html -->
{% extends "base.html" %} {% block content %}
<div class="page-header">
  <h1>Queue</h1>
  <p>Active and queued downloads</p>
</div>

<div
  id="queue-body"
  hx-get="/api/downloads/active"
  hx-trigger="load, every 1.5s"
  hx-swap="innerHTML"
>
  <p class="empty">No active downloads.</p>
</div>
{% endblock %}
```

```html
<!-- app/templates/partials/queue_rows.html -->
{% for job in jobs %}
<div class="card">
  <div class="queue-row">
    <div class="queue-row-info">
      <div class="queue-row-title">{{ job.title or job.url }}</div>
      <div class="queue-row-url">
        {{ job.url }} {% if job.video_format_id %}<span
          style="color:var(--text-muted);"
          >· v:{{ job.video_format_id }}{% if job.audio_format_id %} a:{{
          job.audio_format_id }}{% endif %}</span
        >{% endif %}
      </div>
    </div>
    <div>
      <span class="badge badge-{{ job.status }}">
        {{
        {'queued':'Queued','fetching_info':'Fetching','active':'Downloading','paused':'Paused'}.get(job.status,
        job.status) }}
      </span>
      {% if job.status in ('queued', 'active', 'fetching_info') %}
      <button
        class="btn btn-danger btn-sm"
        hx-post="/api/downloads/{{ job.id }}/cancel"
        hx-target="closest .card"
        hx-swap="outerHTML"
      >
        Cancel
      </button>
      {% endif %}
    </div>
  </div>
  {% if job.status == 'active' %}
  <div class="progress-wrap" style="margin-top:8px;">
    <div class="progress-bg">
      <div
        class="progress-fill"
        style="width:{{ job.progress|default(0) }}%"
      ></div>
    </div>
    <div class="progress-text">
      {{ '%.1f'|format(job.progress|default(0)) }}%
    </div>
  </div>
  {% endif %} {% if job.error %}
  <div style="font-size:12px;color:var(--status-error);margin-top:4px;">
    {{ job.error }}
  </div>
  {% endif %}
</div>
{% else %}
<p class="empty">No active downloads.</p>
{% endfor %}
```

- [ ] **Step 4: Create library page + partials**

```html
<!-- app/templates/pages/library.html -->
{% extends "base.html" %} {% block content %}
<div class="page-header">
  <h1>Library</h1>
  <p>Downloaded videos and files</p>
</div>

<div class="files-bar">
  <input
    type="text"
    id="lib-search"
    name="q"
    placeholder="Search..."
    hx-get="/api/downloads/library"
    hx-trigger="keyup changed delay:300ms"
    hx-target="#library-body"
    hx-include="[name='q'],[name='sort']"
  />
  <select
    id="lib-sort"
    name="sort"
    hx-get="/api/downloads/library"
    hx-trigger="change"
    hx-target="#library-body"
    hx-include="[name='q'],[name='sort']"
  >
    <option value="date">Newest</option>
    <option value="name">Name</option>
    <option value="size">Size</option>
  </select>
</div>

<div id="library-body" hx-get="/api/downloads/library" hx-trigger="load">
  <p class="empty">No downloads yet.</p>
</div>
{% endblock %}
```

```html
<!-- app/templates/partials/library_rows.html -->
{% for item in items %}
<div class="card">
  <div class="lib-row">
    <div class="lib-row-info">
      <div class="lib-row-icon">🎬</div>
      <div>
        <div class="lib-row-name">{{ item.title or 'Untitled' }}</div>
        <div class="lib-row-meta">
          {% if item.file_size %}{{ '%d MB'|format(item.file_size//1048576) }}{%
          endif %} {% if item.completed_at %} · {{
          item.completed_at.strftime('%Y-%m-%d') }}{% endif %}
          <span class="badge badge-{{ item.status }}">{{ item.status }}</span>
          {% if item.video_format_id %}<span style="color:var(--text-muted);"
            >· v:{{ item.video_format_id }}{% if item.audio_format_id %} a:{{
            item.audio_format_id }}{% endif %}</span
          >{% endif %}
        </div>
      </div>
    </div>
    <div class="lib-row-actions">
      {% if item.status == 'done' and item.file_path %}
      <button class="btn btn-ghost btn-sm" onclick="previewFile({{ item.id }})">
        ▶ Preview
      </button>
      <a class="btn btn-primary btn-sm" href="/api/downloads/{{ item.id }}/file"
        >↓ Download</a
      >
      {% endif %}
      <button
        class="btn btn-danger btn-sm"
        hx-delete="/api/downloads/{{ item.id }}"
        hx-target="closest .card"
        hx-swap="outerHTML swap:200ms"
        hx-confirm="Delete this file permanently?"
      >
        ✕
      </button>
    </div>
  </div>
  {% if item.error %}
  <div style="font-size:12px;color:var(--status-error);margin-top:4px;">
    {{ item.error }}
  </div>
  {% endif %}
</div>
{% else %}
<p class="empty">No downloads yet. <a href="/">Download some videos →</a></p>
{% endfor %}
```

```html
<!-- app/templates/partials/toast.html -->
<div id="toast" class="toast {{ type }} show">{{ message }}</div>
<script>
  setTimeout(
    () => document.getElementById("toast")?.classList.remove("show"),
    2500,
  );
</script>
```

- [ ] **Step 5: Create settings page**

```html
<!-- app/templates/pages/settings.html -->
{% extends "base.html" %} {% block content %}
<div class="page-header">
  <h1>Settings</h1>
  <p>Configure download behaviour and system options</p>
</div>

<form
  class="settings-form"
  hx-put="/api/settings"
  hx-target="#settings-feedback"
  hx-swap="innerHTML"
  onsubmit="return false;"
>
  <div class="setting-group">
    <label class="setting-label" for="s-downloads-dir"
      >Downloads directory</label
    >
    <div class="setting-desc">Where downloaded files are saved</div>
    <input
      class="setting-input"
      id="s-downloads-dir"
      name="downloads_dir"
      value=""
    />
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-max-concurrent"
      >Max concurrent downloads</label
    >
    <div class="setting-desc">
      Maximum number of simultaneous downloads (1-8)
    </div>
    <input
      class="setting-input setting-input-short"
      id="s-max-concurrent"
      name="max_concurrent"
      type="number"
      min="1"
      max="8"
      value="2"
    />
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-default-format">Default format</label>
    <div class="setting-desc">MP4 video or MP3 audio</div>
    <select class="setting-select" id="s-default-format" name="default_format">
      <option value="video">Video (MP4)</option>
      <option value="audio">Audio (MP3)</option>
    </select>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-filename-template"
      >Filename template</label
    >
    <div class="setting-desc">
      yt-dlp output template (e.g. %(title)s [%(id)s].%(ext)s)
    </div>
    <input
      class="setting-input"
      id="s-filename-template"
      name="filename_template"
      value=""
    />
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-subtitle-languages"
      >Subtitle languages</label
    >
    <div class="setting-desc">
      JSON array of language codes (e.g. ["en","ko"])
    </div>
    <input
      class="setting-input"
      id="s-subtitle-languages"
      name="subtitle_languages"
      value='["en"]'
    />
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-cookies-path">Cookies path</label>
    <div class="setting-desc">
      Absolute path to a Netscape-format cookies.txt from your browser
    </div>
    <input
      class="setting-input"
      id="s-cookies-path"
      name="cookies_path"
      placeholder="/data/cookies.txt"
      hx-get="/api/settings/cookies/validate"
      hx-trigger="change"
      hx-target="#cookies-status"
      hx-swap="innerHTML"
    />
    <div id="cookies-status" style="font-size:12px;margin-top:4px;"></div>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-proxy-url">Proxy URL</label>
    <div class="setting-desc">
      HTTP proxy for yt-dlp (e.g. http://proxy:8080)
    </div>
    <input
      class="setting-input"
      id="s-proxy-url"
      name="proxy_url"
      placeholder=""
    />
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-audio-bitrate"
      >Audio bitrate (kbps)</label
    >
    <div class="setting-desc">Bitrate for MP3 extraction (64-320)</div>
    <input
      class="setting-input setting-input-short"
      id="s-audio-bitrate"
      name="audio_bitrate"
      type="number"
      min="64"
      max="320"
      value="192"
    />
  </div>

  <div class="setting-group">
    <label class="setting-label">Embed metadata</label>
    <div class="setting-desc">
      Write title, uploader, etc. into file metadata
    </div>
    <select class="setting-select" name="embed_metadata">
      <option value="true">Yes</option>
      <option value="false">No</option>
    </select>
  </div>

  <div class="setting-group">
    <label class="setting-label" for="s-extra-args"
      >Extra yt-dlp arguments</label
    >
    <div class="setting-desc">
      JSON array of additional CLI flags (advanced)
    </div>
    <textarea
      class="setting-textarea"
      id="s-extra-args"
      name="extra_ytdlp_args"
      rows="2"
    >
[]</textarea
    >
  </div>

  <div class="setting-actions">
    <button class="btn btn-primary" type="submit">Save</button>
    <button
      class="btn btn-ghost"
      type="button"
      hx-post="/api/settings/reset"
      hx-target="#settings-feedback"
      hx-confirm="Reset all settings to defaults?"
    >
      Reset to defaults
    </button>
  </div>
</form>

<div id="settings-feedback" style="margin-top:12px;"></div>

<script>
  fetch("/api/settings")
    .then((r) => r.json())
    .then((s) => {
      Object.entries(s).forEach(([k, v]) => {
        const el = document.querySelector(`[name="${k}"]`);
        if (el) el.value = v;
      });
    });
</script>
{% endblock %}
```

- [ ] **Step 6: Add preview modal JS to base.html**

Add to `base.html` before `</body>`:

```html
<!-- Video preview modal -->
<div class="modal-overlay" id="videoModal">
  <div class="modal-content">
    <button class="modal-close" onclick="closePreview()">&times;</button>
    <video id="videoPlayer" controls></video>
  </div>
</div>

<script>
  function previewFile(id) {
    const player = document.getElementById("videoPlayer");
    player.src = "/api/downloads/" + id + "/preview";
    document.getElementById("videoModal").classList.add("active");
    player.play();
  }
  function closePreview() {
    const player = document.getElementById("videoPlayer");
    player.pause();
    player.src = "";
    document.getElementById("videoModal").classList.remove("active");
  }
  document.getElementById("videoModal").addEventListener("click", function (e) {
    if (e.target === this) closePreview();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closePreview();
  });
</script>
```

- [ ] **Step 7: Manual verification**

Start the server:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and verify:

- Home page renders with URL input
- After fetching a YouTube URL, two side-by-side tables appear (Video Streams + Audio Streams)
- Each row is clickable to select
- Clicking "Download Selected" enqueues a job
- Queue page shows the active job with progress
- Library page shows completed files
- Settings page loads with default values

- [ ] **Step 8: Commit**

```bash
git add app/templates/
git commit -m "feat: add frontend templates with two-table format picker (video+audio)"
```

---

## Task 11: DevOps

**Files:**

- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Dockerfile**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN groupadd --system --gid 1000 appuser \
 && useradd  --system --uid 1000 --gid appuser --home /app --shell /sbin/nologin appuser

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

RUN mkdir -p /data /downloads /cookies \
 && chown -R appuser:appuser /data /downloads /cookies

USER appuser

ENV YT_HOST=0.0.0.0 \
    YT_PORT=8000 \
    YT_DATA_DIR=/data \
    YT_DOWNLOADS_DIR=/downloads \
    YT_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

- [ ] **Step 2: docker-compose.yml**

```yaml
services:
  yourtube:
    build: .
    image: yourtube:latest
    container_name: yourtube
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - yourtube-data:/data
      # Uncomment and adjust for your setup:
      # - /path/to/downloads:/downloads
      # - /path/to/cookies:/cookies:ro
    environment:
      YT_LOG_LEVEL: INFO
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

volumes:
  yourtube-data:
    driver: local
```

- [ ] **Step 3: CI workflow**

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

- [ ] **Step 4: Build and verify Docker image**

Run:

```bash
docker build -t yourtube:test .
docker compose up -d
sleep 3
curl -fsS http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .github/workflows/ci.yml
git commit -m "chore: add Dockerfile, docker-compose, and CI workflow"
```

---

## Self-Review Checklist

After writing the complete plan, run through these checks:

**Spec coverage:**

- Architecture (in-process workers, SQLite queue) → Tasks 5, 7
- Data model (single downloads table) → Task 1 (SQLModel)
- API surface (all routes) → Tasks 7, 8
- Frontend (sidebar, pages, htmx patterns) → Tasks 9, 10
- Error handling → Tasks 2, 8
- Testing (80% coverage, mocked yt-dlp) → Tasks 2-8
- DevOps (Dockerfile, compose, CI) → Task 11
- **SQLModel + standalone schemas** → Task 1
- **ty** → Task 11
- **Pydantic (via SQLModel) for all schemas** → Task 1
- **Format picker UI with two tables (video + audio)** → Task 10
- **Backend downloads video and audio separately, muxes to MP4** → Task 4 (downloader) + Task 7 (worker)

**Placeholder scan:** Check for TBD, TODO, "implement later" patterns. All code is inlined.

**Type consistency:** Function signatures used in later tasks match earlier tasks:

- `build_format_selector(video_id, audio_id)` consistent across downloader + tests + worker
- `Download.video_format_id` and `audio_format_id` consistent across model + tests + API + worker
- `run_download(...)` parameters consistent across service definition and worker usage

---

## Execution Handoff

Plan complete and saved to `plans/2026-06-09-yourtube-design.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
