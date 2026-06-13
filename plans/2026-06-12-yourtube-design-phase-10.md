# Phase 10: Queue Completion Toasts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add queue-page in-app completion toasts that announce newly finished jobs exactly once per browser page session, without adding push APIs or replaying historical completions on first load.

**Architecture:** Keep notifications scoped to the existing `/queue` page and reuse HTMX polling on `/queue/rows`. The server will expose a completion cursor based on `(finished_at, id)` and return only completions strictly after that cursor; Alpine on the queue page will persist the cursor and the set of announced job ids in `sessionStorage`, render the toast stack, and update the next poll request.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy 2.x, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   ├── routes/
│   │   └── pages.py
│   ├── services/
│   │   └── queue.py
│   ├── templates/
│   │   ├── pages/
│   │   │   └── queue.html
│   │   └── partials/
│   │       └── queue_rows.html
│   └── static/
│       └── css/app.css
└── tests/
    └── integration/
        ├── test_pages.py
        └── test_partials.py
```

Responsibilities:

- `app/services/queue.py` owns read-only completion cursor helpers so the route layer can ask for newly completed jobs without duplicating ordering logic.
- `app/routes/pages.py` seeds the initial completion cursor for `/queue` and threads cursor query params through `/queue/rows`.
- `app/templates/pages/queue.html` owns the Alpine notification state, the toast region, and the hidden HTMX cursor inputs.
- `app/templates/partials/queue_rows.html` keeps the current active-row markup and adds hidden completion markers plus cursor metadata for Alpine to consume.
- `app/static/css/app.css` adds toast-stack styles that match the existing editorial shell.
- `tests/integration/test_pages.py` covers the full queue-page shell and client-side wiring.
- `tests/integration/test_partials.py` covers the fragment-level completion markers and cursor filtering.

## Design Rules

- Scope notifications to `/queue` only in v1; do not make them global across the base template.
- Do not use a “latest N completed jobs” query. The server response must be cursor-based so completions are not dropped during busy polling windows.
- Use `(finished_at, id)` as the cursor so rows finished in the same timestamp bucket still have a deterministic order.
- Seed the initial cursor from the newest already-completed row on page load so old jobs do not trigger toasts when the user first opens `/queue`.
- Keep the current queue ledger limited to `queued` and `active` rows; completion markers are hidden metadata, not visible ledger entries.
- Keep HTMX polling on `#queue-rows`; do not introduce SSE, websockets, or a notification-specific endpoint.

### Task 1: Add completion cursor helpers in the queue service

**Files:**
- Modify: `app/services/queue.py`
- Test: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing partial-route tests**

```python
from datetime import datetime


def test_queue_rows_partial_includes_only_completions_after_cursor(db_session_visible) -> None:
    older = Download(
        url="https://example.com/old",
        title="Older done",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 10, 0, 0),
    )
    newer = Download(
        url="https://example.com/new",
        title="Newer done",
        status="done",
        progress=100.0,
        finished_at=datetime(2026, 6, 12, 10, 5, 0),
    )
    db_session_visible.add_all([older, newer])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get(
            "/queue/rows",
            params={"after_finished_at": "2026-06-12T10:00:00", "after_id": older.id},
        )

    assert response.status_code == 200
    assert f'data-completed-job-id="{newer.id}"' in response.text
    assert f'data-completed-job-id="{older.id}"' not in response.text


def test_queue_rows_partial_breaks_same_timestamp_ties_by_id(db_session_visible) -> None:
    finished_at = datetime(2026, 6, 12, 10, 0, 0)
    first = Download(
        url="https://example.com/first",
        title="First done",
        status="done",
        progress=100.0,
        finished_at=finished_at,
    )
    second = Download(
        url="https://example.com/second",
        title="Second done",
        status="done",
        progress=100.0,
        finished_at=finished_at,
    )
    db_session_visible.add_all([first, second])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get(
            "/queue/rows",
            params={"after_finished_at": "2026-06-12T10:00:00", "after_id": first.id},
        )

    assert response.status_code == 200
    assert f'data-completed-job-id="{second.id}"' in response.text
    assert f'data-completed-job-id="{first.id}"' not in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_partials.py::test_queue_rows_partial_includes_only_completions_after_cursor tests/integration/test_partials.py::test_queue_rows_partial_breaks_same_timestamp_ties_by_id -v`

