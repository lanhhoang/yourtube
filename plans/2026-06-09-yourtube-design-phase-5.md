# Phase 5: DevOps (Docker + CI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize the YourTube app with Docker and Docker Compose. After this phase, `docker compose up -d` serves the complete application from a container with health checks, persistent volumes, and proper resource limits.

**Architecture:** Python 3.12-slim base image with ffmpeg installed. Uses uv for dependency management (same as local dev). Multi-stage not needed — single stage with dev dependencies excluded. Docker Compose provides volume mounts for data persistence.

**Prerequisites:** Phases 1-4 must be complete (full web app running locally). The CI workflow was already created in Phase 1 — just verify it still passes.

**Tech Stack:** Docker, Docker Compose, uv, python:3.12-slim, ffmpeg

---

## File Structure (this phase adds)

```
yourtube/
├── Dockerfile                  ★ NEW
├── docker-compose.yml          ★ NEW
└── .dockerignore               ★ NEW
```

---

### Task 5.1: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create .dockerignore**

```
.git/
.gitignore
__pycache__/
*.pyc
.env
.env.local
tests/
plans/
docs/
README.md
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

# Install system deps: ffmpeg (for muxing), curl (for healthcheck), ca-certificates
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Create app user (non-root)
RUN groupadd --system --gid 1000 appuser \
 && useradd  --system --uid 1000 --gid appuser --home /app --shell /sbin/nologin appuser

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY app ./app

# Create data directories with correct ownership
RUN mkdir -p /data /downloads /cookies \
 && chown -R appuser:appuser /data /downloads /cookies

# Switch to non-root user
USER appuser

# Default environment variables
ENV YT_HOST=0.0.0.0 \
    YT_PORT=8000 \
    YT_DATA_DIR=/data \
    YT_DOWNLOADS_DIR=/downloads \
    YT_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

- [ ] **Step 3: Build the image**

```bash
docker build -t yourtube:latest .
```
Expected: Build succeeds. First build may take a few minutes (pip install + ffmpeg).

- [ ] **Step 4: Verify the image**

```bash
docker run --rm -p 8000:8000 yourtube:latest &
sleep 5
curl -fsS http://localhost:8000/health
# Docker: stop container
docker ps -q --filter ancestor=yourtube:latest | xargs docker stop
```
Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile with uv, ffmpeg, non-root user, healthcheck"
```

---

### Task 5.2: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

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

- [ ] **Step 2: Start with Compose**

```bash
docker compose up -d
sleep 3
curl -fsS http://localhost:8000/health
docker compose logs
```
Expected: `{"status":"ok"}`. Logs show migrations running and worker starting.

- [ ] **Step 3: Verify the full UI is served from container**

```bash
curl -s http://localhost:8000/ | head -5
curl -s http://localhost:8000/queue | head -3
curl -s http://localhost:8000/settings | grep -c "hx-put"
```
Expected: HTML content returned, settings page has htmx attributes.

- [ ] **Step 4: Test health check in Docker**

```bash
docker inspect yourtube --format='{{json .State.Health}}' | python3 -m json.tool
```
Expected: Health status shows "healthy".

- [ ] **Step 5: Shut down**

```bash
docker compose down
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add Docker Compose with persistent volumes and resource limits"
```

---

### Task 5.3: Verify CI Still Passes

**Files:**
- Verify: `.github/workflows/ci.yml`

- [ ] **Step 1: Run CI checks locally**

```bash
uv sync --all-extras
uv run ruff check .
uv run ty check app
uv run pytest --cov=app --cov-fail-under=80
```
Expected: All pass. If coverage is below 80%, add missing tests.

- [ ] **Step 2: Check coverage gaps (if any)**

```bash
uv run pytest --cov=app --cov-report=term-missing
```
If coverage < 80%, add tests for uncovered lines in the appropriate test files.

Likely coverage gaps after Phase 4:
- `app/routes/api.py`: some error paths (404, 409 responses)
- `app/services/downloader.py`: `run_download` with ffmpeg mux (hard to unit test without real download)

To fix low coverage without fragile tests, add:

```python
# tests/unit/test_api_error_paths.py
from unittest.mock import patch
from app.models import Download


def test_get_download_404(client):
    r = client.get("/api/downloads/99999")
    assert r.status_code == 404


def test_cancel_done_job_409(client, db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        d = Download(url="https://youtube.com/watch?v=test", status="done")
        session.add(d)
        session.commit()
        job_id = d.id

    with Session(db_engine) as session:
        from app.services.queue import cancel_job
        assert not cancel_job(session, job_id)
```

- [ ] **Step 3: Final CI verification**

```bash
uv run pytest --cov=app --cov-fail-under=80 -q
```
Expected: `required test coverage of 80% reached`

- [ ] **Step 4: Commit any coverage fixes**

```bash
git add tests/unit/test_api_error_paths.py  # if created
git commit -m "test: add coverage for API error paths"
```

---

## Self-Review (Phase 5)

**Spec coverage:**
- ✓ Dockerfile: python:3.12-slim, ffmpeg, uv, non-root user, health check
- ✓ Docker Compose: single service, persistent volume, resource limits
- ✓ .dockerignore: excludes tests, docs, plans, git, __pycache__
- ✓ CI still passes with 80% coverage

**Placeholder scan:** No TBD, TODO, or incomplete sections.

**Type consistency:** Dockerfile uses `app.main:app` which matches the existing app entry point. `YT_DATA_DIR=/data` maps to compose volume `yourtube-data:/data`.

---

## End of Phase 5

Deliverable: `docker compose up -d` builds and starts the containerized YourTube on port 8000. The app is identical to the Phase 4 web UI but runs in a container with:
- Persistent SQLite data via Docker volume
- Automatic restart unless stopped
- Health check every 30 seconds
- CPU limit of 2 cores, memory limit of 1 GB
- Non-root user (uid 1000)
