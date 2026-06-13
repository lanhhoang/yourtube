# YourTube Implementation Plan — Phase 15: Simplify `claim_next` to return a job id

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `claim_next()` returns `int | None` (the claimed job's id) instead
of a `ClaimedDownload` dataclass whose extra `status`/`url` fields are only
ever read by tests.

**Architecture:** Remove `ClaimedDownload` from `app/services/queue.py`;
`claim_next`'s `RETURNING` clause projects only `Download.id`. `app/main.py`'s
`_worker_loop`/`_claim_once_for_test` pass the int straight to `_run_job`
(which already re-fetches the full row). Tests that asserted on
`.status`/`.url` are updated to reflect the new return type.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, pytest

---

## Background for the worker

- `ClaimedDownload` (`app/services/queue.py:26-39`) is a frozen dataclass with
  `id`, `status`, `url`. `claim_next()` (lines 91-124) projects all three via
  `RETURNING`.
- `_worker_loop` (`app/main.py:111-118`) only uses `claimed.id`:
  `self._run_job(claimed.id)`. `_run_job` (lines 140-149) re-fetches the full
  `Download` row from the database by id anyway — `status` and `url` from the
  claim are never used downstream.
- `status`/`url` are read only by `tests/unit/test_queue_claim.py`
  (`test_claim_next_returns_detached_safe_payload`,
  `test_claim_next_returns_oldest_queued_row`,
  `test_claim_next_is_idempotent_within_same_session`,
  `test_two_sessions_claim_next_do_not_double_claim`) and
  `tests/integration/test_worker_lifecycle.py`
  (`test_enqueue_claim_release_to_done`, `test_stale_detection_marks_old_active_row_as_error`)
  — both via `claimed.id` and `claimed.status`.
- `tests/integration/test_worker_pool.py::test_worker_loop_can_run_claimed_job_without_detached_instance`
  calls `pool._claim_once_for_test()` and then `pool._run_job(claimed.id)`.

---

### Task 1: Change `claim_next` to return `int | None`

**Files:**
- Modify: `app/services/queue.py`
- Modify: `tests/unit/test_queue_claim.py`
- Modify: `tests/integration/test_worker_lifecycle.py`

- [ ] **Step 1: Update the unit tests to expect an `int`**

In `tests/unit/test_queue_claim.py`:

```diff
-from app.services.queue import ClaimedDownload, claim_next, enqueue_download, release_job
+from app.services.queue import claim_next, enqueue_download, release_job
```

```diff
 def test_claim_next_returns_detached_safe_payload(db_session: Session) -> None:
-    """``claim_next`` returns a detached-safe dataclass that survives the session."""
+    """``claim_next`` returns the claimed job's id, which survives the session."""
     created = enqueue_download(db_session, DownloadCreate(url="https://example.com/watch?v=1"))

     claimed = claim_next(db_session)

     assert claimed is not None
-    assert isinstance(claimed, ClaimedDownload)
-    assert claimed.id == created.id
-    assert claimed.status == "active"
-    assert claimed.url == "https://example.com/watch?v=1"
+    assert claimed == created.id
```

```diff
 def test_claim_next_returns_oldest_queued_row(db_session: Session) -> None:
     """``claim_next`` returns the oldest queued row and marks it active."""
     first = enqueue_download(db_session, _make_payload("https://example.com/first"))
     enqueue_download(db_session, _make_payload("https://example.com/second"))

     claimed = claim_next(db_session)

     assert claimed is not None
-    assert claimed.id == first.id
-    assert claimed.status == "active"
+    assert claimed == first.id
     refreshed = db_session.get(Download, first.id)
     assert refreshed is not None
     assert refreshed.status == "active"
     assert refreshed.claimed_at is not None
```

```diff
 def test_claim_next_skips_non_queued_rows(db_session: Session) -> None:
     ...
     queued = enqueue_download(db_session, _make_payload("https://example.com/winner"))
     claimed = claim_next(db_session)

     assert claimed is not None
-    assert claimed.id == queued.id
+    assert claimed == queued.id
```

```diff
 def test_claim_next_is_idempotent_within_same_session(db_session: Session) -> None:
     """Calling ``claim_next`` twice claims one row, then returns ``None``."""
     enqueued = enqueue_download(db_session, _make_payload("https://example.com/only"))

     first = claim_next(db_session)
     second = claim_next(db_session)

     assert first is not None
-    assert first.id == enqueued.id
-    assert first.status == "active"
+    assert first == enqueued.id
     assert second is None
```

In `test_two_sessions_claim_next_do_not_double_claim`:

```diff
-    results: list[ClaimedDownload | None] = []
+    results: list[int | None] = []
```

```diff
     assert errors == []
     claimed = [row for row in results if row is not None]
     assert len(claimed) == 1
-    assert claimed[0].id == seeded.id
+    assert claimed[0] == seeded.id
```

- [ ] **Step 2: Update `test_worker_lifecycle.py`**

```diff
 def test_enqueue_claim_release_to_done(db_session: Session) -> None:
     """Happy path: enqueue -> claim -> release as done populates file metadata."""
     enqueued = enqueue_download(db_session, _make("https://example.com/happy"))
     claimed = claim_next(db_session)
     assert claimed is not None
-    assert claimed.id == enqueued.id
-    assert claimed.status == "active"
+    assert claimed == enqueued.id

     db_session.refresh(enqueued)
     assert enqueued.status == "active"
     assert enqueued.claimed_at is not None

     updated = release_job(
         db_session,
-        claimed.id,
+        claimed,
         status="done",
         file_path="/tmp/video.mp4",
         file_size=1024,
         media_format="mp4",
         resolution_height=1080,
     )
```

```diff
 def test_stale_detection_marks_old_active_row_as_error(db_session: Session) -> None:
     """A row claimed long ago is marked ``error`` with code ``stale_worker``."""
     enqueued = enqueue_download(db_session, _make("https://example.com/stale"))
     claimed = claim_next(db_session)
     assert claimed is not None
-    assert claimed.id == enqueued.id
+    assert claimed == enqueued.id
     far_past = datetime.now(timezone.utc) - timedelta(minutes=30)
     db_session.execute(
-        Download.__table__.update().where(Download.id == claimed.id).values(claimed_at=far_past)
+        Download.__table__.update().where(Download.id == claimed).values(claimed_at=far_past)
     )
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_lifecycle.py -v`

Expected: FAIL — `claim_next` still returns `ClaimedDownload`, so `claimed ==
created.id` is `False` (a dataclass is never equal to an int) and
`isinstance`/attribute-based assertions in the old code have been removed, so
the new equality assertions fail instead.

- [ ] **Step 4: Simplify `claim_next` and remove `ClaimedDownload`**

In `app/services/queue.py`, remove the `ClaimedDownload` dataclass entirely
(and the `from dataclasses import dataclass` import if nothing else in the
file uses `dataclass` — check with `grep -n dataclass app/services/queue.py`).

Update the module docstring's second paragraph (currently describing Phase 5
and `ClaimedDownload`) — replace it with:

