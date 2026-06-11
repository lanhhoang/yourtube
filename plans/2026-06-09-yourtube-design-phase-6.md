# Phase 6: Media Shelf UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the server-rendered HTMX UI into the approved Media Shelf experience with a stronger home hub, more visual library presentation, a compact active-jobs strip, and surfaced Phase 5 diagnostics.

**Architecture:** Keep the existing FastAPI + Jinja + HTMX stack. Rework page hierarchy, templates, partials, and stylesheet structure so the browser experience becomes library-first and visually intentional, while preserving the existing JSON APIs and HTML-over-the-wire interaction model.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, CSS, pytest

---

## File Structure

```
yourtube/
├── app/
│   ├── routes/
│   │   └── pages.py
│   ├── static/
│   │   ├── css/
│   │   │   └── app.css
│   │   └── vendor/htmx.min.js
│   └── templates/
│       ├── index.html
│       ├── pages/
│       │   ├── home.html
│       │   ├── queue.html
│       │   ├── library.html
│       │   └── settings.html
│       └── partials/
│           ├── home_active_jobs.html   # new
│           ├── home_library_cards.html # new
│           ├── info_result.html
│           ├── library_rows.html
│           ├── queue_rows.html
│           ├── runtime_status.html
│           └── settings_form.html
└── tests/
    └── integration/
        ├── test_pages.py
        └── test_partials.py
```

Responsibilities:

- `app/routes/pages.py` prepares richer page context for the home hub and visual library views.
- `app/static/css/app.css` becomes the primary place for the Media Shelf design system and responsive layout rules.
- `app/templates/index.html` defines the new shell, navigation, and shared framing.
- `app/templates/pages/*.html` define the page-specific flows.
- `app/templates/partials/*.html` keep HTMX fragment updates aligned with the new layout.

## UI Contract For Phase 6

- Keep the same backend stack and existing JSON APIs.
- Home page becomes the primary destination.
- Home page must contain:
  - quick download entry
  - result/enqueue area
  - compact active-jobs strip
  - recent/completed library preview
- `/queue` remains the full management page for progress and cancellation.
- `/library` becomes more visual than a plain table, but still supports download and delete actions.
- `/settings` keeps operational controls and displays the Phase 5 diagnostics status.
- UI must load and remain usable on desktop and mobile.
- Do not introduce a SPA, frontend framework, or custom browser state management layer.

### Task 1: Reshape page data flow for the home hub

**Files:**
- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing home-page data test**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_home_page_renders_active_jobs_and_recent_library_preview(db_session_visible) -> None:
    db_session_visible.add_all(
        [
            Download(url="https://example.com/q", title="Queued clip", status="queued", progress=0.0),
            Download(url="https://example.com/d1", title="Done clip 1", status="done", progress=100.0),
            Download(url="https://example.com/d2", title="Done clip 2", status="done", progress=100.0),
        ]
    )
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Queued clip" in response.text
    assert "Done clip 1" in response.text
    assert "Recent downloads" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_home_page_renders_active_jobs_and_recent_library_preview -v`
Expected: FAIL because `/` currently renders only the bare download form.

- [ ] **Step 3: Extend `home()` to load hub data**

```python
# app/routes/pages.py
from app.services.library import get_library
from app.services.queue import get_active_jobs


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    active_rows = get_active_jobs(session)
    library_rows = get_library(session)[:6]
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {
            "active_rows": active_rows,
            "library_rows": library_rows,
        },
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_pages.py::test_home_page_renders_active_jobs_and_recent_library_preview -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: load media shelf home page data"
```

### Task 2: Replace the shared shell and add a real stylesheet

**Files:**
- Modify: `app/templates/index.html`
- Create: `app/static/css/app.css`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing shell/style test**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_layout_loads_stylesheet_and_media_shelf_navigation() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        css = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "Recent downloads" in response.text
    assert "Library" in response.text
    assert css.status_code == 200
    assert "--page-bg" in css.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_layout_loads_stylesheet_and_media_shelf_navigation -v`
