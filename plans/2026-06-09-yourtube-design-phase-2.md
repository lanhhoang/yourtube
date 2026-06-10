# Phase 2: Backend Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

### Task 1: Error mapping and settings service

**Files:**
- Create: `app/services/error_mapper.py`
- Create: `app/services/settings.py`
- Create: `tests/unit/test_friendly_errors.py`
- Create: `tests/unit/test_settings.py`

- [ ] **Step 1: Write failing error mapping tests**

Cover:

- private or age-restricted video
- geo-blocked video
- HTTP 403
- timeout
- disk full
- permission denied
- generic fallback

- [ ] **Step 2: Implement `friendly_ytdlp_error(raw: str) -> tuple[str, str]`**

Return a user-facing message plus stable error code.

- [ ] **Step 3: Write failing settings tests**

Cover:

- default values when no row exists
- set/get by key
- validation for `max_concurrent`
- reset behavior

- [ ] **Step 4: Implement `app/services/settings.py`**

Expose:

```python
def get_setting(session: Session, key: str) -> str | None: ...
def get_all_settings(session: Session) -> dict[str, str]: ...
def set_setting(session: Session, key: str, value: str) -> None: ...
def set_settings_batch(session: Session, updates: dict[str, str]) -> None: ...
def reset_settings(session: Session) -> None: ...
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_friendly_errors.py tests/unit/test_settings.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/error_mapper.py app/services/settings.py tests/unit/test_friendly_errors.py tests/unit/test_settings.py
git commit -m "feat: add error mapping and settings services"
```

### Task 2: Downloader service

**Files:**
- Create: `app/services/downloader.py`
- Create: `tests/unit/test_downloader_format.py`
- Create: `tests/unit/test_downloader_progress.py`

- [ ] **Step 1: Write failing format classification tests**

Cover:

- combined format
- video-only format
- audio-only format
- missing codec metadata

- [ ] **Step 2: Implement format parsing helpers**

Expose:

```python
def extract_info(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict: ...
def normalize_formats(info: dict) -> list[FormatInfo]: ...
def build_format_selector(video_id: str | None, audio_id: str | None) -> str: ...
```

- [ ] **Step 3: Write failing progress tests**

Cover:

- progress updates
- cancellation hook
- final path extraction

- [ ] **Step 4: Implement `YtdlpProgress` and `run_download(...)`**

`run_download(...)` should accept:

```python
url: str
video_format_id: str | None
audio_format_id: str | None
output_template: str | None
output_dir: str
audio_bitrate: str | None
proxy: str | None
cookies_file: str | None
subtitles: bool
progress_hook: YtdlpProgress | None
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_downloader_format.py tests/unit/test_downloader_progress.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

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

- [ ] **Step 1: Write failing queue tests**

Cover:

- oldest queued row wins
- already-claimed rows are not double-claimed
- queued cancel goes straight to `cancelled`
- active cancel sets `cancel_requested`
- stale detection marks stuck active rows as error
- startup requeue moves active rows back to queued

- [ ] **Step 2: Implement transaction-safe queue functions**

Expose:

```python
def enqueue_download(session: Session, payload: DownloadCreate) -> Download: ...
def claim_next(session: Session) -> Download | None: ...
def release_job(session: Session, job_id: int, *, status: str, error: str | None = None, file_path: str | None = None, file_size: int | None = None, media_format: str | None = None, resolution_height: int | None = None) -> None: ...
def cancel_job(session: Session, job_id: int) -> bool: ...
def get_active_jobs(session: Session) -> list[Download]: ...
def detect_stale_jobs(session: Session, timeout_minutes: int = 10) -> int: ...
def requeue_active_on_startup(session: Session) -> int: ...
```

Implementation rule: `claim_next()` must claim inside a write transaction and succeed only when a conditional update affects one row.

- [ ] **Step 3: Write failing library tests**

Cover:

- done rows only
- newest first
- title/uploader search
- delete removes DB row and file if present

- [ ] **Step 4: Implement library functions**

Expose:

```python
def get_library(session: Session) -> list[Download]: ...
def search_library(session: Session, query: str) -> list[Download]: ...
def delete_from_library(session: Session, job_id: int) -> tuple[bool, str]: ...
```

- [ ] **Step 5: Add worker lifecycle integration test**

Simulate:

- enqueue
- claim
- mocked download success
- release to `done`

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py tests/unit/test_library.py tests/integration/test_worker_lifecycle.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/queue.py app/services/library.py tests/unit/test_queue_claim.py tests/unit/test_queue_cancel.py tests/unit/test_queue_stale.py tests/unit/test_library.py tests/integration/test_worker_lifecycle.py
git commit -m "feat: add queue and library services"
```

## Self-Review (Phase 2)

- No CLI deliverables remain.
- Queue claim semantics are explicit and concurrency-safe.
- Service contracts align with the Phase 3 web routes.

## End of Phase 2

Deliverable: backend services are complete and verified without introducing the web layer yet.
