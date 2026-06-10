# Phase 2: Backend Services Implementation Plan ✅

> **Status:** Complete. All tasks implemented, tested, and code-reviewed.
> **Commits:** `2d66873`, `896af77`, `cd54d83`, `cd4af59`
> **Tests:** 85 passing, 91.77% coverage, lint/type-check clean.

**Goal:** Build the downloader, error mapper, settings, queue, and library services on top of the migrated SQLAlchemy database.

**Architecture:** Services stay synchronous and database-session driven. Routes are not introduced yet; Phase 2 is about durable service boundaries, queue state transitions, and downloader orchestration that the web app will call in Phase 3.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, yt-dlp, ffmpeg, pytest

---

## File Structure (this phase adds)

```
yourtube/
├── app/
│   └── services/
│       ├── error_mapper.py
│       ├── settings.py
│       ├── downloader.py
│       ├── queue.py
│       └── library.py
└── tests/
    ├── unit/
    │   ├── test_friendly_errors.py
    │   ├── test_settings.py
    │   ├── test_downloader_format.py
    │   ├── test_downloader_progress.py
    │   ├── test_queue_claim.py
    │   ├── test_queue_cancel.py
    │   ├── test_queue_stale.py
    │   └── test_library.py
    └── integration/
        └── test_worker_lifecycle.py
```

## Settings Catalog Reference

The following runtime settings are persisted in the `settings` table and consumed by the worker pool and API routes in later phases:

| Key              | Default | Validation             | Description                |
| ---------------- | ------- | ---------------------- | -------------------------- |
| `max_concurrent` | `"1"`   | integer 1-5            | Max simultaneous downloads |
| `proxy_url`      | `""`    | string (URL or empty)  | HTTP proxy for yt-dlp      |
| `cookies_path`   | `""`    | string (path or empty) | Path to cookies.txt        |
| `downloads_dir`  | `""`    | string (path or empty) | Output directory override  |

The settings service validates `max_concurrent` on write (rejects non-integer and out-of-range values with `ValueError`). Other keys accept any string; empty-string values are treated as unset.

### Task 1: Error mapping and settings service

**Files:**

- Create: `app/services/error_mapper.py`
- Create: `app/services/settings.py`
- Create: `tests/unit/test_friendly_errors.py`
- Create: `tests/unit/test_settings.py`

- [x] **Step 1: Write failing error mapping tests**

Cover:

- private or age-restricted video
- geo-blocked video
- HTTP 403
- timeout
- disk full
- permission denied
- generic fallback

- [x] **Step 2: Implement `friendly_ytdlp_error(raw: str) -> tuple[str, str]`**

Return a user-facing message plus stable error code.

- [x] **Step 3: Write failing settings tests**

Cover:

- `get_setting()` returns default value when no row exists (`max_concurrent` -> `"1"`)
- `get_setting()` returns stored value after `set_setting()`
- `get_all_settings()` returns all catalog keys with defaults when table is empty
- `set_setting()` with a non-catalog key is allowed (flexible storage) but not validated
- validation: `max_concurrent` rejects `"0"`, `"6"`, `"abc"` with `ValueError`; accepts `"1"` through `"5"`
- `set_settings_batch(updates=...)` updates multiple keys atomically
- `reset_settings()` restores all catalog keys to their defaults

- [x] **Step 4: Implement `app/services/settings.py`**

Expose:

```python
def get_setting(session: Session, key: str) -> str | None: ...
def get_all_settings(session: Session) -> dict[str, str]: ...
def set_setting(session: Session, key: str, value: str) -> None: ...
def set_settings_batch(session: Session, updates: dict[str, str]) -> None: ...
def reset_settings(session: Session) -> None: ...
```

