# Phase 3A: Backend-Complete Worker + API Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete backend contract that Phase 3B depends on: startup wiring, worker lifecycle, progress persistence, and all JSON endpoints required by the server-rendered UI.

**Architecture:** Keep the existing synchronous service layer and add one thin integration layer around it. `app/main.py` owns startup and worker threads, `app/routes/api.py` owns the JSON contract, and the existing services remain the source of truth for queue state, settings, downloader behavior, and library deletion.

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
│       ├── library.py
│       ├── queue.py
│       └── settings.py
└── tests/
    ├── unit/
    │   ├── test_queue_progress.py
    │   ├── test_queue_cancel_flag.py
    │   ├── test_settings_runtime_resolution.py
    │   └── test_downloader_progress.py
    └── integration/
        ├── test_startup_recovery.py
        ├── test_worker_pool.py
        ├── test_api_info.py
        ├── test_api_downloads.py
        ├── test_api_settings.py
        └── test_api_library.py
```

Responsibilities:

- `app/services/queue.py` owns the additive worker helpers: persist progress and read the cancellation flag.
- `app/services/settings.py` owns conversion from persisted string settings to runtime-ready typed values.
- `app/services/downloader.py` publishes progress callbacks that can both cancel and persist progress.
- `app/main.py` owns lifespan order, worker startup and shutdown, and thread-to-service orchestration.
- `app/routes/api.py` owns the complete Phase 3A JSON contract:
  - `POST /api/info`
  - `POST /api/downloads`
  - `POST /api/downloads/{id}/cancel`
  - `GET /api/downloads/{id}/file`
  - `GET /api/settings`
  - `PUT /api/settings`
  - `POST /api/settings/reset`
  - `DELETE /api/library/{id}`

## Runtime And API Defaults

- Persisted non-empty settings override environment defaults.
- Persisted empty strings mean "unset":
  - `proxy_url -> None`
  - `cookies_path -> None`
  - `downloads_dir -> app.config.settings.downloads_dir`
- `max_concurrent` is loaded from persisted settings at startup and does not hot-reload in Phase 3A.
- `GET /api/downloads/{id}/file` only serves jobs in `done` state with an existing file path on disk.
- `POST /api/downloads/{id}/cancel` returns `409` for terminal jobs because no state transition is available.
- Phase 3A does not add JSON queue or library list endpoints; Phase 3B will render queue and library state through HTML partial routes.

### Task 1: Add worker-facing queue helpers and runtime settings resolution

**Files:**
- Modify: `app/services/queue.py`
- Modify: `app/services/settings.py`
- Create: `tests/unit/test_queue_progress.py`
- Create: `tests/unit/test_queue_cancel_flag.py`
- Create: `tests/unit/test_settings_runtime_resolution.py`

- [ ] **Step 1: Write the failing queue progress and cancel-flag tests**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Download
from app.schemas import DownloadCreate
from app.services.queue import enqueue_download, is_cancel_requested, update_progress


def test_update_progress_persists_percent_for_active_job(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/video"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active")
    )
    db_session.commit()

    changed = update_progress(db_session, row.id, 42.5)

    assert changed is True
    db_session.refresh(row)
    assert row.progress == 42.5


def test_update_progress_ignores_non_active_job(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/queued"))

    changed = update_progress(db_session, row.id, 80.0)

    assert changed is False
    db_session.refresh(row)
    assert row.progress == 0.0


def test_is_cancel_requested_reads_current_flag(db_session: Session) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/cancel"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    db_session.commit()

    assert is_cancel_requested(db_session, row.id) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_queue_progress.py tests/unit/test_queue_cancel_flag.py -v`
Expected: FAIL with `ImportError` because `update_progress` and `is_cancel_requested` do not exist

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


def test_resolve_runtime_settings_turns_blank_values_into_runtime_defaults(db_session) -> None:
    resolved = resolve_runtime_settings(db_session)

    assert resolved.max_concurrent == 1
    assert resolved.proxy_url is None
    assert resolved.cookies_path is None


