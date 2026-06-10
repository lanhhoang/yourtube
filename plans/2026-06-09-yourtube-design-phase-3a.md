# Phase 3A: Backend App + Worker Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend bootstrap, worker pool, runtime settings resolution, and JSON APIs on top of the completed Phase 2 services.

**Architecture:** Lifespan remains the integration boundary: it ensures directories exist, runs Alembic migrations, requeues stranded work, resolves runtime settings, and starts an in-process worker pool. JSON routes stay thin and call Phase 2 services plus one additive progress helper, while worker threads use short-lived SQLAlchemy sessions and explicit cancellation handling.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Starlette responses, yt-dlp, pytest

---

## File Structure

```
yourtube/
├── app/
│   ├── main.py
│   ├── schemas.py
│   ├── routes/
│   │   └── api.py
│   └── services/
│       ├── downloader.py
│       ├── queue.py
│       └── settings.py
└── tests/
    └── integration/
        ├── test_startup_recovery.py
        ├── test_worker_pool.py
        ├── test_api_info.py
        ├── test_api_downloads.py
        └── test_api_settings.py
```

Responsibilities:

- `app/main.py` owns lifespan, worker startup/shutdown, and app wiring.
- `app/routes/api.py` owns JSON-only HTTP contracts.
- `app/services/queue.py` gains the minimal additive helper required to persist progress.
- `app/services/settings.py` remains the source of persisted runtime settings.
- `tests/integration/` verifies startup behavior, worker behavior, and route contracts end to end.

### Task 1: Add progress persistence and runtime setting resolution helpers

**Files:**
- Modify: `app/services/queue.py`
- Modify: `app/services/settings.py`
- Create: `tests/unit/test_queue_progress.py`
- Create: `tests/unit/test_settings_runtime_resolution.py`

- [ ] **Step 1: Write the failing queue progress test**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download, update_progress