- [x] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_friendly_errors.py tests/unit/test_settings.py -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add app/services/error_mapper.py app/services/settings.py tests/unit/test_friendly_errors.py tests/unit/test_settings.py
git commit -m "feat: add error mapping and settings services"
```

### Task 2: Downloader service

**Files:**

- Create: `app/services/downloader.py`
- Create: `tests/unit/test_downloader_format.py`
- Create: `tests/unit/test_downloader_progress.py`

- [x] **Step 1: Write failing format classification tests**

Cover:

- combined format
- video-only format
- audio-only format
- missing codec metadata

- [x] **Step 2: Implement format parsing helpers**

Expose:

```python
def extract_info(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict: ...
def normalize_formats(info: dict) -> list[FormatInfo]: ...
def build_format_selector(video_id: str | None, audio_id: str | None) -> str: ...
```

- [x] **Step 3: Define `YtdlpProgress` callback class**

Add to `app/services/downloader.py`:

```python
class YtdlpProgress:
    """Callback matching yt-dlp's progress hook interface.

    The ``d`` dict follows yt-dlp's progress hook format:
    ``status`` ("downloading" | "finished" | "error"),
    ``_percent_str``, ``_speed_str``, ``_eta_str``,
    ``downloaded_bytes``, ``total_bytes``, ``filename``.
    """

    def __call__(self, d: dict) -> None:
        ...


class DownloadCancelled(Exception):
    """Raised inside the progress hook when cancellation is requested."""
```

- [x] **Step 4: Write failing progress tests**

Cover:

- progress callback extracts `_percent_str` and normalises to a `float` between 0 and 100
- progress callback detects `status == "finished"` and records the `filename`
- cancellation: when a `cancel_requested` flag is `True`, the callback raises `DownloadCancelled`
- `run_download()` raises `DownloadCancelled` when the hook raises it
- `run_download()` returns the output file path on success

- [x] **Step 5: Implement `run_download(...)`**

```python
def run_download(
    url: str,
    video_format_id: str | None = None,
    audio_format_id: str | None = None,
    output_template: str | None = None,
    output_dir: str,
    audio_bitrate: str | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hook: YtdlpProgress | None = None,
) -> str:
    """Run yt-dlp and return the output file path.

    Raises ``DownloadCancelled`` if the progress hook signals cancellation.
    Callers should map yt-dlp errors through ``friendly_ytdlp_error()``.
    """
```

Implementation: build `ydl_opts` dict from parameters, call `yt_dlp.YoutubeDL(ydl_opts).download([url])`, and return the file path extracted from the progress hook on `"finished"` status.

- [x] **Step 6: Run tests**

Run: `uv run pytest tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py -v`
Expected: PASS

- [x] **Step 7: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py
git commit -m "feat: add yt-dlp downloader service"
```

### Task 3: Queue and library services

**Files:**

- Create: `app/services/queue.py`
- Create: `app/services/library.py`
- Create: `tests/unit/test_queue_claim.py`
- Create: `tests/unit/test_queue_cancel.py`
- Create: `tests/unit/test_queue_stale.py`
- Create: `tests/unit/test_library.py`
- Create: `tests/integration/test_worker_lifecycle.py`

- [x] **Step 1: Write failing queue tests**

Cover:

- `enqueue_download()` creates a row with status `"queued"` and auto-incremented id
- `claim_next()` returns the oldest `queued` row and sets status to `active` and `claimed_at` to now
- `claim_next()` skips rows that are already `active`, `done`, `error`, or `cancelled`
- two concurrent calls to `claim_next()` must not return the same row (transactional claim semantics)
- `cancel_job()` on a `queued` row sets status to `cancelled` immediately
- `cancel_job()` on an `active` row sets `cancel_requested = True` and returns `True`
- `cancel_job()` on `done`, `error`, or `cancelled` returns `False` (no-op)
- `detect_stale_jobs(timeout_minutes=10)` marks rows with `status='active'` and `claimed_at < now - 10min` as `error` with code `stale_worker`
- `requeue_active_on_startup()` moves all `active` rows back to `queued` and clears `claimed_at`

- [x] **Step 2: Implement transaction-safe queue functions**

Expose:

```python
def enqueue_download(session: Session, payload: DownloadCreate) -> Download: ...
def claim_next(session: Session) -> Download | None:
    """Claim the oldest ``queued`` row.

    Uses a conditional UPDATE inside a write transaction:
    ``UPDATE downloads SET status='active', claimed_at=CURRENT_TIMESTAMP
     WHERE id = (SELECT id FROM downloads WHERE status='queued'
     ORDER BY created_at LIMIT 1) AND status='queued'``.
    Returns the claimed ``Download`` or ``None``.
    """
    ...
def release_job(
    session: Session,
    job_id: int,
    *,
    status: str,                       # "done" | "error" | "cancelled"
    error_code: str | None = None,
    error_message: str | None = None,
    file_path: str | None = None,
    file_size: int | None = None,
    media_format: str | None = None,
    resolution_height: int | None = None,
) -> bool:
    """Transition a claimed job to its terminal state.

    Sets ``finished_at`` to now. For ``status="done"``, populates file
    metadata columns. For ``"error"``, sets ``error_code`` and
    ``error_message``. Returns ``True`` if the row was updated.
    """
    ...
def cancel_job(session: Session, job_id: int) -> bool:
    """Request cancellation.

    - ``queued`` -> ``cancelled`` immediately (returns ``True``)
    - ``active`` -> sets ``cancel_requested = True`` (returns ``True``)
    - ``done`` / ``error`` / ``cancelled`` -> no-op (returns ``False``)
    """
    ...
def get_active_jobs(session: Session) -> list[Download]:
    """Return all rows with status ``queued`` or ``active``, ordered by ``created_at``."""
    ...
def detect_stale_jobs(session: Session, timeout_minutes: int = 10) -> int:
    """Mark ``active`` rows older than ``timeout_minutes`` as ``error`` with code ``stale_worker``. Returns count."""
    ...
def requeue_active_on_startup(session: Session) -> int:
    """Move all ``active`` rows back to ``queued`` and clear ``claimed_at``. Returns count."""
    ...
```

Implementation rule: `claim_next()` must claim inside a write transaction and succeed only when a conditional update affects one row.

- [x] **Step 3: Write failing library tests**

Cover:

- done rows only
- newest first
- title/uploader search
- delete removes DB row and file if present

- [x] **Step 4: Implement library functions**

Expose:

```python
def get_library(session: Session) -> list[Download]:
    """Return all ``done`` rows ordered by ``finished_at`` descending."""
    ...
def search_library(session: Session, query: str) -> list[Download]:
    """Search ``done`` rows by ``title`` or ``uploader`` (LIKE match)."""
    ...
def delete_from_library(session: Session, job_id: int) -> tuple[bool, str]:
    """Delete a completed download.

    Returns ``(True, "")`` on success (row deleted, file removed).
    Returns ``(False, "not_found")`` if the id does not exist.
    Returns ``(False, "not_done")`` if the job is not in ``done`` state.
    Missing files on disk are tolerated: returns ``(True, "file_missing")``.
    """
    ...
```

- [x] **Step 5: Add worker lifecycle integration test**

Simulate:

- enqueue a download
- claim it and verify status becomes `active` with `claimed_at` set
- release via `release_job(..., status="done", ...)` and verify row is `done` with file metadata populated
- enqueue a second download, cancel it while `queued`, verify status is `cancelled`
- enqueue a third download, claim it, manually set `claimed_at` far in the past, run `detect_stale_jobs()`, verify it becomes `error` with code `stale_worker`
- create an `active` row directly, run `requeue_active_on_startup()`, verify it returns to `queued` and `claimed_at` is cleared

- [x] **Step 6: Run tests**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py tests/unit/test_library.py tests/integration/test_worker_lifecycle.py -v`
Expected: PASS

- [x] **Step 7: Commit**

```bash
git add app/services/queue.py app/services/library.py tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py tests/unit/test_library.py tests/integration/test_worker_lifecycle.py
git commit -m "feat: add queue and library services"
```

## Self-Review (Phase 2)

- No CLI deliverables remain.
- Queue claim semantics are explicit and concurrency-safe.
- Service contracts align with the Phase 3 web routes.

## Execution Results

### Test count: 85 (up from 6 Phase 1 baselines)

| Test file                     | Count |
| ----------------------------- | ----- |
| `test_friendly_errors.py`     | 17    |
| `test_settings.py`            | 17    |
| `test_downloader_format.py`   | 10    |
| `test_downloader_progress.py` | 10    |
| `test_queue_claim.py`         | 6     |
| `test_queue_cancel.py`        | 3     |
| `test_queue_stale.py`         | 4     |
| `test_library.py`             | 8     |
| `test_worker_lifecycle.py`    | 4     |
| Phase 1 baseline              | 6     |

### Deviations from plan

1. `YtdlpProgress` implemented as a real stateful class (with `percent`, `filename` fields and optional `cancel_requested` callback), not an abstract stub. Tests exercise the real class, not a test-only subclass.
2. `cancel_job` uses conditional UPDATE statements (not `session.get`) so the result is independent of the session's identity map.
3. `run_download` always installs an internal progress hook to capture the output path, even when no external `progress_hook` is supplied. The caller hook is called after the internal path capture.
4. `release_job` guards against `status != 'active'` rows — only active rows can be transitioned to a terminal state.
5. `claim_next` ordering made deterministic with `(created_at, id)` tiebreaker.
6. `delete_from_library` distinguishes `FileNotFoundError` (tolerated, returns `file_missing`) from other `OSError` (returns `delete_failed`, row preserved).

### Commits

| Commit    | Message                                       |
| --------- | --------------------------------------------- |
| `2d66873` | feat: add error mapping and settings services |
| `896af77` | feat: add yt-dlp downloader service           |
| `cd54d83` | feat: add queue and library services          |
| `cd4af59` | fix: address code review findings             |
