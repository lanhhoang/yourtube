# YourTube Implementation Plan — Phase 12: Client-only queue completion toasts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the server-side `(finished_at, id)` completion cursor with a
single client-side `sessionStorage` Set as the only "have I already toasted
this completion" record.

**Architecture:** `app/services/queue.py` drops
`get_latest_completion_cursor`/`get_completed_jobs_after` in favor of a single
`get_recent_completed_jobs(session, limit=20)` that bounds result size without
any cursor state. `app/routes/pages.py`'s `/queue` and `/queue/rows` routes
both call this unconditionally. `app/templates/pages/queue.html`'s Alpine
component does a **silent** seed-scan on page load (marks initial completion
markers as "seen" without toasting) and a normal scan on every HTMX poll
(toasts anything not yet seen). The redundant `data-completed-cursor-id` and
now-unused `data-completed-finished-at` attributes are removed from
`app/templates/partials/queue_rows.html`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2, Alpine.js, HTMX, pytest

---

## Background for the worker

- Today, "has completion X already been announced?" is tracked twice:
  - Server: `(finished_at, id)` cursor, seeded by `get_latest_completion_cursor`
    on `/queue` page load, threaded through `/queue/rows` via hidden inputs
    (`#queue-after-finished-at`, `#queue-after-id`) and `hx-include`, filtered
    by `get_completed_jobs_after`.
  - Client: `seenCompletedJobs` Set in `sessionStorage["yt-seen-completed-jobs"]`.
- After this phase, only the client Set remains. The server always returns the
  last `limit` completed jobs (oldest-first); the client's first scan on page
  load is **silent** (seeds the Set without toasting — these are "old news"),
  and every subsequent scan (triggered by `htmx:afterSwap` on `#queue-rows`)
  toasts anything new.
- This relies on `seenCompletedJobs` already being session-scoped — a fresh
  tab/session has an empty Set, does a silent seed of whatever's currently in
  `completed_rows`, and only toasts genuinely new completions from then on.
  This matches current behavior (no cross-session toast leakage).

---

### Task 1: Add `get_recent_completed_jobs` and remove the cursor functions

**Files:**
- Modify: `app/services/queue.py`
- Test: `tests/unit/test_queue_completions.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_queue_completions.py`:

```python
"""Unit tests for ``app.services.queue.get_recent_completed_jobs``."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Download
from app.services.queue import get_recent_completed_jobs


def _done(session: Session, *, url: str, finished_at: datetime) -> Download:
    row = Download(url=url, status="done", progress=100.0, finished_at=finished_at)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_get_recent_completed_jobs_orders_oldest_first(db_session: Session) -> None:
    first = _done(db_session, url="https://example.com/a", finished_at=datetime(2026, 6, 12, 10, 0))
    second = _done(db_session, url="https://example.com/b", finished_at=datetime(2026, 6, 12, 11, 0))

    rows = get_recent_completed_jobs(db_session)

    assert [row.id for row in rows] == [first.id, second.id]


def test_get_recent_completed_jobs_respects_limit(db_session: Session) -> None:
    for index in range(5):
        _done(db_session, url=f"https://example.com/{index}", finished_at=datetime(2026, 6, 12, 10, index))

    rows = get_recent_completed_jobs(db_session, limit=3)

    assert len(rows) == 3
    # The 3 most recent, still returned oldest-first.
    assert [row.url for row in rows] == [
        "https://example.com/2",
        "https://example.com/3",
        "https://example.com/4",
    ]


def test_get_recent_completed_jobs_ignores_non_done_rows(db_session: Session) -> None:
    queued = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session.add(queued)
    db_session.commit()

    rows = get_recent_completed_jobs(db_session)

    assert rows == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_queue_completions.py -v`

Expected: FAIL with `ImportError: cannot import name 'get_recent_completed_jobs'`

- [ ] **Step 3: Replace the cursor functions in `app/services/queue.py`**

Remove `get_latest_completion_cursor` and `get_completed_jobs_after` (the two
functions at the end of the file) and replace both with:

```python
def get_recent_completed_jobs(session: Session, limit: int = 20) -> list[Download]:
    """Return the most recently completed jobs, oldest-first.

    Used to render completion markers on the queue page. The client
    deduplicates toasts via a sessionStorage set, so the server only
    needs to bound the result size — no cursor state is kept.
    """
    stmt = (
        select(Download)
        .where(Download.status == "done", Download.finished_at.is_not(None))
        .order_by(Download.finished_at.desc(), Download.id.desc())
        .limit(limit)
    )
    rows = list(session.execute(stmt).scalars())
    return list(reversed(rows))
```

Then check the top-of-file imports: `and_` and `or_` from `sqlalchemy` were
only used by `get_completed_jobs_after`. Run:

```bash
grep -n "and_\|or_" app/services/queue.py
```