def test_resolve_runtime_settings_uses_saved_proxy_and_cookies(db_session, tmp_path: Path) -> None:
    cookies_path = tmp_path / "cookies.txt"
    set_settings_batch(
        db_session,
        {
            "proxy_url": "http://proxy.internal:8080",
            "cookies_path": str(cookies_path),
            "max_concurrent": "3",
        },
    )

    resolved = resolve_runtime_settings(db_session)

    assert resolved.max_concurrent == 3
    assert resolved.proxy_url == "http://proxy.internal:8080"
    assert resolved.cookies_path == cookies_path
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_queue_progress.py tests/unit/test_queue_cancel_flag.py tests/unit/test_settings_runtime_resolution.py -v`
Expected: FAIL because `resolve_runtime_settings` does not exist

- [ ] **Step 5: Write minimal implementation**

```python
# app/services/queue.py
from sqlalchemy import select, update


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


def is_cancel_requested(session: Session, job_id: int) -> bool:
    stmt = select(Download.cancel_requested).where(Download.id == job_id)
    return bool(session.execute(stmt).scalar_one_or_none())
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
    stored = get_all_settings(session)
    max_concurrent = int(stored["max_concurrent"] or "1")
    downloads_dir = (
        Path(stored["downloads_dir"])
        if stored["downloads_dir"]
        else app_settings.downloads_dir
    )
    proxy_url = stored["proxy_url"] or app_settings.proxy_url
    cookies_path = (
        Path(stored["cookies_path"])
        if stored["cookies_path"]
        else app_settings.cookies_path
    )
    return RuntimeSettings(
        max_concurrent=max(1, min(5, max_concurrent)),
        proxy_url=proxy_url or None,
        cookies_path=cookies_path,
        downloads_dir=downloads_dir,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_queue_progress.py tests/unit/test_queue_cancel_flag.py tests/unit/test_settings_runtime_resolution.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/queue.py app/services/settings.py tests/unit/test_queue_progress.py tests/unit/test_queue_cancel_flag.py tests/unit/test_settings_runtime_resolution.py
git commit -m "feat: add worker runtime helpers"
```

### Task 2: Add progress callbacks, startup recovery, and worker pool orchestration

**Files:**
- Modify: `app/services/downloader.py`
- Modify: `app/main.py`
- Create: `tests/integration/test_startup_recovery.py`
- Create: `tests/integration/test_worker_pool.py`
- Modify: `tests/unit/test_downloader_progress.py`

- [ ] **Step 1: Write the failing downloader progress callback test**

```python
from __future__ import annotations

from app.services.downloader import YtdlpProgress


def test_progress_callback_calls_on_progress_with_normalized_percent() -> None:
    seen: list[float] = []
    progress = YtdlpProgress(on_progress=seen.append)

    progress({"status": "downloading", "_percent_str": "12.5%"})

    assert seen == [12.5]
```

- [ ] **Step 2: Write the failing startup and worker tests**

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
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active")
    )
    db_session.commit()

    with TestClient(app):
        pass

    db_session.refresh(row)
    assert row.status == "queued"
```

```python
from __future__ import annotations

from pathlib import Path

from app.models import Download
from app.schemas import DownloadCreate
from app.services.downloader import DownloadCancelled
from app.services.queue import enqueue_download
from app.services.settings import set_settings_batch


def test_worker_success_marks_job_done(monkeypatch, db_session, tmp_path: Path) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/success"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active")
    )
    set_settings_batch(db_session, {"downloads_dir": str(tmp_path)})
    db_session.commit()

    def fake_run_download(**kwargs):
        hook = kwargs["progress_hook"]
        hook({"status": "downloading", "_percent_str": "55.0%"})
        hook({"status": "finished", "filename": str(tmp_path / "video.mp4")})
        return str(tmp_path / "video.mp4")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session.refresh(row)
    assert row.status == "done"
    assert row.progress == 55.0
    assert row.file_path == str(tmp_path / "video.mp4")


def test_worker_cancelled_download_ends_cancelled(monkeypatch, db_session, tmp_path: Path) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/cancel"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active", cancel_requested=True)
    )
    set_settings_batch(db_session, {"downloads_dir": str(tmp_path)})
    db_session.commit()

    def fake_run_download(**_kwargs):
        raise DownloadCancelled("cancelled by user")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session.refresh(row)
    assert row.status == "cancelled"


def test_worker_failure_maps_error(monkeypatch, db_session, tmp_path: Path) -> None:
    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/fail"))
    db_session.execute(
        Download.__table__.update()
        .where(Download.id == row.id)
        .values(status="active")
    )
    set_settings_batch(db_session, {"downloads_dir": str(tmp_path)})
    db_session.commit()

    def fake_run_download(**_kwargs):
        raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    pool._run_job(row.id)

    db_session.refresh(row)
    assert row.status == "error"
    assert row.error_code == "http_forbidden"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_progress.py::test_progress_callback_calls_on_progress_with_normalized_percent tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py -v`
Expected: FAIL because `YtdlpProgress` does not accept `on_progress` and `WorkerPool` does not exist

- [ ] **Step 4: Write minimal implementation**

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
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.db import SessionLocal, engine
from app.models import Download
from app.services.downloader import DownloadCancelled, YtdlpProgress, run_download
from app.services.error_mapper import friendly_ytdlp_error
from app.services.queue import claim_next, is_cancel_requested, release_job, requeue_active_on_startup, update_progress
from app.services.settings import resolve_runtime_settings

logger = logging.getLogger("yourtube")


class WorkerPool:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def start(self, concurrency: int) -> None:
        for index in range(concurrency):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"worker-{index}",
                daemon=True,
            )
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
            Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
            job = session.get(Download, job_id)
            if job is None:
                return
            progress = YtdlpProgress(
                cancel_requested=lambda: _cancel_requested(job_id),
                on_progress=lambda percent: _persist_progress(job_id, percent),
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
            except Exception as exc:  # noqa: BLE001
                code, message = friendly_ytdlp_error(str(exc))
                release_job(
                    session,
                    job_id,
                    status="error",
                    error_code=code,
                    error_message=message,
                )
                return
            release_job(session, job_id, status="done", file_path=output_path or None)


def _persist_progress(job_id: int, percent: float) -> None:
    with SessionLocal() as session:
        update_progress(session, job_id, percent)


def _cancel_requested(job_id: int) -> bool:
    with SessionLocal() as session:
        return is_cancel_requested(session, job_id)
```

- [ ] **Step 5: Finish lifespan wiring**

```python
# app/main.py
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    _ensure_data_dir()
    _run_migrations()
    with SessionLocal() as session:
        requeue_active_on_startup(session)
        runtime = resolve_runtime_settings(session)
    Path(runtime.downloads_dir).mkdir(parents=True, exist_ok=True)
    worker_pool = WorkerPool()
    worker_pool.start(runtime.max_concurrent)
    _app.state.worker_pool = worker_pool
    yield
    worker_pool.stop()
    engine.dispose()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_progress.py tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/services/downloader.py tests/unit/test_downloader_progress.py tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py
git commit -m "feat: add backend worker integration"
```

### Task 3: Add info, enqueue, cancel, and file-download APIs

**Files:**
- Create: `app/routes/api.py`
- Modify: `app/main.py`
- Modify: `app/schemas.py`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads.py`

- [ ] **Step 1: Write the failing info and download API tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_fetch_info_returns_normalized_formats(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Example uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [{"format_id": "18", "ext": "mp4", "resolution": "360p"}],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.api.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/api/info", json={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert response.json()["formats"][0]["format_id"] == "18"


def test_create_download_returns_201() -> None:
    with TestClient(app) as client:
        response = client.post("/api/downloads", json={"url": "https://example.com/video"})

    assert response.status_code == 201
    assert response.json()["status"] == "queued"


def test_cancel_download_returns_updated_state(db_session) -> None:
    from app.schemas import DownloadCreate
    from app.services.queue import enqueue_download

    row = enqueue_download(db_session, DownloadCreate(url="https://example.com/cancel"))

    with TestClient(app) as client:
        response = client.post(f"/api/downloads/{row.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
```

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_download_file_serves_completed_job(db_session, tmp_path: Path) -> None:
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"data")
    row = Download(
        url="https://example.com/done",
        status="done",
        progress=100.0,
        file_path=str(file_path),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/api/downloads/{row.id}/file")

    assert response.status_code == 200
    assert response.content == b"data"


def test_download_file_rejects_non_done_job(db_session) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/api/downloads/{row.id}/file")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "download_not_ready"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_api_info.py tests/integration/test_api_downloads.py -v`
Expected: FAIL with `404 Not Found` for `/api/...` routes

- [ ] **Step 3: Add the request and response schemas**

```python
# app/schemas.py
class SettingsUpdateRequest(BaseModel):
    max_concurrent: str | None = None
    proxy_url: str | None = None
    cookies_path: str | None = None
    downloads_dir: str | None = None

    def as_updates(self) -> dict[str, str]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class SettingsResponse(BaseModel):
    max_concurrent: str
    proxy_url: str
    cookies_path: str
    downloads_dir: str


class MutationOkResponse(BaseModel):
    ok: bool = True
```

- [ ] **Step 4: Write minimal route implementation**

```python
# app/routes/api.py
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Download
from app.schemas import DownloadCreate, DownloadResponse, InfoRequest, InfoResponse
from app.services.downloader import extract_info, normalize_formats
from app.services.queue import cancel_job, enqueue_download
from app.services.settings import resolve_runtime_settings

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


@router.post("/downloads", response_model=DownloadResponse, status_code=201)
def create_download(
    body: DownloadCreate,
    session: Session = Depends(get_session),
) -> DownloadResponse:
    row = enqueue_download(session, body)
    return DownloadResponse.model_validate(row)


@router.post("/downloads/{job_id}/cancel", response_model=DownloadResponse)
def cancel_download(job_id: int, session: Session = Depends(get_session)) -> DownloadResponse:
    changed = cancel_job(session, job_id)
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "download_not_found", "message": f"Download {job_id} not found."},
        )
    if not changed:
        raise HTTPException(
            status_code=409,
            detail={"code": "download_not_cancellable", "message": f"Download {job_id} is already finished."},
        )
    session.refresh(row)
    return DownloadResponse.model_validate(row)


@router.get("/downloads/{job_id}/file")
def download_file(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "download_not_found", "message": f"Download {job_id} not found."},
        )
    if row.status != "done" or not row.file_path:
        raise HTTPException(
            status_code=409,
            detail={"code": "download_not_ready", "message": f"Download {job_id} is not ready."},
        )
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "download_file_missing", "message": f"File for download {job_id} is missing."},
        )
    return FileResponse(path)
```

- [ ] **Step 5: Wire the router into the app**

```python
# app/main.py
from app.routes.api import router as api_router

app = FastAPI(title="YourTube", lifespan=lifespan)
app.include_router(api_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_api_info.py tests/integration/test_api_downloads.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/routes/api.py app/schemas.py tests/integration/test_api_info.py tests/integration/test_api_downloads.py
git commit -m "feat: add download and info api routes"
```

### Task 4: Add settings read/write/reset and library delete APIs

**Files:**
- Modify: `app/routes/api.py`
- Modify: `app/schemas.py`
- Create: `tests/integration/test_api_settings.py`
- Create: `tests/integration/test_api_library.py`

- [ ] **Step 1: Write the failing settings and library API tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_get_settings_returns_catalog_values() -> None:
    with TestClient(app) as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["max_concurrent"] == "1"


def test_update_settings_rejects_unknown_keys() -> None:
    with TestClient(app) as client:
        response = client.put("/api/settings", json={"made_up": "value"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_settings_key"


def test_reset_settings_restores_defaults(db_session) -> None:
    from app.services.settings import set_setting

    set_setting(db_session, "max_concurrent", "4")

    with TestClient(app) as client:
        response = client.post("/api/settings/reset")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_delete_library_entry_removes_completed_job(db_session, tmp_path: Path) -> None:
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"data")
    row = Download(
        url="https://example.com/done",
        status="done",
        progress=100.0,
        file_path=str(file_path),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    with TestClient(app) as client:
        response = client.delete(f"/api/library/{row.id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_library_entry_rejects_non_done_job(db_session) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    with TestClient(app) as client:
        response = client.delete(f"/api/library/{row.id}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "library_entry_not_done"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_api_settings.py tests/integration/test_api_library.py -v`
Expected: FAIL with `404 Not Found` for `/api/settings` and `/api/library/...`

- [ ] **Step 3: Write minimal implementation**

```python
# app/routes/api.py
from app.schemas import MutationOkResponse, SettingsResponse, SettingsUpdateRequest
from app.services.library import delete_from_library
from app.services.settings import SETTINGS_CATALOG, get_all_settings, reset_settings, set_settings_batch


@router.get("/settings", response_model=SettingsResponse)
def read_settings(session: Session = Depends(get_session)) -> SettingsResponse:
    return SettingsResponse(**get_all_settings(session))


@router.put("/settings", response_model=MutationOkResponse)
def update_settings(
    body: SettingsUpdateRequest,
    session: Session = Depends(get_session),
) -> MutationOkResponse:
    updates = body.as_updates()
    invalid = sorted(set(updates) - set(SETTINGS_CATALOG))
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_settings_key", "message": f"Unknown settings key: {invalid[0]}"},
        )
    set_settings_batch(session, updates)
    return MutationOkResponse()


@router.post("/settings/reset", response_model=MutationOkResponse)
def reset_settings_route(session: Session = Depends(get_session)) -> MutationOkResponse:
    reset_settings(session)
    return MutationOkResponse()


@router.delete("/library/{job_id}", response_model=MutationOkResponse)
def delete_library_entry(job_id: int, session: Session = Depends(get_session)) -> MutationOkResponse:
    deleted, reason = delete_from_library(session, job_id)
    if deleted:
        return MutationOkResponse()
    if reason == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"code": "library_entry_not_found", "message": f"Library entry {job_id} not found."},
        )
    if reason == "not_done":
        raise HTTPException(
            status_code=409,
            detail={"code": "library_entry_not_done", "message": f"Library entry {job_id} is not complete."},
        )
    raise HTTPException(
        status_code=500,
        detail={"code": "library_delete_failed", "message": f"Could not delete library entry {job_id}."},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_api_settings.py tests/integration/test_api_library.py -v`
Expected: PASS

- [ ] **Step 5: Run the consolidated backend suite**

Run: `uv run pytest tests/test_health.py tests/unit/test_queue_progress.py tests/unit/test_queue_cancel_flag.py tests/unit/test_settings_runtime_resolution.py tests/unit/test_downloader_progress.py tests/integration/test_startup_recovery.py tests/integration/test_worker_pool.py tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py tests/integration/test_api_library.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/api.py app/schemas.py tests/integration/test_api_settings.py tests/integration/test_api_library.py
git commit -m "feat: add settings and library api routes"
```

## Self-Review

- Spec coverage:
  - worker-facing progress persistence -> Task 1
  - runtime settings precedence -> Task 1
  - startup requeue and worker lifecycle -> Task 2
  - info, enqueue, cancel, and file download APIs -> Task 3
  - settings read/write/reset and library deletion APIs -> Task 4
- Placeholder scan:
  - removed undefined helper references by explicitly defining `is_cancel_requested`, `_cancel_requested`, and `_persist_progress`
  - replaced the earlier partial API surface with the complete Phase 3A contract
- Type consistency:
  - request and response contracts live in `app/schemas.py`
  - JSON routes return `DownloadResponse`, `InfoResponse`, `SettingsResponse`, or `MutationOkResponse`
  - worker helpers use SQLAlchemy `Session` and existing `Download` rows

## Execution Handoff

Plan complete and saved to `plans/2026-06-09-yourtube-design-phase-3a.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