Expected: FAIL because `app/static/css/app.css` does not exist.

- [ ] **Step 3: Rewrite the shell and add the base stylesheet**

```html
<!-- app/templates/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}YourTube{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='css/app.css') }}" />
    <script defer src="{{ url_for('static', path='vendor/htmx.min.js') }}"></script>
  </head>
  <body class="app-body">
    <header class="site-header">
      <a class="brand" href="/">YourTube</a>
      <nav class="site-nav">
        <a href="/">Home</a>
        <a href="/queue">Queue</a>
        <a href="/library">Library</a>
        <a href="/settings">Settings</a>
      </nav>
    </header>
    <main class="page-shell">{% block content %}{% endblock %}</main>
  </body>
</html>
```

```css
/* app/static/css/app.css */
:root {
  --page-bg: #f4efe6;
  --panel-bg: rgba(255, 252, 246, 0.88);
  --panel-border: #d8c9af;
  --text-main: #1f1a14;
  --text-muted: #645847;
  --accent: #0f766e;
  --accent-strong: #0b5d57;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_pages.py::test_layout_loads_stylesheet_and_media_shelf_navigation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/index.html app/static/css/app.css tests/integration/test_pages.py
git commit -m "feat: add media shelf shell and base styles"
```

### Task 3: Build the new home hub partials and layout

**Files:**
- Modify: `app/templates/pages/home.html`
- Create: `app/templates/partials/home_active_jobs.html`
- Create: `app/templates/partials/home_library_cards.html`
- Modify: `app/templates/partials/info_result.html`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing home partial test**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_home_partials_render_media_shelf_sections(db_session_visible) -> None:
    db_session_visible.add(
        Download(url="https://example.com/done", title="Shelf item", status="done", progress=100.0)
    )
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/")

    assert "Active downloads" in response.text
    assert "Recent downloads" in response.text
    assert "Shelf item" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_partials.py::test_home_partials_render_media_shelf_sections -v`
Expected: FAIL because the new partials and headings do not exist.

- [ ] **Step 3: Rebuild the home page around the hub sections**

```html
<!-- app/templates/pages/home.html -->
{% extends "index.html" %}
{% block title %}YourTube | Home{% endblock %}
{% block content %}
<section class="hero-panel">
  <div class="hero-copy">
    <p class="eyebrow">Media Shelf</p>
    <h1>Collect videos into a clean personal library.</h1>
    <p class="lede">Paste a URL, inspect formats, queue the job, and keep recent downloads within reach.</p>
  </div>
  <div class="hero-form">
    <!-- existing info form stays here -->
  </div>
</section>

<section class="home-grid">
  {% include "partials/home_active_jobs.html" %}
  {% include "partials/home_library_cards.html" %}
</section>
{% endblock %}
```

- [ ] **Step 4: Keep the enqueue fragment aligned with the new layout**

```html
<!-- app/templates/partials/info_result.html -->
<section class="panel panel-info">
  <div class="info-header">
    <h2>{{ title or url }}</h2>
    <p class="meta">{{ uploader or "Unknown uploader" }}</p>
  </div>
  <!-- existing hidden inputs and form behavior stay intact -->
</section>
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_partials.py::test_home_partials_render_media_shelf_sections -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/pages/home.html app/templates/partials/home_active_jobs.html app/templates/partials/home_library_cards.html app/templates/partials/info_result.html tests/integration/test_partials.py
git commit -m "feat: build media shelf home hub sections"
```

### Task 4: Refactor queue, library, and settings pages to match the new hierarchy

**Files:**
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/pages/library.html`
- Modify: `app/templates/pages/settings.html`
- Modify: `app/templates/partials/queue_rows.html`
- Modify: `app/templates/partials/library_rows.html`
- Modify: `tests/integration/test_pages.py`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing page hierarchy tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_queue_page_is_detailed_management_view() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert "Manage active downloads" in response.text


def test_library_page_uses_visual_collection_language() -> None:
    with TestClient(app) as client:
        response = client.get("/library")

    assert response.status_code == 200
    assert "Browse your library" in response.text