If `and_`/`or_` no longer appear anywhere else in the file, remove them from
the `from sqlalchemy import ...` line. `datetime`/`timedelta`/`timezone`
remain in use by `detect_stale_jobs` — keep those.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_queue_completions.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/queue.py tests/unit/test_queue_completions.py
git commit -m "feat: replace completion cursor with bounded recent-completions query"
```

---

### Task 2: Update `/queue` and `/queue/rows` routes

**Files:**
- Modify: `app/routes/pages.py`

- [ ] **Step 1: Update imports**

```diff
 from app.services.queue import (
     cancel_job,
     enqueue_download,
     get_active_jobs,
-    get_completed_jobs_after,
-    get_latest_completion_cursor,
+    get_recent_completed_jobs,
 )
```

Also remove the now-unused `datetime` import if `/queue/rows` no longer takes
a `datetime` query param (check the top of `pages.py` — `from datetime import
datetime` was added for the `after_finished_at: datetime | None` query param).

- [ ] **Step 2: Simplify the `/queue` route**

```diff
 @router.get("/queue", response_class=HTMLResponse)
 def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
-    latest_finished_at, latest_id = get_latest_completion_cursor(session)
     return templates.TemplateResponse(
         request,
         "pages/queue.html",
         {
             "rows": get_active_jobs(session),
-            "completed_rows": [],
-            "after_finished_at": latest_finished_at.isoformat() if latest_finished_at else "",
-            "after_id": latest_id,
+            "completed_rows": get_recent_completed_jobs(session),
         },
     )
```

- [ ] **Step 3: Simplify the `/queue/rows` route**

```diff
 @router.get("/queue/rows", response_class=HTMLResponse)
