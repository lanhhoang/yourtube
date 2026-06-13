# YourTube Implementation Plan — Phase 13: Wire `detect_stale_jobs` into the worker pool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `detect_stale_jobs()` (`app/services/queue.py:210-234`) run
periodically during normal operation, so a job stuck `active` after a worker
crash mid-run gets reaped without waiting for the next app restart.

**Architecture:** `WorkerPool` (`app/main.py`) gains a `_stale_check_loop`
background thread, started alongside the existing worker threads in
`start()` and stopped by the existing `stop()`. The interval and timeout are
constructor parameters with module-level defaults, so tests can use short
intervals.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, threading, pytest

---

## Background for the worker

- `requeue_active_on_startup()` (`app/services/queue.py`) runs once at
  lifespan startup and moves any `active` rows back to `queued` — this
  handles "app restarted while a job was running".
- `detect_stale_jobs(session, timeout_minutes=10)` does something different:
  it marks `active` rows whose `claimed_at` is older than `timeout_minutes` as
  `error` with `error_code="stale_worker"`. This handles "a worker thread died
  or hung while the app is still running" — a case `requeue_active_on_startup`
  never sees because the app never restarts.
- Today `detect_stale_jobs` is only called from tests
  (`tests/unit/test_queue_stale.py`,
  `tests/integration/test_worker_lifecycle.py::test_stale_detection_marks_old_active_row_as_error`).
  This phase adds a production call site.
- `WorkerPool` (`app/main.py`) already has `start()`/`stop()`/`_worker_loop()`
  using `self._stop_event` (a `threading.Event`) and `self._threads` (a list
  of daemon threads joined in `stop()`). The new stale-check loop follows the
  same pattern: a daemon thread that wakes on an interval via
  `self._stop_event.wait(interval)` (which returns `True` immediately once
  `stop()` sets the event, so shutdown stays fast).

---

### Task 1: Add `_stale_check_loop` to `WorkerPool`

**Files:**
- Modify: `app/main.py`
- Test: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_worker_pool.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Download


def test_worker_pool_reaps_stale_jobs_periodically(db_session_visible) -> None:
    """A row claimed long ago is marked ``error`` by the periodic stale check."""
    row = Download(
        url="https://example.com/stale",
        status="active",
        progress=0.0,
        claimed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    from app.main import WorkerPool

    pool = WorkerPool(stale_check_interval_seconds=0.05, stale_timeout_minutes=1)
    pool.start(1)
    try:
        for _ in range(100):
            db_session_visible.refresh(row)
            if row.status == "error":
                break
            time.sleep(0.05)
    finally:
        pool.stop()

    assert row.status == "error"
    assert row.error_code == "stale_worker"
```

Add `import time` to the top of the file alongside the existing imports.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_worker_pool.py::test_worker_pool_reaps_stale_jobs_periodically -v`

Expected: FAIL — `WorkerPool(stale_check_interval_seconds=..., stale_timeout_minutes=...)`
raises `TypeError: __init__() got an unexpected keyword argument`.

- [ ] **Step 3: Implement the periodic stale check**

In `app/main.py`, add the import:

```diff
 from app.services.queue import (
     ClaimedDownload,
     claim_next,
+    detect_stale_jobs,
     is_cancel_requested,
     release_job,
     requeue_active_on_startup,
     update_progress,
 )
```

Add module-level defaults near the top of the file (after `logger = ...`):

```python
STALE_CHECK_INTERVAL_SECONDS = 60.0
STALE_TIMEOUT_MINUTES = 10
```

Update `WorkerPool.__init__` and `start`/add the new loop method:

```python
class WorkerPool:
    """Thread pool that consumes the ``downloads`` queue.

    The pool is a thin orchestration layer: each worker loop calls
    :func:`claim_next` to atomically claim the oldest queued row, then
    hands the job off to :meth:`_run_job` which drives the download
    through the existing services. State transitions, progress writes,
    and error mapping all happen through the existing service layer. A
    separate daemon thread periodically calls :func:`detect_stale_jobs`
    to reap rows left ``active`` by a crashed or hung worker.
    """

    def __init__(
        self,
        stale_check_interval_seconds: float = STALE_CHECK_INTERVAL_SECONDS,
        stale_timeout_minutes: int = STALE_TIMEOUT_MINUTES,
    ) -> None:
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._stale_check_interval_seconds = stale_check_interval_seconds
        self._stale_timeout_minutes = stale_timeout_minutes

    def start(self, concurrency: int) -> None:
        """Spawn ``concurrency`` daemon worker threads plus the stale-check thread."""
        for index in range(max(1, concurrency)):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"worker-{index}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        stale_thread = threading.Thread(
            target=self._stale_check_loop,
            name="stale-check",
            daemon=True,
        )
        stale_thread.start()
        self._threads.append(stale_thread)
```

Add the new loop method near `_worker_loop`:

```python
    def _stale_check_loop(self) -> None:
        """Periodically reap jobs left ``active`` by a crashed or hung worker."""
        while not self._stop_event.wait(self._stale_check_interval_seconds):
            with SessionLocal() as session:
                detect_stale_jobs(session, timeout_minutes=self._stale_timeout_minutes)
```

`stop()` requires no changes — it already sets `self._stop_event` and joins
every thread in `self._threads`, and `_stop_event.wait(...)` returns
immediately (`True`) once the event is set.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_worker_pool.py::test_worker_pool_reaps_stale_jobs_periodically -v`

Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS. If any test constructs `WorkerPool()` and asserts on
`len(pool._threads)` or similar, update it to account for the extra
stale-check thread.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/integration/test_worker_pool.py
git commit -m "feat: periodically reap stale active jobs"
```

---

## Self-Review Notes

- **Spec coverage:** `detect_stale_jobs` now has a production call site
  (Task 1), driven by a configurable interval/timeout so it can be tested with
  a short interval without waiting 10 minutes.
- **Placeholder scan:** no TBD/TODO; full code given for `__init__`, `start`,
  and `_stale_check_loop`.
- **Type consistency:** `WorkerPool(stale_check_interval_seconds=..., stale_timeout_minutes=...)`
  matches the constructor signature defined in Step 3; `detect_stale_jobs(session, timeout_minutes=...)`
  matches the existing signature in `app/services/queue.py`.