Expected: FAIL because `/queue/rows` does not yet accept cursor params or return completion markers.

- [ ] **Step 3: Add cursor helpers in `app/services/queue.py`**

```python
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select, update


def get_latest_completion_cursor(session: Session) -> tuple[datetime | None, int]:
    """Return the newest completion cursor as ``(finished_at, id)``.

    The cursor seeds the queue page so historical completions do not
    toast on initial page load. When no completed jobs exist, return
    ``(None, 0)``.
    """
    stmt = (
        select(Download.finished_at, Download.id)
        .where(Download.status == "done", Download.finished_at.is_not(None))
        .order_by(Download.finished_at.desc(), Download.id.desc())
        .limit(1)
    )
    row = session.execute(stmt).one_or_none()
    if row is None:
        return None, 0
    return row[0], int(row[1])


def get_completed_jobs_after(
    session: Session,
    *,
    after_finished_at: datetime | None,
    after_id: int,
) -> list[Download]:
    """Return completed jobs strictly after ``(after_finished_at, after_id)``.

    Results are ordered oldest-to-newest so the browser announces
    completions in the same order they finished.
    """
    stmt = select(Download).where(Download.status == "done", Download.finished_at.is_not(None))
    if after_finished_at is not None:
        stmt = stmt.where(
            or_(
                Download.finished_at > after_finished_at,
                and_(Download.finished_at == after_finished_at, Download.id > after_id),
            )
        )
    stmt = stmt.order_by(Download.finished_at, Download.id)
    return list(session.execute(stmt).scalars())
```

- [ ] **Step 4: Run the tests to verify they still fail at the route/template layer**

Run: `uv run pytest tests/integration/test_partials.py::test_queue_rows_partial_includes_only_completions_after_cursor tests/integration/test_partials.py::test_queue_rows_partial_breaks_same_timestamp_ties_by_id -v`

Expected: FAIL because the route still does not pass the new helper output into the template.

- [ ] **Step 5: Commit**

```bash
git add app/services/queue.py tests/integration/test_partials.py
git commit -m "feat: add queue completion cursor helpers"
```

### Task 2: Thread the completion cursor through the queue routes and partial

**Files:**
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/queue_rows.html`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Extend the failing fragment tests to assert cursor metadata**

```python
def test_queue_rows_partial_exposes_completion_cursor_metadata(db_session_visible) -> None:
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
    assert 'data-completed-finished-at="2026-06-12T11:30:00"' in response.text
    assert f'data-completed-cursor-id="{done.id}"' in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_partials.py::test_queue_rows_partial_includes_only_completions_after_cursor tests/integration/test_partials.py::test_queue_rows_partial_breaks_same_timestamp_ties_by_id tests/integration/test_partials.py::test_queue_rows_partial_exposes_completion_cursor_metadata -v`

Expected: FAIL because the route/template still only render active queue rows.

- [ ] **Step 3: Update `app/routes/pages.py` to pass seeded completion data**

```python
from datetime import datetime

from app.services.queue import (
    cancel_job,
    enqueue_download,
    get_active_jobs,
    get_completed_jobs_after,
    get_latest_completion_cursor,
)


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    latest_finished_at, latest_id = get_latest_completion_cursor(session)
    return templates.TemplateResponse(
        request,
        "pages/queue.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": [],
            "after_finished_at": latest_finished_at.isoformat() if latest_finished_at else "",
            "after_id": latest_id,
        },
    )