-def queue_rows(
-    request: Request,
-    after_finished_at: datetime | None = Query(default=None),
-    after_id: int = Query(default=0),
-    session: Session = Depends(get_session),
-) -> HTMLResponse:
+def queue_rows(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
     return templates.TemplateResponse(
         request,
         "partials/queue_rows.html",
         {
             "rows": get_active_jobs(session),
-            "completed_rows": get_completed_jobs_after(
-                session,
-                after_finished_at=after_finished_at,
-                after_id=after_id,
-            ),
+            "completed_rows": get_recent_completed_jobs(session),
         },
     )
```

`Query` is still used by `library_page` and `library_rows` (the `q` param) —
keep that import.

- [ ] **Step 4: Commit (tests come in Task 4, this step alone will fail template rendering — that's expected and fixed in Task 3)**

```bash
git add app/routes/pages.py
git commit -m "feat: drop completion cursor from queue routes"
```

---

### Task 3: Update the Alpine notification script and completion markers

**Files:**
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/partials/queue_rows.html`

- [ ] **Step 1: Rewrite the Alpine component in `queue.html`**

Replace the entire `<script>` block in `app/templates/pages/queue.html` with:

```html
  <script>
    function queueNotifications() {
      return {
        toasts: [],
        seenCompletedJobs: new Set(
          JSON.parse(sessionStorage.getItem("yt-seen-completed-jobs") || "[]")
        ),
        boot() {
          this.scan(this.$root, { silent: true });
          document.body.addEventListener("htmx:afterSwap", (event) => {
            if (event.target && event.target.id === "queue-rows") {
              this.scan(event.target, { silent: false });
            }
          });
        },
        persistSeen() {
          sessionStorage.setItem(
            "yt-seen-completed-jobs",
            JSON.stringify([...this.seenCompletedJobs])
          );
        },
        scan(root, { silent }) {
          root.querySelectorAll("[data-completed-job-id]").forEach((row) => {
            const jobId = row.dataset.completedJobId;
            if (this.seenCompletedJobs.has(jobId)) return;
            this.seenCompletedJobs.add(jobId);
            if (!silent) {
              this.toasts.push({ id: jobId, title: row.dataset.completedJobTitle });
              window.setTimeout(() => this.dismiss(jobId), 5000);
            }
          });
          this.persistSeen();
        },
        dismiss(jobId) {
          this.toasts = this.toasts.filter((toast) => toast.id !== jobId);
        },
      };
    }
  </script>
```

- [ ] **Step 2: Remove the hidden cursor inputs and `hx-include`**

In the same file, remove these two `<input>` elements entirely:

```html
  <input
    id="queue-after-finished-at"
    x-ref="afterFinishedAt"
    type="hidden"
    name="after_finished_at"
    value="{{ after_finished_at }}"
    x-model="afterFinishedAt"
    data-initial-value="{{ after_finished_at }}"
  />
  <input
    id="queue-after-id"
    x-ref="afterId"
    type="hidden"
    name="after_id"
    value="{{ after_id }}"
    x-model="afterId"
    data-initial-value="{{ after_id }}"
  />
```

And on the `#queue-rows` div, remove the `hx-include` attribute:

```diff
     <div
       id="queue-rows"
       hx-get="/queue/rows"
       hx-trigger="load, every 2s"
-      hx-include="#queue-after-finished-at, #queue-after-id"
       hx-swap="innerHTML"
     >
       {% include "partials/queue_rows.html" %}
     </div>
```

- [ ] **Step 3: Simplify completion markers in `queue_rows.html`**

In `app/templates/partials/queue_rows.html`, remove the now-unused
`data-completed-finished-at` and `data-completed-cursor-id` attributes:

```diff
 <div class="completion-markers" hidden>
   {% for row in completed_rows %}
   <span
     data-completed-job-id="{{ row.id }}"
     data-completed-job-title="{{ row.title or row.url }}"
-    data-completed-finished-at="{{ row.finished_at.isoformat() if row.finished_at else '' }}"
-    data-completed-cursor-id="{{ row.id }}"
   ></span>
   {% endfor %}
 </div>
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/pages/queue.html app/templates/partials/queue_rows.html
git commit -m "feat: dedupe queue completion toasts client-side only"
```

---

### Task 4: Update integration tests for the new behavior

**Files:**
- Modify: `tests/integration/test_pages.py`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Update `test_pages.py`**

Replace these three tests (around lines 301-343):

```python
def test_queue_page_renders_notification_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'x-data="queueNotifications()"' in response.text
    assert 'id="toast-region"' in response.text
    assert 'id="queue-after-finished-at"' in response.text
    assert 'id="queue-after-id"' in response.text


def test_queue_page_seeds_cursor_without_initial_completion_markers(db_session_visible) -> None:
    done = Download(
        url="https://example.com/done",
        title="Already finished",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 9, 15, 0),
    )
    db_session_visible.add(done)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue")

    parser = _InputValueParser()
    parser.feed(response.text)

    assert response.status_code == 200
    assert parser.values["queue-after-finished-at"] == "2026-06-12T09:15:00"
    assert parser.values["queue-after-id"] == str(done.id)
    assert f'data-completed-job-id="{done.id}"' not in response.text


def test_queue_page_notification_script_persists_cursor_and_seen_ids() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'sessionStorage.getItem("yt-seen-completed-jobs")' in response.text
    assert 'sessionStorage.setItem("yt-queue-after-finished-at"' in response.text
    assert 'hx-include="#queue-after-finished-at, #queue-after-id"' in response.text
    assert "dismiss(jobId)" in response.text
```

with:

```python
def test_queue_page_renders_notification_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'x-data="queueNotifications()"' in response.text
    assert 'id="toast-region"' in response.text


def test_queue_page_renders_recent_completions(db_session_visible) -> None:
    done = Download(
        url="https://example.com/done",
        title="Already finished",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 9, 15, 0),
    )
    db_session_visible.add(done)
    db_session_visible.commit()
    db_session_visible.refresh(done)

    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert f'data-completed-job-id="{done.id}"' in response.text


def test_queue_page_notification_script_seeds_silently_and_dedupes() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'sessionStorage.getItem("yt-seen-completed-jobs")' in response.text
    assert "scan(this.$root, { silent: true })" in response.text
    assert "dismiss(jobId)" in response.text
    assert "queue-after-finished-at" not in response.text
    assert "hx-include" not in response.text
```

If `_InputValueParser` (used by the old
`test_queue_page_seeds_cursor_without_initial_completion_markers`) is not used
by any other test in this file, remove its class definition too — check with
`grep -n "_InputValueParser" tests/integration/test_pages.py`.

- [ ] **Step 2: Update `test_partials.py`**

Remove these tests entirely:
- `test_queue_rows_partial_includes_only_completions_after_cursor`
- `test_queue_rows_partial_breaks_same_timestamp_ties_by_id`
- `test_queue_rows_partial_rejects_invalid_cursor_value`

Replace `test_queue_rows_partial_exposes_completion_cursor_metadata` with:

```python
def test_queue_rows_partial_exposes_completion_markers(db_session_visible) -> None:
    done = Download(
        url="https://example.com/done",
        title="Done row",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 11, 30, 0),
    )
    db_session_visible.add(done)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert f'data-completed-job-id="{done.id}"' in response.text
    assert 'data-completed-job-title="Done row"' in response.text
    assert "data-completed-finished-at" not in response.text
    assert "data-completed-cursor-id" not in response.text
```

If `datetime` becomes unused in `test_partials.py` after removing the cursor
tests, keep it — `test_queue_rows_partial_exposes_completion_markers` still
uses it.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "test: update queue completion tests for client-only dedup"
```

---

## Self-Review Notes

- **Spec coverage:** server cursor functions removed (Task 1), routes
  simplified (Task 2), client-side dedup is now the sole "seen" record with a
  silent first-load seed to avoid replaying history (Task 3), redundant
  `data-completed-cursor-id`/`data-completed-finished-at` attributes removed
  (Task 3), tests updated to match (Task 4).
- **Placeholder scan:** no TBD/TODO; all steps show full code/diffs.
- **Type consistency:** `get_recent_completed_jobs(session, limit=20)` is used
  identically in `queue_page` and `queue_rows`; `data-completed-job-id` /
  `data-completed-job-title` are the only attributes referenced by both the
  template and the Alpine script after this phase.
