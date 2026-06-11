# Phase 4: Docker Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the app for local deployment with Docker and Compose, preserving the existing application-owned migration startup flow.

**Architecture:** Docker and Compose package the FastAPI app, Alembic migrations, and persisted volumes. The container starts uvicorn directly on port `8000`, while the existing FastAPI lifespan remains the single place that runs `alembic upgrade head` before serving traffic.

**Tech Stack:** Docker, Docker Compose, uv, Alembic

---

> **Note:** The CI quality workflow (lint, types, tests, coverage) was already added in Phase 1
> as `.github/workflows/quality.yml`. This phase only covers Docker + Compose.

## File Structure (this phase adds)

```
yourtube/
├── Dockerfile
├── docker-compose.yml
└── .dockerignore
```

### Task 1: Container packaging

**Files:**

- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

Ignore:

- `.git/`
- `__pycache__/`
- `.env`
- `tests/`
- `plans/`

- [ ] **Step 2: Create `Dockerfile`**

Requirements:

- `python:3.12-slim`
- install `ffmpeg`, `curl`, `ca-certificates`
- install `uv`
- copy `pyproject.toml`, `uv.lock`, `alembic.ini`, `alembic/`, and `app/`
- run `uv sync --frozen --no-dev`
- create non-root user
- expose port `8000`

Boot command starts uvicorn directly and relies on the existing FastAPI lifespan to run migrations before serving traffic, for example:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

- [ ] **Step 3: Build the image**

Run: `docker build -t yourtube:latest .`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add container packaging with alembic startup"
```

### Task 2: Compose and runtime verification

**Files:**

- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

Include:

- port mapping `8000:8000`
- persistent volume for `/data`
- persistent volume for `/downloads`
- optional volume comments for `/cookies`
- environment defaults for `YT_HOST`, `YT_PORT`, `YT_DATA_DIR`, and `YT_DOWNLOADS_DIR`

- [ ] **Step 2: Verify fresh boot**

Run:

```bash
docker compose up -d
sleep 5
curl -fsS http://localhost:8000/health
docker compose logs
```

Expected:

- `/health` returns `{"status":"ok"}`
- logs show normal startup without schema boot failures on an empty data volume

- [ ] **Step 3: Shut down and commit**

```bash
docker compose down
git add docker-compose.yml
git commit -m "chore: add docker compose for persistent runtime"
```

## Self-Review (Phase 4)

- Docker includes Alembic artifacts.
- Boot flow still migrates before serving traffic, but migration ownership stays in application startup rather than a Docker wrapper command.
- CI quality workflow was already covered in Phase 1 (`.github/workflows/quality.yml`), not this phase.

## End of Phase 4

Deliverable: the app can boot from Docker against an empty data volume, self-migrate through the existing lifespan flow, and serve on `http://localhost:8000`.