def test_update_progress_persists_percent_for_active_job(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/video"))
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session.commit()

    changed = update_progress(db_session, row.id, 42.5)

    assert changed is True
    db_session.refresh(row)
    assert row.progress == 42.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_queue_progress.py::test_update_progress_persists_percent_for_active_job -v`
Expected: FAIL with `ImportError` or `AttributeError` for `update_progress`

- [ ] **Step 3: Write the failing runtime settings resolution tests**

```python
from __future__ import annotations

from pathlib import Path

from app.services.settings import resolve_runtime_settings, set_settings_batch


def test_resolve_runtime_settings_prefers_saved_download_dir(db_session, tmp_path: Path) -> None:
    saved_dir = tmp_path / "saved-downloads"
    set_settings_batch(db_session, {"downloads_dir": str(saved_dir)})

    resolved = resolve_runtime_settings(db_session)

    assert resolved.downloads_dir == saved_dir


def test_resolve_runtime_settings_uses_defaults_when_setting_blank(db_session) -> None:
    resolved = resolve_runtime_settings(db_session)

    assert resolved.proxy_url is None
    assert resolved.cookies_path is None
    assert resolved.max_concurrent == 1
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_queue_progress.py tests/unit/test_settings_runtime_resolution.py -v`
Expected: FAIL because `update_progress` and `resolve_runtime_settings` do not exist

- [ ] **Step 5: Write minimal implementation**

```python
# app/services/queue.py
def update_progress(session: Session, job_id: int, percent: float) -> bool:
    clamped = max(0.0, min(100.0, float(percent)))
    stmt = (
        update(Download)
        .where(Download.id == job_id, Download.status == "active")
        .values(progress=clamped)
    )
    result = session.execute(stmt)
    session.commit()
    return bool(result.rowcount)
```

```python
# app/services/settings.py
from dataclasses import dataclass
from pathlib import Path

from app.config import settings as app_settings


@dataclass(frozen=True)
class RuntimeSettings:
    max_concurrent: int
    proxy_url: str | None
    cookies_path: Path | None
    downloads_dir: Path


def resolve_runtime_settings(session: Session) -> RuntimeSettings:
    saved = get_all_settings(session)
    max_concurrent = int(saved["max_concurrent"] or "1")
    downloads_dir = Path(saved["downloads_dir"]) if saved["downloads_dir"] else app_settings.downloads_dir
    proxy_url = saved["proxy_url"] or app_settings.proxy_url
    cookies_path = Path(saved["cookies_path"]) if saved["cookies_path"] else app_settings.cookies_path
    return RuntimeSettings(
        max_concurrent=max(1, min(5, max_concurrent)),
        proxy_url=proxy_url or None,
        cookies_path=cookies_path,
        downloads_dir=downloads_dir,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_queue_progress.py tests/unit/test_settings_runtime_resolution.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/queue.py app/services/settings.py tests/unit/test_queue_progress.py tests/unit/test_settings_runtime_resolution.py
git commit -m "feat: add progress persistence and runtime settings resolution"
```

### Task 2: Add lifespan startup recovery and worker pool

**Files:**
- Modify: `app/main.py`
- Modify: `app/services/downloader.py`
- Create: `tests/integration/test_startup_recovery.py`
- Create: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Write the failing startup and worker tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download


def test_startup_requeues_active_rows(db_session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/stranded"))
    db_session.execute(
        Download.__table__.update().where(Download.id == row.id).values(status="active")
    )
    db_session.commit()

    with TestClient(app):
        pass

    db_session.refresh(row)
    assert row.status == "queued"
```

```python
from __future__ import annotations

from app.models import Download
from app.schemas import DownloadCreate
from app.services.downloader import DownloadCancelled
from app.services.queue import enqueue_download


def test_worker_cancelled_download_ends_cancelled(monkeypatch, db_session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/cancel"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    db_session.commit()

    def fake_run_download(**_kwargs):
        raise DownloadCancelled("cancelled by user")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session.refresh(row)
    assert row.status == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py -v`
Expected: FAIL because no worker pool or startup recovery integration exists

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/downloader.py
class YtdlpProgress:
    def __init__(
        self,
        cancel_requested: Callable[[], bool] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> None:
        self.cancel_requested = cancel_requested
        self.on_progress = on_progress
        self.percent: float | None = None
        self.filename: str | None = None

    def __call__(self, d: dict[str, Any]) -> None:
        if self.cancel_requested is not None and self.cancel_requested():
            raise DownloadCancelled("cancelled by user")
        percent = parse_percent(d.get("_percent_str"))
        if percent is not None:
            self.percent = percent
            if self.on_progress is not None:
                self.on_progress(percent)
        if d.get("status") == "finished" and d.get("filename"):
            self.filename = str(d["filename"])
```

```python
# app/main.py
class WorkerPool:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def start(self, concurrency: int) -> None:
        for index in range(concurrency):
            thread = threading.Thread(target=self._worker_loop, name=f"worker-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            with SessionLocal() as session:
                job = claim_next(session)
            if job is None:
                self._stop_event.wait(1.0)
                continue
            self._run_job(job.id)

    def _run_job(self, job_id: int) -> None:
        with SessionLocal() as session:
            runtime = resolve_runtime_settings(session)
            job = session.get(Download, job_id)
            if job is None:
                return
            progress = YtdlpProgress(
                cancel_requested=lambda: _cancel_requested(job_id),
                on_progress=lambda pct: _persist_progress(job_id, pct),
            )
            try:
                output_path = run_download(
                    url=job.url,
                    video_format_id=job.video_format_id,
                    audio_format_id=job.audio_format_id,
                    output_template=job.output_template,
                    output_dir=str(runtime.downloads_dir),
                    audio_bitrate=job.audio_bitrate,
                    proxy=runtime.proxy_url,
                    cookies_file=str(runtime.cookies_path) if runtime.cookies_path else None,
                    subtitles=job.subtitles,
                    progress_hook=progress,
                )
            except DownloadCancelled:
                release_job(session, job_id, status="cancelled")
                return
            except Exception as exc:
                code, message = friendly_ytdlp_error(str(exc))
                release_job(session, job_id, status="error", error_code=code, error_message=message)
                return
            release_job(session, job_id, status="done", file_path=output_path or None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/services/downloader.py tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py
git commit -m "feat: add backend startup recovery and worker pool"
```

### Task 3: Add JSON APIs for info, downloads, files, and settings

**Files:**
- Create: `app/routes/api.py`
- Modify: `app/main.py`
- Modify: `app/schemas.py`
- Modify: `app/services/settings.py`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads.py`
- Create: `tests/integration/test_api_settings.py`

- [ ] **Step 1: Write the failing API tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_create_download_returns_201() -> None:
    with TestClient(app) as client:
        response = client.post("/api/downloads", json={"url": "https://example.com/video"})
    assert response.status_code == 201
    assert response.json()["status"] == "queued"


def test_settings_reject_unknown_keys() -> None:
    with TestClient(app) as client:
        response = client.put("/api/settings", json={"made_up": "value"})
    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "invalid_settings_key",
            "message": "Unknown settings key: made_up",
        }
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py -v`
Expected: FAIL with `404 Not Found` for `/api/...` routes

- [ ] **Step 3: Write minimal implementation**

```python
# app/schemas.py
class SettingsUpdateRequest(BaseModel):
    max_concurrent: str | None = None
    proxy_url: str | None = None
    cookies_path: str | None = None
    downloads_dir: str | None = None

    def as_updates(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value is not None}
```

```python
# app/routes/api.py
router = APIRouter(prefix="/api")


@router.post("/info", response_model=InfoResponse)
def fetch_info(body: InfoRequest, session: Session = Depends(get_session)) -> InfoResponse:
    runtime = resolve_runtime_settings(session)
    raw = extract_info(
        body.url,
        proxy=runtime.proxy_url if body.proxy else None,
        cookies_file=str(runtime.cookies_path) if body.cookies and runtime.cookies_path else None,
    )
    return InfoResponse(
        url=raw["url"],
        title=raw["title"],
        uploader=raw.get("uploader"),
        duration=raw.get("duration"),
        thumbnail=raw.get("thumbnail"),
        formats=normalize_formats(raw),
        captions=raw.get("captions", {}),
    )


@router.put("/settings")
def update_settings(body: SettingsUpdateRequest, session: Session = Depends(get_session)) -> dict[str, bool]:
    updates = body.as_updates()
    invalid = sorted(set(updates) - set(SETTINGS_CATALOG))
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_settings_key", "message": f"Unknown settings key: {invalid[0]}"},
        )
    set_settings_batch(session, updates)
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/api.py app/main.py app/schemas.py app/services/settings.py tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py
git commit -m "feat: add backend api routes for downloads and settings"
```

## Self-Review (Phase 3A)

- Covers the missing progress write path before any UI polling depends on it.
- Separates worker correctness from page rendering so backend behavior can be finished and verified first.
- Locks settings precedence:
  - saved `downloads_dir` / `proxy_url` / `cookies_path` override env defaults only when non-empty
  - `InfoRequest.proxy` and `InfoRequest.cookies` are opt-in booleans for saved values
  - `max_concurrent` comes from persisted settings

## End of Phase 3A

Deliverable: `uv run uvicorn app.main:app` serves the migrated backend, runs worker threads, and exposes stable JSON endpoints for the later UI.
