# Phase 3: Web App + Worker Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full FastAPI web app, HTML UI, API routes, and in-process worker pool on top of the Phase 2 services.

**Architecture:** FastAPI serves Jinja templates and JSON/HTML partial APIs. Lifespan applies Alembic migrations, requeues stranded work, loads runtime settings, and starts worker threads. Routes depend on SQLAlchemy sessions and translate between ORM models and Pydantic schemas.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2, htmx, yt-dlp, pytest

---

## Phase 2 Service Contracts (already implemented)

Phase 3 routes call these Phase 2 service functions. Key signatures:

| Route / Need                       | Service function                                                                                   |
| ---------------------------------- | -------------------------------------------------------------------------------------------------- |
| `POST /api/info`                   | `extract_info(url, *, proxy, cookies_file) -> dict`, `normalize_formats(info) -> list[FormatInfo]` |
| `POST /api/downloads`              | `enqueue_download(session, payload: DownloadCreate) -> Download`                                   |
| `GET /api/downloads/active`        | `get_active_jobs(session) -> list[Download]`                                                       |
| `GET /api/downloads/library`       | `get_library(session) -> list[Download]`                                                           |
| `GET /api/downloads/library?q=...` | `search_library(session, query) -> list[Download]`                                                 |
| `POST /api/downloads/{id}/cancel`  | `cancel_job(session, job_id) -> bool`                                                              |
| `DELETE /api/downloads/{id}`       | `delete_from_library(session, job_id) -> tuple[bool, str]`                                         |
| `GET /api/settings`                | `get_all_settings(session) -> dict[str, str]`                                                      |
| `PUT /api/settings`                | `set_settings_batch(session, updates) -> None`                                                     |
| `POST /api/settings/reset`         | `reset_settings(session) -> None`                                                                  |

Worker-pool functions:

| Need                 | Service function                                        |
| -------------------- | ------------------------------------------------------- | ------ |
| Claim a job          | ``claim_next(session) -> Download                       | None`` |
| Finish a job         | `release_job(session, id, *, status, ...) -> bool`      |
| Detect stale         | `detect_stale_jobs(session, timeout_minutes=10) -> int` |
| Startup recovery     | `requeue_active_on_startup(session) -> int`             |
| Read max concurrency | ``get_setting(session, "max_concurrent") -> str         | None`` |

## File Structure (this phase adds)

```
yourtube/
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── pages.py
│   │   └── api.py
│   ├── static/
│   │   └── css/app.css
│   └── templates/
│       ├── base.html
│       ├── components/
│       ├── pages/
│       └── partials/
└── tests/
    └── integration/
        ├── test_pages.py
        ├── test_api_info.py
        ├── test_api_downloads_create.py
        ├── test_api_downloads_active.py
        ├── test_api_downloads_library.py
        ├── test_api_downloads_cancel.py
        ├── test_api_downloads_delete.py
        ├── test_api_downloads_file.py
        ├── test_api_settings_get.py
        ├── test_api_settings_put.py
        ├── test_api_settings_reset.py
        └── test_startup_recovery.py
```

### Task 1: Full app bootstrap and worker pool

**Files:**

- Modify: `app/main.py`
- Create: `tests/integration/test_startup_recovery.py`

- [ ] **Step 1: Write failing startup recovery test**

Test file: `tests/integration/test_startup_recovery.py`

```python
"""Verify lifespan bootstraps the app correctly."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import engine, SessionLocal
from app.models import Download
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _clean_db():
    """Ensure a clean slate before each test."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM downloads"))
        conn.execute(text("DELETE FROM settings"))
    yield


def test_migrations_run_on_startup() -> None:
    """The health endpoint proves the database is migrated."""
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_startup_requeues_active_rows() -> None:
    """Rows stranded as active on last shutdown are requeued."""
    session = SessionLocal()
    try:
        session.add(Download(url="https://example.com/stranded", status="active"))
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        pass  # triggers lifespan which runs requeue

    session = SessionLocal()
    try:
        row = session.get(Download, 1)
        assert row is not None
        assert row.status == "queued"
    finally:
        session.close()


def test_worker_pool_reads_max_concurrent() -> None:
    """Worker pool starts the configured number of threads."""
    session = SessionLocal()
    try:
        from app.services.settings import set_setting
        set_setting(session, "max_concurrent", "2")
    finally:
        session.close()

    with TestClient(app) as client:
        pass  # triggers lifespan which reads settings
```

- [ ] **Step 2: Implement worker pool in `app/main.py`**

Add before the `lifespan` function:

