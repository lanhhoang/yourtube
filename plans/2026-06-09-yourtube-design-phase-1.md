# Phase 1: Scaffold + SQLAlchemy + Alembic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a bootable FastAPI skeleton with SQLAlchemy persistence, Alembic migrations, and migrated test fixtures.

**Architecture:** `app/db.py` owns the engine, session factory, and FastAPI dependency. `app/models.py` contains ORM models only, `app/schemas.py` contains Pydantic contracts only, and Alembic owns initial schema creation. Startup runs migrations before exposing `/health`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Pydantic Settings, uv, ruff, ty, pytest

---

## File Structure (this phase)

```
yourtube/
├── pyproject.toml
├── uv.lock
├── .env.example
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── routes/__init__.py
│   └── services/__init__.py
├── alembic/
│   ├── env.py
│   └── versions/
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_db.py
    └── test_health.py
```

### Task 1: Project metadata and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/routes/__init__.py`
- Create: `app/services/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml` with the runtime stack**

Include these runtime dependencies:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.36",
    "alembic>=1.14.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "yt-dlp>=2024.12.0",
    "curl-cffi>=0.7.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.18",
]
```

- [ ] **Step 2: Add dev dependencies and tool config**

Include:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "ty>=0.11.0",
]
```

- [ ] **Step 3: Add package marker files and `.env.example`**

`.env.example` should include:

```dotenv
YT_HOST=127.0.0.1
YT_PORT=8000
YT_DATA_DIR=./tmp/data
YT_DOWNLOADS_DIR=./tmp/downloads
YT_LOG_LEVEL=INFO
```

- [ ] **Step 4: Install dependencies**

Run: `uv sync`
Expected: lockfile updates successfully and installs `sqlalchemy` and `alembic`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .env.example app/__init__.py app/routes/__init__.py app/services/__init__.py tests/__init__.py
git commit -m "chore: scaffold project metadata for sqlalchemy and alembic"
```

### Task 2: Config, database setup, and ORM boundaries

**Files:**
- Create: `app/config.py`
- Create: `app/db.py`
- Create: `app/models.py`
- Create: `app/schemas.py`
- Create: `tests/test_config.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing config test**

```python
from app.config import settings


def test_settings_defaults():
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
```

- [ ] **Step 2: Implement `app/config.py`**

Define a `Settings` class with:

```python
host: str = "127.0.0.1"
port: int = 8000
data_dir: Path
downloads_dir: Path
cookies_path: Path | None = None
proxy_url: str | None = None
log_level: str = "INFO"
workers: int = 1
```

- [ ] **Step 3: Define database setup in `app/db.py`**

Implement:

```python
engine = create_engine(...)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_session() -> Generator[Session, None, None]:
    ...
```

Add SQLite pragmas on connect and do not call `Base.metadata.create_all()`.

- [ ] **Step 4: Define ORM models in `app/models.py`**

Create SQLAlchemy declarative models:

```python
class Download(Base): ...
class Setting(Base): ...
```

Include queue, metadata, file output, and timestamp columns. Do not include request or response schemas in this file.

- [ ] **Step 5: Define Pydantic contracts in `app/schemas.py`**

Create:

```python
class InfoRequest(BaseModel): ...
class DownloadCreate(BaseModel): ...
class FormatInfo(BaseModel): ...
class InfoResponse(BaseModel): ...
class DownloadResponse(BaseModel): ...
class ErrorResponse(BaseModel): ...
```

- [ ] **Step 6: Add ORM boundary tests**

`tests/test_db.py` should check:

```python
from app.models import Download, Setting


def test_model_tables_named():
    assert Download.__tablename__ == "downloads"
    assert Setting.__tablename__ == "settings"
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_config.py tests/test_db.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/db.py app/models.py app/schemas.py tests/test_config.py tests/test_db.py
git commit -m "feat: add sqlalchemy models and pydantic schemas"
```

### Task 3: Alembic baseline and migrated test fixtures

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize Alembic configuration**

`alembic/env.py` must load metadata from `app.models.Base.metadata`.

- [ ] **Step 2: Write the initial migration**

The revision must create:

- `downloads`
- `settings`

It must not create a schema version application table beyond Alembic's own version table.

- [ ] **Step 3: Implement migrated test fixtures**

`tests/conftest.py` should:

- create a temporary SQLite file
- override the app database URL for tests
- run `alembic upgrade head`
- provide a SQLAlchemy `Session` fixture

- [ ] **Step 4: Add migration health test**

Add this to `tests/test_db.py`:

```python
def test_migrations_create_expected_tables(db_engine):
    inspector = inspect(db_engine)
    assert "downloads" in inspector.get_table_names()
    assert "settings" in inspector.get_table_names()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add alembic.ini alembic tests/conftest.py tests/test_db.py
git commit -m "feat: add alembic baseline migration and migrated test fixtures"
```

### Task 4: Minimal app startup and health route

**Files:**
- Create: `app/main.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Implement startup flow**

`app/main.py` should:

- run `alembic upgrade head` in lifespan
- expose `/health`
- verify DB reachability with `SELECT 1`

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_health.py
git commit -m "feat: add migrated app startup and health endpoint"
```

## Self-Review (Phase 1)

- Covers dependency swap to SQLAlchemy.
- Makes Alembic the only schema authority.
- Keeps ORM and API schemas separate.
- Ensures tests use migrated schema, not `create_all()`.

## End of Phase 1

Deliverable: `uv run uvicorn app.main:app` starts successfully, `/health` returns `{"status":"ok"}`, and a fresh test database is built by Alembic migrations.
