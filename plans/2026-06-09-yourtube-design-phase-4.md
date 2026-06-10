# Phase 4: Packaging + CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the app for local deployment and CI with Alembic-aware startup and verification.

**Architecture:** Docker and Compose package the FastAPI app, Alembic migrations, and persisted volumes. Container boot runs migrations before serving the web process. CI verifies lint, typing, tests, and migration health together.

**Tech Stack:** Docker, Docker Compose, uv, Alembic, GitHub Actions

---

## File Structure (this phase adds)

```
yourtube/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── .github/workflows/ci.yml
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

Boot command must run migrations before starting uvicorn, for example:

```bash
uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
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
- optional volume comments for `/downloads` and `/cookies`
- environment defaults for `YT_DATA_DIR` and `YT_DOWNLOADS_DIR`

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
- logs show migrations applied before app startup

- [ ] **Step 3: Shut down and commit**

```bash
docker compose down
git add docker-compose.yml
git commit -m "chore: add docker compose for persistent runtime"
```

### Task 3: CI and migration health

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

CI must run:

```bash
uv sync --all-extras
uv run ruff check .
uv run ty check app
uv run pytest --cov=app --cov-fail-under=80
uv run alembic upgrade head
```

- [ ] **Step 2: Verify CI locally**

Run the same commands locally.
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add ci checks for lint tests and migrations"
```

## Self-Review (Phase 4)

- Docker now includes Alembic artifacts.
- Boot flow migrates before serving traffic.
- CI verifies schema health explicitly.

## End of Phase 4

Deliverable: the app can boot from Docker against an empty data volume and self-migrate successfully.