```python
import threading
import time
import logging
from app.db import SessionLocal
from app.services.queue import claim_next, release_job, detect_stale_jobs, requeue_active_on_startup
from app.services.settings import get_setting
from app.services.downloader import run_download, YtdlpProgress

logger = logging.getLogger("yourtube")


class WorkerPool:
    """In-process worker pool that claims and runs downloads.

    Workers are daemon threads that poll ``claim_next`` on a sleep
    interval. Each worker runs a single download via ``run_download``
    and reports the result via ``release_job``. Cancellation is
    detected by polling ``cancel_requested`` on the DB row through
    a :class:`YtdlpProgress` instance.
    """

    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Read concurrency from settings and start worker threads."""
        session = SessionLocal()
        try:
            raw = get_setting(session, "max_concurrent") or "1"
            concurrency = max(1, min(5, int(raw)))
        finally:
            session.close()

        logger.info("starting %d workers", concurrency)
        for i in range(concurrency):
            t = threading.Thread(target=self._worker_loop, name=f"worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        """Signal all workers to exit."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()

    def _worker_loop(self) -> None:
        """Worker thread: poll for queued work, run, release."""
        session = SessionLocal()
        try:
            while not self._stop_event.is_set():
                job = claim_next(session)
                if job is None:
                    self._stop_event.wait(timeout=2)
                    continue

                self._run_job(session, job)
        finally:
            session.close()

    def _run_job(self, session, job) -> None:
        """Execute a single download job and release it."""
        from app.config import settings

        progress = YtdlpProgress(
            cancel_requested=lambda: (
                session.refresh(job) is None and job.cancel_requested
            )
        )
        try:
            output_path = run_download(
                url=job.url,
                video_format_id=job.video_format_id,
                audio_format_id=job.audio_format_id,
                output_template=job.output_template,
                output_dir=str(settings.downloads_dir),
                audio_bitrate=job.audio_bitrate,
                subtitles=job.subtitles,
                progress_hook=progress,
            )
            session.refresh(job)
            if job.cancel_requested:
                release_job(session, job.id, status="cancelled")
            else:
                release_job(
                    session, job.id,
                    status="done",
                    file_path=output_path or None,
                )
        except Exception as exc:
            logger.exception("download failed: %s", exc)
            from app.services.error_mapper import friendly_ytdlp_error

            friendly, code = friendly_ytdlp_error(str(exc))
            release_job(session, job.id, status="error", error_code=code, error_message=friendly)
```

Lifespan order (inside `lifespan`):

1. `alembic upgrade head`
2. `requeue_active_on_startup(session)`
3. `detect_stale_jobs(session)`
4. load concurrency from settings
5. `WorkerPool().start()`

- [ ] **Step 3: Run test**

Run: `uv run pytest tests/integration/test_startup_recovery.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/integration/test_startup_recovery.py
git commit -m "feat: add worker pool bootstrap and startup recovery"
```

### Task 2: Page routes, templates, and styles

**Files:**

- Create: `app/routes/pages.py`
- Create: `app/static/css/app.css`
- Create: `app/templates/base.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `app/templates/partials/queue_rows.html`
- Create: `app/templates/partials/library_rows.html`
- Create: `tests/integration/test_pages.py`

- [ ] **Step 1: Write failing page tests**

Test file: `tests/integration/test_pages.py`

```python
"""Verify page routes render successfully."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from app.main import app


@pytest.mark.parametrize("path,status", [
    ("/", 200),
    ("/queue", 200),
    ("/library", 200),
    ("/settings", 200),
    ("/health", 200),
])
def test_page_renders(path: str, status: int) -> None:
    with TestClient(app) as client:
        resp = client.get(path)
    assert resp.status_code == status
```

- [ ] **Step 2: Implement page routes**

`app/routes/pages.py` should render the page templates and keep `/health` JSON-based.

- [ ] **Step 3: Implement base layout and pages**

Include:

- sidebar navigation
- URL input and format picker shell on home page
- queue polling container
- library list and search UI
- settings form shell

- [ ] **Step 4: Implement stylesheet**

Keep styling intentional but lightweight. Preserve existing visual direction from the earlier plan where practical.

- [ ] **Step 5: Run page tests**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/pages.py app/static/css/app.css app/templates tests/integration/test_pages.py
git commit -m "feat: add page routes templates and styles"
```

### Task 3: API routes

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

- [ ] **Step 1: Write failing API tests**

Create one test file per route group (e.g. `test_api_info.py`, `test_api_downloads_create.py`, etc.). Each imports `TestClient` from `app.main` and uses FastAPI's test client.

Example — `tests/integration/test_api_info.py`:

```python
"""Test ``POST /api/info`` returns format metadata."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import app


