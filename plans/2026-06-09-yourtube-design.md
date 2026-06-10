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
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .github/workflows/ci.yml
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
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    └── integration/
```

## Phase Overview

### Phase 1

- Scaffold the app.
- Add SQLAlchemy models and Pydantic schemas.
- Add Alembic and the baseline migration.
- Make tests create schema by running migrations.

See: `plans/2026-06-09-yourtube-design-phase-1.md`

### Phase 2

- Build backend services.
- Keep them web-facing, not CLI-facing.
- Lock down queue state transitions and atomic claim semantics.

See: `plans/2026-06-09-yourtube-design-phase-2.md`

### Phase 3

- Build the full FastAPI app, templates, routes, and worker pool.
- Apply migrations on startup before worker recovery.
- Verify queue, library, settings, and file-serving behavior end-to-end.

See: `plans/2026-06-09-yourtube-design-phase-3.md`

### Phase 4

- Package the app with Docker and Compose.
- Ensure Alembic migrations run in container boot flow.
- Verify lint, typing, tests, and migration health in CI.

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
3. Update that row with a conditional `WHERE status = 'queued'`.
4. Only treat the claim as successful if exactly one row was updated.

Terminal states:

- `queued`
- `active`
- `done`
- `error`
- `cancelled`

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

## Self-Review Checklist

- Spec coverage:
  - persistence and migrations -> Phase 1
  - backend services -> Phase 2
  - web routes, templates, workers -> Phase 3
  - Docker and CI -> Phase 4
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
