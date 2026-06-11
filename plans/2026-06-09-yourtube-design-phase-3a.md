# Phase 3A: Backend-Complete Worker + API Contract Implementation Plan

> **Status: ✅ Complete (June 11, 2026)**

**Goal:** Build the complete backend contract that Phase 3B depends on: startup wiring, worker lifecycle, progress persistence, and all JSON endpoints required by the server-rendered UI.

**Architecture:** Keep the existing synchronous service layer and add one thin integration layer around it. `app/main.py` owns startup and worker threads, `app/routes/api.py` owns the JSON contract, and the existing services remain the source of truth for queue state, settings, downloader behavior, and library deletion.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Starlette responses, yt-dlp, pytest

**Results:**
- 113 tests pass (baseline 85), 0 regressions
- 18 files changed (8 modified, 10 new)
- 3 feature-group commits on `20260610-phase-3a-implement-backend-worker-integration`

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

### Task 1: Add worker-facing queue helpers and runtime settings resolution — ✅ Complete

**Files:**
- Modify: `app/services/queue.py` — `update_progress`, `is_cancel_requested`
- Modify: `app/services/settings.py` — `RuntimeSettings` dataclass, `resolve_runtime_settings`
- Create: `tests/unit/test_queue_progress.py`
- Create: `tests/unit/test_queue_cancel_flag.py`
- Create: `tests/unit/test_settings_runtime_resolution.py`

**8 tests** testing progress persistence for active/non-active jobs, cancel-flag reads, and runtime settings precedence (saved dirs, blank values, saved proxy/cookies).

### Task 2: Add progress callbacks, startup recovery, and worker pool orchestration — ✅ Complete

**Files:**
- Modify: `app/services/downloader.py` — `YtdlpProgress(on_progress=...)` callback
- Modify: `app/main.py` — `WorkerPool` class, daemon-thread worker loop, lifespan wiring (requeue → start → shutdown), `workers_enabled` flag
- Modify: `app/config.py` — `workers_enabled: bool = True` (tests set `YT_WORKERS_ENABLED=0`)
- Modify: `tests/conftest.py` — `db_session_visible` fixture (committing session with table-level teardown)
- Modify: `tests/unit/test_downloader_progress.py` — `test_progress_callback_calls_on_progress_with_normalized_percent`
- Create: `tests/integration/test_startup_recovery.py`
- Create: `tests/integration/test_worker_pool.py`

**6 new tests** covering progress callback dispatch, startup requeue, and the three `_run_job` outcome paths (success, cancelled, error).

**Deviation from plan:** the integration tests use `db_session_visible` (a new committing fixture) instead of `db_session` because the existing `db_session` wraps the session in a rollback-only transaction; worker threads and the FastAPI lifespan use `SessionLocal` (a different connection) and cannot see uncommitted data. `db_session_visible` is identical to `db_session` except it omits the external `connection.begin()` so that `session.commit()` persists to the database. Table-level cleanup (`DELETE FROM downloads, settings`) runs at fixture teardown to prevent data leakage into the next test. The FastAPI lifespan skips the worker pool when `workers_enabled=False`. Both changes keep the existing 85 `db_session`-based unit tests untouched.

### Task 3: Add info, enqueue, cancel, and file-download APIs — ✅ Complete

**Files:**
- Create: `app/routes/api.py` — `POST /api/info`, `POST /api/downloads`, `POST /api/downloads/{id}/cancel`, `GET /api/downloads/{id}/file`, `GET /api/settings`, `PUT /api/settings`, `POST /api/settings/reset`, `DELETE /api/library/{id}`
- Modify: `app/schemas.py` — `SettingsResponse`, `MutationOkResponse`, `ErrorResponse`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads.py`

**7 tests** covering info format normalization, 201 on enqueue, cancel status codes (200, 404, 409), file serving for done/queued jobs.

### Task 4: Add settings read/write/reset and library delete APIs — ✅ Complete

**Files:**
- Tests for settings and library endpoints (in `test_api_settings.py`, `test_api_library.py`)

**7 tests** covering settings GET defaults, PUT rejection of unknown keys, PUT persistence of known keys, POST reset, library DELETE success (done jobs), 409 for non-done jobs, 404 for missing ids.

**Deviation from plan:** the plan specified a `SettingsUpdateRequest` Pydantic model with an `as_updates()` helper, but Pydantic v2 silently drops extra fields from `model_dump()`, so a request body with `{"made_up": "value"}` would produce an empty update dict and the rejection test would see HTTP 200 instead of 400. The route was switched to `body: dict[str, str | None] = Body(...)` so it sees the raw JSON mapping and can reject unknown keys directly against `SETTINGS_CATALOG`. `SettingsUpdateRequest` was removed from `schemas.py` as dead code.
