# Phase 10: In-App Completion Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-app completion notifications that appear when queue entries transition to `done`, without introducing browser permission prompts or new push infrastructure.

**Architecture:** Reuse the existing queue polling loop and HTML surfaces rather than adding websockets or a notification-specific API. The browser stores a small in-memory/session-backed set of completed job IDs it has already announced, and Alpine manages the toast list and dismissal behavior.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy 2.x, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   ├── templates/
│   │   ├── index.html
│   │   ├── pages/queue.html
│   │   └── partials/
│   │       └── queue_rows.html
│   └── services/
│       └── queue.py
│   └── static/
│       └── css/app.css
└── tests/
    └── integration/
        └── test_pages.py
```

Responsibilities:

- `app/templates/index.html` owns the global toast region.
- `app/services/queue.py` exposes a read-only helper for recently finished jobs so queue polling can report completions without changing the visible queue ledger.
- `app/templates/pages/queue.html` exposes the Alpine notification store around the existing queue polling area.
- `app/templates/partials/queue_rows.html` carries both visible active rows and hidden recent-completion markers the browser can observe.
- `app/static/css/app.css` styles the toast stack.

### Task 1: Add a toast region and recent-completion markers

**Files:**
- Modify: `app/services/queue.py`
- Modify: `app/templates/index.html`
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/partials/queue_rows.html`
- Modify: `app/static/css/app.css`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing notification markup tests**

```python
def test_queue_page_renders_notification_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert 'id="toast-region"' in response.text
    assert 'x-data="queueNotifications()"' in response.text


def test_queue_rows_include_recent_completion_markers(db_session_visible) -> None:
    done = Download(url="https://example.com/d", title="Done row", status="done", progress=100.0)
    db_session_visible.add(done)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert 'data-completed-job-id="' in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_renders_notification_shell tests/integration/test_pages.py::test_queue_rows_include_recent_completion_markers -v`

Expected: FAIL because there is no toast region or completed-job metadata yet.

- [ ] **Step 3: Add a read-only recent-completions helper and hidden markers**

```python
# app/services/queue.py
def get_recently_finished_jobs(session: Session, limit: int = 5) -> list[Download]:
    stmt = (
        select(Download)
        .where(Download.status == "done")
        .order_by(Download.finished_at.desc(), Download.id.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())
```

```html
<!-- app/templates/index.html -->
<section id="toast-region" class="toast-region"></section>
```

```html
<!-- app/templates/pages/queue.html -->
<section class="page-panel" x-data="queueNotifications()" x-init="boot()">
```

```html
<!-- app/templates/partials/queue_rows.html -->
<div class="completion-markers" hidden>
  {% for row in completed_rows %}
  <span data-completed-job-id="{{ row.id }}" data-completed-job-title="{{ row.title or row.url }}"></span>
  {% endfor %}
</div>

<article class="queue-entry" data-job-id="{{ row.id }}">
```

- [ ] **Step 4: Add toast styles**

```css
.toast-region {
  position: fixed;
  right: 20px;
  bottom: 20px;
  display: grid;
  gap: 12px;
  z-index: 50;
}

.toast {
  padding: 14px 16px;
  border-radius: 12px;
  background: #fffdf9;
  box-shadow: 0 14px 40px rgba(51, 49, 45, 0.12);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`

Expected: PASS for toast-region and completed-row markers.

- [ ] **Step 6: Commit**

```bash
git add app/services/queue.py app/templates/index.html app/templates/pages/queue.html app/templates/partials/queue_rows.html app/static/css/app.css tests/integration/test_pages.py
git commit -m "feat: add queue notification shell and completion markers"
```

### Task 2: Announce completed jobs once per page session

**Files:**
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/index.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing once-only notification test**

```python
def test_queue_page_notification_script_uses_seen_job_tracking() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert "sessionStorage" in response.text
    assert "seenCompletedJobs" in response.text
    assert "queueNotifications()" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_notification_script_uses_seen_job_tracking -v`

Expected: FAIL because the queue page does not define notification state or duplicate-suppression logic.

- [ ] **Step 3: Add Alpine notification state with duplicate suppression**

```html
<script>
  function queueNotifications() {
    return {
      toasts: [],
      seenCompletedJobs: new Set(JSON.parse(sessionStorage.getItem("yt-seen-completed-jobs") || "[]")),
      boot() {
        this.scan(document);
        document.body.addEventListener("htmx:afterSwap", (event) => {
          this.scan(event.target);
        });
      },
      scan(root) {
        root.querySelectorAll("[data-completed-job-id]").forEach((row) => {
          const jobId = row.dataset.completedJobId;
          if (this.seenCompletedJobs.has(jobId)) return;
          this.seenCompletedJobs.add(jobId);
          sessionStorage.setItem("yt-seen-completed-jobs", JSON.stringify([...this.seenCompletedJobs]));
          this.toasts.push({ id: jobId, title: row.dataset.completedJobTitle });
        });
      },
    };
  }
</script>
```

- [ ] **Step 4: Run the page tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/queue.html app/templates/index.html tests/integration/test_pages.py
git commit -m "feat: announce completed jobs once per page session"
```