@router.get("/queue/rows", response_class=HTMLResponse)
def queue_rows(
    request: Request,
    after_finished_at: str = Query(default=""),
    after_id: int = Query(default=0),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    cursor_dt = datetime.fromisoformat(after_finished_at) if after_finished_at else None
    return templates.TemplateResponse(
        request,
        "partials/queue_rows.html",
        {
            "rows": get_active_jobs(session),
            "completed_rows": get_completed_jobs_after(
                session,
                after_finished_at=cursor_dt,
                after_id=after_id,
            ),
        },
    )
```

- [ ] **Step 4: Update `app/templates/partials/queue_rows.html` to carry hidden completion markers**

```html
<div class="completion-markers" hidden>
  {% for row in completed_rows %}
  <span
    data-completed-job-id="{{ row.id }}"
    data-completed-job-title="{{ row.title or row.url }}"
    data-completed-finished-at="{{ row.finished_at.isoformat() if row.finished_at else '' }}"
    data-completed-cursor-id="{{ row.id }}"
  ></span>
  {% endfor %}
</div>

{% for row in rows %}
<article class="queue-entry" data-job-id="{{ row.id }}">
  <div class="queue-entry-main">
    <h2>{{ row.title or row.url }}</h2>
    <p class="queue-entry-status">{{ row.status }}</p>
  </div>
  <div class="queue-entry-progress">{{ "%.1f"|format(row.progress) }}%</div>
  <div class="queue-entry-action">
    {% if row.status in ("queued", "active") %}
    <button
      type="button"
      hx-post="/queue/cancel/{{ row.id }}"
      hx-target="#queue-rows"
      hx-swap="innerHTML"
    >
      Cancel
    </button>
    {% endif %}
  </div>
</article>
{% else %}
<article class="empty-state">
  <h2>No queued or active downloads.</h2>
</article>
{% endfor %}
```

- [ ] **Step 5: Run the partial tests to verify they pass**

Run: `uv run pytest tests/integration/test_partials.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/pages.py app/templates/partials/queue_rows.html tests/integration/test_partials.py
git commit -m "feat: expose queue completion markers in partial responses"
```

### Task 3: Add the queue-page toast shell and Alpine notification state

**Files:**
- Modify: `app/templates/pages/queue.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing queue-page shell tests**

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

    assert response.status_code == 200
    assert 'value="2026-06-12T09:15:00"' in response.text
    assert f'value="{done.id}"' in response.text
    assert f'data-completed-job-id="{done.id}"' not in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_renders_notification_shell tests/integration/test_pages.py::test_queue_page_seeds_cursor_without_initial_completion_markers -v`

Expected: FAIL because the queue page does not yet render toast state or cursor inputs.

- [ ] **Step 3: Add the toast shell and Alpine state in `app/templates/pages/queue.html`**

```html
{% extends "index.html" %}
{% block title %}YourTube | Queue{% endblock %}
{% block content %}
<section class="page-panel" x-data="queueNotifications()" x-init="boot()">
  <script>
    function queueNotifications() {
      return {
        toasts: [],
        seenCompletedJobs: new Set(
          JSON.parse(sessionStorage.getItem("yt-seen-completed-jobs") || "[]")
        ),
        afterFinishedAt: sessionStorage.getItem("yt-queue-after-finished-at") || "",
        afterId: sessionStorage.getItem("yt-queue-after-id") || "0",
        boot() {
          const seededFinishedAt = this.$refs.afterFinishedAt.dataset.initialValue || "";
          const seededAfterId = this.$refs.afterId.dataset.initialValue || "0";
          if (!this.afterFinishedAt && seededFinishedAt) {
            this.afterFinishedAt = seededFinishedAt;
          }
          if ((this.afterId === "" || this.afterId === "0") && seededAfterId !== "0") {
            this.afterId = seededAfterId;
          }
          this.persistCursor();
          this.scan(this.$root);
          document.body.addEventListener("htmx:afterSwap", (event) => {
            if (event.target && event.target.id === "queue-rows") {
              this.scan(event.target);
            }
          });
        },
        persistCursor() {
          sessionStorage.setItem("yt-queue-after-finished-at", this.afterFinishedAt);
          sessionStorage.setItem("yt-queue-after-id", this.afterId);
          sessionStorage.setItem(
            "yt-seen-completed-jobs",
            JSON.stringify([...this.seenCompletedJobs])
          );
        },
        scan(root) {
          root.querySelectorAll("[data-completed-job-id]").forEach((row) => {
            const jobId = row.dataset.completedJobId;
            if (this.seenCompletedJobs.has(jobId)) return;
            this.seenCompletedJobs.add(jobId);
            this.afterFinishedAt = row.dataset.completedFinishedAt || this.afterFinishedAt;
            this.afterId = row.dataset.completedCursorId || this.afterId;
            this.toasts.push({ id: jobId, title: row.dataset.completedJobTitle });
            this.persistCursor();
            window.setTimeout(() => this.dismiss(jobId), 5000);
          });
        },
        dismiss(jobId) {
          this.toasts = this.toasts.filter((toast) => toast.id !== jobId);
        },
      };
    }
  </script>

  <div class="panel-heading">
    <p class="eyebrow">Operations</p>
    <h1>Queue ledger</h1>
    <p>Queued and active downloads update automatically.</p>
  </div>

  <div id="toast-region" class="toast-region" aria-live="polite" aria-atomic="false">
    <template x-for="toast in toasts" :key="toast.id">
      <article class="toast">
        <p class="eyebrow">Completed</p>
        <h2 x-text="toast.title"></h2>
        <button type="button" class="toast-dismiss" @click="dismiss(toast.id)">Dismiss</button>
      </article>
    </template>
  </div>

  <input
    id="queue-after-finished-at"
    x-ref="afterFinishedAt"
    type="hidden"
    name="after_finished_at"
    x-model="afterFinishedAt"
    data-initial-value="{{ after_finished_at }}"
  />
  <input
    id="queue-after-id"
    x-ref="afterId"
    type="hidden"
    name="after_id"
    x-model="afterId"
    data-initial-value="{{ after_id }}"
  />

  <div id="queue-status"></div>
  <div class="queue-ledger">
    <div class="ledger-head">
      <span>Title</span><span>Status</span><span>Progress</span><span>Action</span>
    </div>
    <div
      id="queue-rows"
      hx-get="/queue/rows"
      hx-trigger="load, every 2s"
      hx-include="#queue-after-finished-at, #queue-after-id"
      hx-swap="innerHTML"
    >
      {% include "partials/queue_rows.html" %}
    </div>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 4: Run the page tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_renders_notification_shell tests/integration/test_pages.py::test_queue_page_seeds_cursor_without_initial_completion_markers -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/queue.html tests/integration/test_pages.py
git commit -m "feat: add queue page toast shell and cursor state"
```

### Task 4: Style the toast stack and finish the queue-page regression coverage

**Files:**
- Modify: `app/static/css/app.css`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing queue-page script/style regression test**

```python
def test_queue_page_notification_script_persists_cursor_and_seen_ids() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert "sessionStorage.getItem(\"yt-seen-completed-jobs\")" in response.text
    assert "sessionStorage.setItem(\"yt-queue-after-finished-at\"" in response.text
    assert "hx-include=\"#queue-after-finished-at, #queue-after-id\"" in response.text
    assert "dismiss(jobId)" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_notification_script_persists_cursor_and_seen_ids -v`

Expected: FAIL until the final script strings and queue-page wiring are in place.

- [ ] **Step 3: Add toast styles in `app/static/css/app.css`**

```css
.toast-region {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 30;
  display: grid;
  gap: 12px;
  width: min(360px, calc(100vw - 32px));
}

.toast {
  padding: 18px 20px;
  border: 1px solid rgba(47, 125, 77, 0.22);
  border-radius: var(--radius-md);
  background: rgba(255, 253, 249, 0.97);
  box-shadow: 0 14px 40px rgba(51, 49, 45, 0.12);
}

.toast h2 {
  margin: 6px 0 0;
  font-size: 1.15rem;
}

.toast-dismiss {
  margin-top: 12px;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--accent);
  font-weight: 700;
  cursor: pointer;
}

.toast-dismiss:hover {
  color: var(--accent-hover);
}

@media (max-width: 720px) {
  .toast-region {
    right: 14px;
    bottom: 14px;
    width: calc(100vw - 28px);
  }
}
```

- [ ] **Step 4: Run the relevant integration suites to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/css/app.css tests/integration/test_pages.py
git commit -m "feat: style queue completion toasts"
```

## Self-Review Notes

- Spec coverage: the plan now covers queue-scoped notifications, exact-once delivery within a page session, initial cursor seeding to avoid historical replay, hidden completion markers, and regression coverage at the page/partial seams.
- Placeholder scan: no `TODO`, `TBD`, or “similar to” placeholders remain.
- Type consistency: the plan consistently uses `after_finished_at`, `after_id`, `get_latest_completion_cursor()`, and `get_completed_jobs_after()`.