```python
"""Queue service: enqueue, claim, release, cancel, stale recovery, startup requeue.

The service owns the lifecycle transitions of the ``downloads`` table.
Claims are transaction-safe: ``claim_next`` uses a conditional UPDATE with
``RETURNING`` so only one row is claimed, even under concurrency.
"""
```

Replace `claim_next`:

```python
def claim_next(session: Session) -> int | None:
    """Claim the oldest ``queued`` row and return its id.

    Uses a conditional UPDATE with ``RETURNING`` so the operation is
    atomic across concurrent workers. Returns ``None`` when no queued row
    is available.
    """
    subq: Select = (
        select(Download.id)
        .where(Download.status == "queued")
        .order_by(Download.created_at, Download.id)
        .limit(1)
    )
    stmt = (
        update(Download)
        .where(Download.id == subq.scalar_subquery(), Download.status == "queued")
        .values(status="active", claimed_at=func.current_timestamp())
        .returning(Download.id)
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    row_id = result.scalar_one_or_none()
    session.commit()
    return int(row_id) if row_id is not None else None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_lifecycle.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/queue.py tests/unit/test_queue_claim.py tests/integration/test_worker_lifecycle.py
git commit -m "feat: simplify claim_next to return a job id"
```

---

### Task 2: Update `WorkerPool` and remaining test references

**Files:**
- Modify: `app/main.py`
- Modify: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Update the failing test reference**

In `tests/integration/test_worker_pool.py::test_worker_loop_can_run_claimed_job_without_detached_instance`:

```diff
     claimed = pool._claim_once_for_test()
     assert claimed is not None
-    pool._run_job(claimed.id)
+    pool._run_job(claimed)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_worker_pool.py::test_worker_loop_can_run_claimed_job_without_detached_instance -v`

Expected: FAIL — `pool._claim_once_for_test()` still returns `ClaimedDownload`
(or, after Task 1, an `int` — but `_run_job(claimed)` where `claimed` is now
an `int` is actually correct already; the failure before this task's Step 3 is
that `_worker_loop`/`_claim_once_for_test` still reference the removed
`ClaimedDownload` type). Run this after Step 3 below if it passes immediately
— the important check is the full-suite run in Step 4.

- [ ] **Step 3: Update `app/main.py`**

Remove `ClaimedDownload` from the import:

```diff
 from app.services.queue import (
-    ClaimedDownload,
     claim_next,
     detect_stale_jobs,
     is_cancel_requested,
     release_job,
     requeue_active_on_startup,
     update_progress,
 )
```

Update `_worker_loop` and `_claim_once_for_test`:

```diff
     def _worker_loop(self) -> None:
         """Worker loop: claim a job, run it, repeat until stopped."""
         while not self._stop_event.is_set():
-            claimed = self._claim_once_for_test()
-            if claimed is None:
+            job_id = self._claim_once_for_test()
+            if job_id is None:
                 self._stop_event.wait(1.0)
                 continue
-            self._run_job(claimed.id)
+            self._run_job(job_id)

-    def _claim_once_for_test(self) -> ClaimedDownload | None:
-        """Claim the next queued job from a short-lived session.
-
-        Exposed for tests and reused by :meth:`_worker_loop`. The session
-        is closed before the caller uses the returned payload, so the
-        payload must be detached-safe (``ClaimedDownload`` is).
-        """
+    def _claim_once_for_test(self) -> int | None:
+        """Claim the next queued job id from a short-lived session.
+
+        Exposed for tests and reused by :meth:`_worker_loop`.
+        """
         with SessionLocal() as session:
             return claim_next(session)
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/integration/test_worker_pool.py
git commit -m "feat: drop ClaimedDownload, pass job id directly to worker"
```

---

## Self-Review Notes

- **Spec coverage:** `ClaimedDownload` removed (Task 1), `claim_next` returns
  `int | None`, `_worker_loop`/`_claim_once_for_test`/`_run_job` updated
  (Task 2), all 7 test sites that referenced `.id`/`.status`/`.url` or the
  `ClaimedDownload` type updated.
- **Placeholder scan:** no TBD/TODO; all diffs shown in full.
- **Type consistency:** `claim_next(session) -> int | None`,
  `_claim_once_for_test(self) -> int | None`, `_run_job(self, job_id: int)`
  (unchanged signature) — all consistent. `release_job(db_session, claimed, ...)`
  in `test_worker_lifecycle.py` now passes an `int`, matching `release_job`'s
  existing `job_id: int` parameter.
