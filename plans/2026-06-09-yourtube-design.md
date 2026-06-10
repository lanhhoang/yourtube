# YourTube Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted YouTube downloader web app with persistent queue, library, settings, and worker-driven downloads using SQLAlchemy and Alembic.

**Architecture:** FastAPI serves HTML pages and JSON endpoints. SQLAlchemy 2.x owns persistence, Alembic owns schema creation and upgrades, and Pydantic schemas define request/response contracts. A single-process worker pool claims queued jobs from SQLite and runs yt-dlp plus ffmpeg.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Pydantic Settings, Jinja2, htmx, yt-dlp, curl-cffi, uv, ruff, ty, pytest

---

## Why This Replan Replaces The Old One

- The old plan used `SQLModel.metadata.create_all()` and a custom `schema_version` table, which conflicts with proper migration ownership.
- The queue plan claimed atomic job acquisition but described a race-prone read-then-write implementation.
- The middle phases were CLI-heavy even though the product target is the web app.

This plan removes those flaws:

- `SQLModel` is fully replaced by `SQLAlchemy`.
- `Alembic` is the only schema authority.
- Queue claiming is transaction-safe by design.
- Delivery is web-first and reduced to 4 phases.

## File Structure

```
yourtube/
├── pyproject.toml
├── uv.lock
├── .env.example
├── alembic.ini
├── .github/workflows/quality.yml        ← pre-added from Phase 4
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py
│   │   └── api.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── downloader.py
│   │   ├── error_mapper.py
│   │   ├── settings.py
│   │   ├── queue.py
│   │   └── library.py
│   ├── templates/
│   └── static/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── YYYYMMDDHHMMSS_action_object.py     # naming convention
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    └── integration/
```

## Phase Overview

### Phase 1 ✅ Complete

- Scaffold the app.
- Add SQLAlchemy models and Pydantic schemas.
- Add Alembic and the baseline migration (timestamped filename convention).
- Make tests create schema by running migrations.
- Add CI quality workflow (lint, type check, tests, coverage).

See: `plans/2026-06-09-yourtube-design-phase-1.md`

### Phase 2 ✅ Complete

- Build backend services (error mapping, settings, downloader, queue, library).
- Stay web-facing, not CLI-facing.
- Lock down queue state transitions and atomic claim semantics.
- **85 tests, 91.77% coverage** across all service modules.
- Review findings addressed: real `YtdlpProgress`, active-only `release_job` guard, atomic two-session claim test, deterministic ordering by `(created_at, id)`, safe file-delete failure handling.

See: `plans/2026-06-09-yourtube-design-phase-2.md`

### Phase 3

- Build the full FastAPI app, templates, routes, and worker pool.
- Apply migrations on startup before worker recovery.
- Verify queue, library, settings, and file-serving behavior end-to-end.

See: `plans/2026-06-09-yourtube-design-phase-3.md`

### Phase 4

- Package the app with Docker and Compose.
- Ensure Alembic migrations run in container boot flow.
- CI was already added in Phase 1; this phase only needs Docker + Compose.

See: `plans/2026-06-09-yourtube-design-phase-4.md`

## Core Design Rules

- No `SQLModel` anywhere in code or tests.
- No runtime `create_all()` in app code.
- No custom schema version table.
- Routes use Pydantic schemas, not ORM instances as API contracts.
- Test databases are initialized by `alembic upgrade head`.
- Uvicorn runs with one process; download concurrency is handled by in-process worker threads.

## Queue Ownership Contract

Queue claim must be safe under concurrent workers:

1. Open a write transaction.
2. Select the oldest queued, non-cancelled job candidate.
3. Update that row: set `status = 'active'` and `claimed_at = now()` with a conditional `WHERE status = 'queued'`.
4. Only treat the claim as successful if exactly one row was updated.

Terminal states:

| State       | Description                   |
| ----------- | ----------------------------- |
| `queued`    | Waiting for a worker to claim |
| `active`    | Being downloaded              |
| `done`      | Completed successfully        |
| `error`     | Download failed               |
| `cancelled` | Cancelled before completion   |

**Cancel contract:**

- `cancel_job()` on a `queued` job transitions immediately to `cancelled`.
- `cancel_job()` on an `active` job sets `cancel_requested = True`; the worker thread polls this flag, stops the download, and transitions to `cancelled`.
- `cancel_job()` on `done`, `error`, or `cancelled` returns `False` (no-op).

**Stale detection:**

- `detect_stale_jobs(timeout_minutes=10)` marks any `active` row whose `claimed_at` is older than the timeout as `error` with code `stale_worker`.

## Settings Catalog

Runtime settings persisted in the `settings` table and consumed by the worker pool and API routes:

| Key              | Default | Validation             | Description                    |
| ---------------- | ------- | ---------------------- | ------------------------------ |
| `max_concurrent` | `"1"`   | integer 1-5            | Max simultaneous downloads     |
| `proxy_url`      | `""`    | string (URL or empty)  | HTTP proxy for yt-dlp          |
| `cookies_path`   | `""`    | string (path or empty) | Path to cookies.txt for yt-dlp |
| `downloads_dir`  | `""`    | string (path or empty) | Output directory override      |

Empty-string values are treated as unset and passed as `None` to yt-dlp. The settings service validates `max_concurrent` on write; other keys accept any string but empty means unset.

Startup behavior:

- run Alembic migrations
- requeue stranded `active` rows
- load concurrency settings
- start worker threads

## Acceptance Criteria

- `/health` works against a migrated SQLite database.
- The queue supports enqueue, claim, progress, cancel, stale recovery, and startup recovery.
- `/api/info` returns the format data needed by the format picker.
- `/api/downloads` creates queue entries and `/api/downloads/{id}/file` serves completed files.
- The settings page persists to the database.
- `docker compose up` boots a fresh database and self-migrates.
- CI fails if migrations are broken or omitted.

## Design Decisions

**Migration naming convention:** All Alembic revision files use `YYYYMMDDHHMMSS_action_object.py` (configured via `file_template` in `alembic.ini`).

The first migration is `20260609233000_create_downloads_and_settings.py`.

**Database URL:** Defaults to `sqlite:///{data_dir}/yourtube.db`, deriving from `YT_DATA_DIR` unless `YT_DATABASE_URL` is explicitly set.

**Alembic config path:** Always resolved by `Path(__file__).resolve().parents[1] / "alembic.ini"` so the app works from any working directory.

**CI quality workflow:** Added in Phase 1. Runs ruff, ty, pytest with coverage on every push/PR to `master`. Threshold is 50% (Phase 1 baseline ~62%). Raise to 80% after Phase 4.

## Self-Review Checklist

- Spec coverage:
  - persistence and migrations -> Phase 1
  - backend services -> Phase 2
  - web routes, templates, workers -> Phase 3
  - Docker -> Phase 4
  - CI -> Phase 1 (pre-added)
- Placeholder scan: no `SQLModel`, no CLI-first milestones, no custom schema version flow remain.
- Type consistency:
  - `Download` and `Setting` are ORM models
  - request and response types live in `app/schemas.py`
  - queue service functions accept SQLAlchemy `Session`

## Execution Handoff

Plan complete and saved to `plans/2026-06-09-yourtube-design.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
