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
├── .github/workflows/quality.yml         # ← added in Phase 1
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
│   ├── script.py.mako
│   └── versions/
│       └── YYYYMMDDHHMMSS_create_downloads_and_settings.py
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

- [x] **Step 1: Create `pyproject.toml`**

Dependencies follow the plan's `>=` lower bounds but use uv's modern `[dependency-groups]` instead of `[project.optional-dependencies]`.

`pyproject.toml` also includes tool config sections for ruff, ty, and pytest (merged from the `20260609-phase-1-scaffold-project-old` branch).

- [x] **Step 2: Create `.env.example`**

```dotenv
YT_HOST=127.0.0.1
YT_PORT=8000
YT_DATA_DIR=./tmp/data
YT_DOWNLOADS_DIR=./tmp/downloads
YT_LOG_LEVEL=INFO
```

- [x] **Step 3: Create package marker files**

`app/__init__.py`, `app/routes/__init__.py`, `app/services/__init__.py`, `tests/__init__.py`.

- [x] **Step 4: Install dependencies**

Run: `uv sync`

- [x] **Step 5: Commit**

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

- [x] **Step 1: Write the failing config test**

```python
from app.config import settings


def test_settings_defaults():
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
```

- [x] **Step 2: Implement `app/config.py`**

`Settings` uses pydantic-settings with `YT_` prefix. Key differences from the skeleton plan:

- `database_url: str` derives from `data_dir` via a `model_validator(mode="before")` unless `YT_DATABASE_URL` is explicitly set
- All fields have defaults so the `settings` singleton loads without a `.env` file

```python
class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("./tmp/data")
    downloads_dir: Path = Path("./tmp/downloads")
    cookies_path: Path | None = None
    proxy_url: str | None = None
    log_level: str = "INFO"
    workers: int = 1
    database_url: str = ""     # filled by validator from data_dir
```

- [x] **Step 3: Define database setup in `app/db.py`**

Eagerly-created `engine`, `SessionLocal`, FastAPI `get_session` dependency, and a SQLite connect listener that sets `PRAGMA foreign_keys=ON` and `PRAGMA busy_timeout=5000`. Engine allows `check_same_thread=False` for concurrent usage.

- [x] **Step 4: Define ORM models in `app/models.py`**

`Base(DeclarativeBase)`, `Download`, `Setting` with queue/metadata/file/timestamp columns.

- [x] **Step 5: Define Pydantic contracts in `app/schemas.py`**

`InfoRequest`, `DownloadCreate`, `FormatInfo`, `InfoResponse`, `DownloadResponse`, `ErrorResponse`.

- [x] **Step 6: Add ORM boundary tests**

```python
def test_model_tables_named():
    assert Download.__tablename__ == "downloads"
    assert Setting.__tablename__ == "settings"
```

- [x] **Step 7: Run tests**

Run: `uv run pytest tests/test_config.py tests/test_db.py -v`
Expected: PASS

- [x] **Step 8: Commit**

```bash
git add app/config.py app/db.py app/models.py app/schemas.py tests/test_config.py tests/test_db.py
git commit -m "feat: add sqlalchemy models and pydantic schemas"
```

### Task 3: Alembic baseline and migrated test fixtures

**Files:**

- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/YYYYMMDDHHMMSS_create_downloads_and_settings.py`
- Create: `tests/conftest.py`

- [x] **Step 1: Initialize Alembic configuration**

`alembic/env.py` loads metadata from `app.models.Base.metadata`, reads the database URL from `app.config.settings`, and sets `render_as_batch` for SQLite.

`alembic.ini` configures the migration filename template:

```
file_template = %%(year)d%%(month).2d%%(day).2d%%(hour).2d%%(minute).2d%%(second).2d_%%(slug)s
```

- [x] **Step 2: Write the initial migration**

Revision ID: `20260609233000`
Filename: `20260609233000_create_downloads_and_settings.py`

Creates `downloads` and `settings` tables matching the ORM models. Uses `server_default` for boolean/float defaults instead of Python-level defaults so Alembic-generated DDL is self-contained.

- [x] **Step 3: Implement migrated test fixtures**

`tests/conftest.py`:

- sets `os.environ["YT_DATABASE_URL"]` at module load time (before any `app` module is imported) to a temp SQLite file
- `pytest_configure` runs `alembic upgrade head` once per session
- `db_engine` fixture: returns the shared engine
- `db_session` fixture: opens a connection + transaction, yields a Session, rollbacks after the test (isolation guarantee)
- `db_inspector` fixture: convenience wrapper
- Alembic config path is resolved from `Path(__file__).resolve().parents[1]` rather than the cwd

- [x] **Step 4: Add migration health test**

```python
def test_migrations_create_expected_tables(db_inspector):
    table_names = set(db_inspector.get_table_names())
    assert "downloads" in table_names
    assert "settings" in table_names
```

- [x] **Step 5: Run tests**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add alembic.ini alembic tests/conftest.py tests/test_db.py
git commit -m "feat: add alembic baseline migration and migrated test fixtures"
```

### Task 4: Minimal app startup and health route

**Files:**

- Create: `app/main.py`
- Create: `tests/test_health.py`

- [x] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [x] **Step 2: Implement startup flow**

`app/main.py`:

- computes `ALEMBIC_INI_PATH` from `Path(__file__).resolve()` (cwd-independent)
- lifespan ensures data dirs exist, runs `alembic upgrade head`, starts serving
- `/health` runs `SELECT 1`, returns 200 with `{"status": "ok"}` or 503 with `ErrorResponse`-compatible body

- [x] **Step 3: Run tests**

Run: `uv run pytest tests/test_health.py -v`
Expected: PASS

- [x] **Step 4: Commit**

```bash
git add app/main.py tests/test_health.py
git commit -m "feat: add migrated app startup and health endpoint"
```

## Post-Phase-1 Fixes (applied during review)

After the initial implementation, a code review uncovered the following issues that were fixed in a follow-up commit:

- **Missing baseline migration** — migration file was not tracked; created `20260609233000_create_downloads_and_settings.py`
- **Alembic `env.py`** — replaced default template with one that loads `app.models.Base.metadata` and `app.config.settings`
- **Alembic config path** — both `app/main.py` and `tests/conftest.py` now resolve `alembic.ini` relative to `__file__` instead of depending on cwd
- **`database_url` derives from `data_dir`** — unless overridden via `YT_DATABASE_URL`, the default URL is `sqlite:///{data_dir}/yourtube.db`
- **Ruff lint/format** — import sorting fixed, unused `Path` import removed, 5 files reformatted
- **Ty type-check pass** — `database_url` changed to `str = ""` + `model_validator(mode="before")` so type checker sees a non-optional field
- **Test DB isolation** — `db_session` fixture now wraps each test in a rollback-only transaction
- **CI workflow** — `.github/workflows/quality.yml` added with ruff, ty, pytest + coverage checks

## Current Test Suite (6 tests)

```
tests/test_config.py::test_settings_defaults                       PASSED
tests/test_config.py::test_database_url_defaults_to_data_dir       PASSED
tests/test_db.py::test_model_tables_named                          PASSED
tests/test_db.py::test_migrations_create_expected_tables           PASSED
tests/test_health.py::test_health                                  PASSED
tests/test_health.py::test_health_from_another_working_directory   PASSED
```

## Self-Review

- ✓ SQLAlchemy models only
- ✓ Alembic is the only schema authority; no `create_all()` in app code
- ✓ ORM models in `app/models.py`, API schemas in `app/schemas.py`
- ✓ Tests build schema via `alembic upgrade head`; migration health test proves it
- ✓ CI workflow runs ruff, ty, pytest with coverage on every push/PR

## End of Phase 1

Deliverable achieved: `uv run uvicorn app.main:app` starts successfully, `/health` returns `{"status":"ok"}`, and a fresh test database is built by Alembic migrations.