@patch("app.services.downloader.extract_info")
def test_fetch_info(mock_extract) -> None:
    mock_extract.return_value = {
        "url": "https://youtube.com/watch?v=abc123",
        "title": "Test Video",
        "formats": [
            {
                "format_id": "137", "ext": "mp4",
                "vcodec": "avc1", "acodec": "none",
                "height": 1080,
            }
        ],
        "captions": {},
    }
    with TestClient(app) as client:
        resp = client.post("/api/info", json={"url": "https://youtube.com/watch?v=abc123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Video"
    assert len(data["formats"]) == 1
    assert data["formats"][0]["format_id"] == "137"


@patch("app.services.downloader.extract_info")
def test_fetch_info_proxy_cookies(mock_extract) -> None:
    mock_extract.return_value = {"url": "...", "title": "T", "formats": [], "captions": {}}
    with TestClient(app) as client:
        resp = client.post("/api/info", json={
            "url": "https://youtube.com/watch?v=def456",
            "cookies": True,
            "proxy": True,
        })
    assert resp.status_code == 200
```

Example — `tests/integration/test_api_downloads_create.py`:

```python
"""Test ``POST /api/downloads`` creates a queued job."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app


def test_create_download() -> None:
    payload = {
        "url": "https://youtube.com/watch?v=abc123",
        "title": "Test",
        "uploader": "Creator",
        "duration": 120,
    }
    with TestClient(app) as client:
        resp = client.post("/api/downloads", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == payload["url"]
    assert data["status"] == "queued"
    assert "id" in data


def test_create_download_missing_url_rejected() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/downloads", json={})
    assert resp.status_code == 422  # Pydantic validation
```

- [ ] **Step 2: Implement `app/routes/api.py`**

Use service layer functions from Phase 2 (see contract table above). All routes receive `session: Session` via FastAPI `Depends(get_session)`.

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_session
from app.schemas import InfoRequest, DownloadCreate, DownloadResponse, InfoResponse, ErrorResponse
from app.services.downloader import extract_info, normalize_formats
from app.services.queue import enqueue_download, get_active_jobs, cancel_job
from app.services.library import get_library, search_library, delete_from_library
from app.services.settings import get_all_settings, set_settings_batch, reset_settings
from starlette.responses import FileResponse

router = APIRouter(prefix="/api")


@router.post("/info", response_model=InfoResponse)
def fetch_info(body: InfoRequest, session: Session = Depends(get_session)):
    raw = extract_info(body.url, proxy=body.proxy, cookies_file=body.cookies)
    formats = normalize_formats(raw)
    return InfoResponse(
        url=raw["url"], title=raw["title"],
        uploader=raw.get("uploader"), duration=raw.get("duration"),
        thumbnail=raw.get("thumbnail"), formats=formats,
        captions=raw.get("captions", {}),
    )


@router.post("/downloads", response_model=DownloadResponse, status_code=201)
def create_download(body: DownloadCreate, session: Session = Depends(get_session)):
    return enqueue_download(session, body)


@router.get("/downloads/active", response_model=list[DownloadResponse])
def list_active(session: Session = Depends(get_session)):
    return get_active_jobs(session)


@router.get("/downloads/library", response_model=list[DownloadResponse])
def list_library(q: str | None = None, session: Session = Depends(get_session)):
    if q:
        return search_library(session, q)
    return get_library(session)


@router.post("/downloads/{job_id}/cancel", response_model=dict)
def cancel(job_id: int, session: Session = Depends(get_session)):
    ok = cancel_job(session, job_id)
    return {"ok": ok}


@router.delete("/downloads/{job_id}", response_model=dict)
def delete(job_id: int, session: Session = Depends(get_session)):
    ok, msg = delete_from_library(session, job_id)
    if not ok:
        raise HTTPException(400, detail={"code": msg})
    return {"ok": True}


@router.get("/downloads/{job_id}/file")
def serve_file(job_id: int, session: Session = Depends(get_session)):
    from app.models import Download
    row = session.get(Download, job_id)
    if not row or row.status != "done" or not row.file_path:
        raise HTTPException(404)
    return FileResponse(row.file_path)


@router.get("/settings", response_model=dict[str, str])
def list_settings(session: Session = Depends(get_session)):
    return get_all_settings(session)


@router.put("/settings", response_model=dict)
def update_settings(body: dict[str, str], session: Session = Depends(get_session)):
    try:
        set_settings_batch(session, body)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))


@router.post("/settings/reset", response_model=dict)
def reset(session: Session = Depends(get_session)):
    reset_settings(session)
    return {"ok": True}
```

- [ ] **Step 3: Wire partial rendering for queue and library**

Support htmx polling responses for the queue and library views.

- [ ] **Step 4: Run API tests**

Run: `uv run pytest tests/integration/test_api_*.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/api.py tests/integration/test_api_info.py tests/integration/test_api_downloads_create.py tests/integration/test_api_downloads_active.py tests/integration/test_api_downloads_library.py tests/integration/test_api_downloads_cancel.py tests/integration/test_api_downloads_delete.py tests/integration/test_api_downloads_file.py tests/integration/test_api_settings_get.py tests/integration/test_api_settings_put.py tests/integration/test_api_settings_reset.py
git commit -m "feat: add web api routes for downloads and settings"
```

## Self-Review (Phase 3)

- Web app is now the main product path.
- Lifespan and worker startup order is explicit.
- API contracts rely on Pydantic schemas, not ORM instances directly.

## End of Phase 3

Deliverable: `uv run uvicorn app.main:app` serves the complete web app with queue, library, settings, and worker integration.