def test_settings_page_keeps_runtime_status_visible() -> None:
    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert "Runtime status" in response.text or "Settings" in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`
Expected: FAIL because the current page copy and table-first templates do not match the new hierarchy.

- [ ] **Step 3: Update page copy and structure**

```html
<!-- queue.html -->
<section class="panel page-intro">
  <h1>Manage active downloads</h1>
  <p>Track progress, cancel work in flight, and keep the queue moving.</p>
</section>
```

```html
<!-- library.html -->
<section class="panel page-intro">
  <h1>Browse your library</h1>
  <p>Search finished downloads, reopen files, or prune items you no longer want.</p>
</section>
```

```html
<!-- settings.html -->
<section class="panel page-intro">
  <h1>Settings</h1>
  <p>Control storage, concurrency, and runtime readiness.</p>
  {% include "partials/runtime_status.html" %}
</section>
```

- [ ] **Step 4: Update partials to match the new visual treatment**

```html
<!-- queue_rows.html -->
{% for row in rows %}
<tr class="queue-row" data-job-id="{{ row.id }}">
  <td>
    <strong>{{ row.title or row.url }}</strong>
    <div class="row-meta">{{ row.status }}</div>
  </td>
  <td>{{ "%.1f"|format(row.progress) }}%</td>
  <td>
    {% if row.status in ("queued", "active") %}
    <button
      type="button"
      hx-post="/queue/cancel/{{ row.id }}"
      hx-target="#queue-rows"
      hx-swap="innerHTML"
    >Cancel</button>
    {% endif %}
  </td>
</tr>
{% endfor %}
```

```html
<!-- library_rows.html -->
{% for row in rows %}
<tr class="library-row" data-job-id="{{ row.id }}">
  <td>
    <strong>{{ row.title or row.url }}</strong>
    <div class="row-meta">{{ row.uploader or "Unknown uploader" }}</div>
  </td>
  <td>
    <a href="/api/downloads/{{ row.id }}/file">Download file</a>
    <button
      type="button"
      hx-delete="/library/delete/{{ row.id }}?q={{ query | urlencode }}"
      hx-target="#library-rows"
      hx-swap="innerHTML"
    >Delete</button>
  </td>
</tr>
{% endfor %}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/pages/queue.html app/templates/pages/library.html app/templates/pages/settings.html app/templates/partials/queue_rows.html app/templates/partials/library_rows.html tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "feat: refactor queue library and settings pages for media shelf"
```

### Task 5: Finish responsive styling and run UI regression checks

**Files:**
- Modify: `app/static/css/app.css`
- Modify: `README.md`

- [ ] **Step 1: Add responsive layout and component styles**

Add CSS for:

- hero panel
- home grid
- status panel
- card-style library preview
- queue/library tables
- mobile navigation and stacked layout below `768px`

- [ ] **Step 2: Update README screenshots/copy if present**

Refresh any UI description that still describes the pre-Phase-6 table-first layout.

- [ ] **Step 3: Run the integration suite**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py tests/integration/test_api_downloads.py tests/integration/test_api_library.py -v`
Expected: PASS

- [ ] **Step 4: Do a manual browser smoke check**

Run: `uv run uvicorn app.main:app --reload`
Expected:

- home page shows quick download, active jobs, and recent downloads
- queue polling still updates
- library search and delete still work
- settings save/reset still work
- layout remains usable on mobile-width viewport

- [ ] **Step 5: Commit**

```bash
git add app/static/css/app.css README.md
git commit -m "style: complete media shelf ui refactor"
```

## Self-Review (Phase 6)

- Home is the hub and `/queue` remains the detailed management page.
- The redesign stays inside Jinja + HTMX.
- Phase 5 diagnostics are visible in the new settings experience.
- Tests verify both visual hierarchy copy and existing HTMX behavior.

## End of Phase 6

Deliverable: the server-rendered UI presents the approved Media Shelf experience with a stronger home hub, a more visual library flow, preserved queue/settings behavior, and responsive styling across desktop and mobile.
