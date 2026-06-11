# Phase 3B: HTMX Server-Rendered UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the functional HTMX-driven server-rendered web UI on top of the completed Phase 3A backend, covering video info lookup, enqueue, queue polling, library management, and settings editing.

**Architecture:** Page routes render full Jinja pages with useful initial state from the existing services, while browser-facing HTMX endpoints return HTML fragments for lookup, enqueue, queue refreshes, library actions, and settings changes. The existing Phase 3A JSON endpoints remain intact as backend/public contracts, but the browser UI is HTML-over-the-wire and uses a self-hosted HTMX asset instead of an app-specific JavaScript module.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, CSS, pytest

---

## File Structure

```
yourtube/
├── app/
│   ├── main.py
│   ├── routes/
│   │   └── pages.py
│   ├── static/
│   │   ├── css/app.css
│   │   └── vendor/htmx.min.js
│   └── templates/
│       ├── index.html
│       ├── pages/
│       │   ├── home.html
│       │   ├── queue.html
│       │   ├── library.html
│       │   └── settings.html
│       └── partials/
│           ├── queue_rows.html
│           └── library_rows.html
└── tests/
    └── integration/
        ├── test_pages.py
        └── test_partials.py
```

Responsibilities:

- `app/main.py` mounts static assets and includes the page router next to the existing API router.
- `app/routes/pages.py` owns page rendering plus browser-facing HTML fragment and mutation routes.
- `app/templates/index.html` owns the shared layout and self-hosted HTMX script include.
- `app/templates/pages/*.html` own full-page markup and HTMX attributes for forms, buttons, polling, and fragment targets.
- `app/templates/partials/*.html` own queue/library row fragments and empty states.
- `app/static/vendor/htmx.min.js` is the only required browser-side interaction layer in Phase 3B.

## Runtime Contract For Phase 3B

- Do not add new JSON queue or library list endpoints.
- Do not change the existing Phase 3A API shapes.
- Do not use a CDN-hosted HTMX asset; serve it locally from `app/static/`.
- Initial page loads must be useful without waiting for JavaScript:
  - `/queue` renders current queued/active rows on first response.
  - `/library` renders current done rows on first response.
  - `/settings` renders persisted values on first response.
- HTMX progressively enhances the pages:
  - `/` uses an HTMX form post to an HTML endpoint that returns the info/enqueue fragment
  - the enqueue form posts to an HTML mutation endpoint that returns a status fragment and queue updates
  - `/queue` polls `GET /queue/rows` every 2 seconds with HTMX and posts cancels through HTML mutation endpoints
  - `/library` fetches `GET /library/rows?q=...` through HTMX and deletes entries with HTMX `DELETE`
  - `/settings` saves with HTMX `PUT` and resets with HTMX `POST`
- Browser-facing HTMX routes return HTML fragments or out-of-band swaps, not JSON error envelopes.
- The Phase 3A JSON APIs remain intact, but they are not the primary browser UI contract in Phase 3B.

### Task 1: Add page routing, self-hosted HTMX, and shared `index.html` layout

**Files:**
- Create: `app/routes/pages.py`
- Modify: `app/main.py`
- Create: `app/templates/index.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `app/static/vendor/htmx.min.js`
- Create: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing page tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download
from app.services.settings import set_settings_batch


def test_home_queue_library_and_settings_pages_render() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        queue = client.get("/queue")
        library = client.get("/library")
        settings = client.get("/settings")

    assert home.status_code == 200
    assert "Download a video" in home.text
    assert queue.status_code == 200
    assert "Active Queue" in queue.text
    assert library.status_code == 200
    assert "Library" in library.text
    assert settings.status_code == 200
    assert "Settings" in settings.text


def test_queue_and_library_pages_render_initial_rows(db_session_visible) -> None:
    queued = Download(url="https://example.com/q", title="Queued row", status="queued", progress=0.0)
    done = Download(url="https://example.com/d", title="Done row", status="done", progress=100.0)
    db_session_visible.add_all([queued, done])
    db_session_visible.commit()

    with TestClient(app) as client:
        queue = client.get("/queue")
        library = client.get("/library")

    assert "Queued row" in queue.text
    assert "Done row" in library.text


def test_settings_page_renders_persisted_values(db_session_visible) -> None:
    set_settings_batch(
        db_session_visible,
        {
            "max_concurrent": "3",
            "proxy_url": "http://proxy.internal:8080",
            "cookies_path": "/tmp/cookies.txt",
            "downloads_dir": "/tmp/downloads",
        },
    )

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'value="3"' in response.text
    assert 'value="http://proxy.internal:8080"' in response.text
    assert 'value="/tmp/cookies.txt"' in response.text
    assert 'value="/tmp/downloads"' in response.text


def test_pages_extend_index_layout_and_load_local_htmx() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        htmx = client.get("/static/vendor/htmx.min.js")

    assert response.status_code == 200
    assert '/static/vendor/htmx.min.js' in response.text
    assert 'hx-' in response.text
    assert htmx.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: FAIL with `404 Not Found` for the page routes and missing HTMX asset

- [ ] **Step 3: Write the minimal implementation**

```python
# app/routes/pages.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.library import get_library, search_library
from app.services.queue import get_active_jobs
from app.services.settings import get_all_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/home.html", {"request": request})


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        "pages/queue.html",
        {"request": request, "rows": get_active_jobs(session)},
    )


@router.get("/library", response_class=HTMLResponse)
def library_page(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        "pages/library.html",
        {"request": request, "rows": rows, "query": q},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        "pages/settings.html",
        {"request": request, "settings_values": get_all_settings(session)},
    )
```

```python
# app/main.py
from fastapi.staticfiles import StaticFiles

from app.routes.pages import router as pages_router

app = FastAPI(title="YourTube", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "app" / "static"), name="static")
app.include_router(api_router)
app.include_router(pages_router)
```

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
  <body>
    <header class="site-header">
      <nav class="site-nav">
        <a href="/">Download</a>
        <a href="/queue">Queue</a>
        <a href="/library">Library</a>
        <a href="/settings">Settings</a>
      </nav>
    </header>
    <main class="page-shell">{% block content %}{% endblock %}</main>
    <section id="flash-region"></section>
  </body>
</html>
```

```html
<!-- app/templates/pages/queue.html -->
{% extends "index.html" %}
{% block title %}YourTube | Queue{% endblock %}
{% block content %}
<section>
  <h1>Active Queue</h1>
  <p>Queued and active downloads update automatically.</p>
  <div id="queue-status"></div>
  <table class="data-table">
    <thead>
      <tr><th>Title</th><th>Status</th><th>Progress</th><th>Action</th></tr>
    </thead>
    <tbody id="queue-rows" hx-get="/queue/rows" hx-trigger="load, every 2s" hx-swap="innerHTML">
      {% include "partials/queue_rows.html" %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/routes/pages.py app/templates/index.html app/templates/pages/home.html app/templates/pages/queue.html app/templates/pages/library.html app/templates/pages/settings.html app/static/vendor/htmx.min.js tests/integration/test_pages.py
git commit -m "feat: add HTMX page routes and shared index layout"
```

### Task 2: Add queue and library HTMX fragment routes

**Files:**
- Modify: `app/routes/pages.py`
- Create: `app/templates/partials/queue_rows.html`
- Create: `app/templates/partials/library_rows.html`
- Create: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing partial tests**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import Download


def test_queue_rows_partial_renders_fragment_only_html(db_session_visible) -> None:
    first = Download(url="https://example.com/a", title="First", status="queued", progress=0.0)
    second = Download(url="https://example.com/b", title="Second", status="active", progress=42.5)
    db_session_visible.add_all([first, second])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert "<tbody" not in response.text
    assert response.text.index("First") < response.text.index("Second")
    assert 'hx-post="/queue/cancel/' in response.text


def test_library_rows_partial_filters_by_query(db_session_visible) -> None:
    keep = Download(url="https://example.com/keep", title="Keep me", status="done", progress=100.0)
    skip = Download(url="https://example.com/skip", title="Skip me", status="done", progress=100.0)
    db_session_visible.add_all([keep, skip])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/library/rows", params={"q": "Keep"})

    assert response.status_code == 200
    assert "Keep me" in response.text
    assert "Skip me" not in response.text
    assert 'hx-delete="/library/delete/' in response.text


def test_partials_render_explicit_empty_states() -> None:
    with TestClient(app) as client:
        queue = client.get("/queue/rows")
        library = client.get("/library/rows")

    assert "No queued or active downloads." in queue.text
    assert "No completed downloads yet." in library.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_partials.py -v`
Expected: FAIL with `404 Not Found` for `/queue/rows` and `/library/rows`

- [ ] **Step 3: Write the minimal implementation**

```python
# app/routes/pages.py
@router.get("/queue/rows", response_class=HTMLResponse)
def queue_rows(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/queue_rows.html",
        {"request": request, "rows": get_active_jobs(session)},
    )


@router.get("/library/rows", response_class=HTMLResponse)
def library_rows(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        "partials/library_rows.html",
        {"request": request, "rows": rows, "query": q},
    )
```

```html
<!-- app/templates/partials/queue_rows.html -->
{% for row in rows %}
<tr data-job-id="{{ row.id }}">
  <td>{{ row.title or row.url }}</td>
  <td>{{ row.status }}</td>
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
{% else %}
<tr>
  <td colspan="4">No queued or active downloads.</td>
</tr>
{% endfor %}
```

```html
<!-- app/templates/partials/library_rows.html -->
{% for row in rows %}
<tr data-job-id="{{ row.id }}">
  <td>{{ row.title or row.url }}</td>
  <td>{{ row.uploader or "" }}</td>
  <td>
    <a href="/api/downloads/{{ row.id }}/file">Download file</a>
    <button
      type="button"
      hx-delete="/library/delete/{{ row.id }}"
      hx-target="#library-rows"
      hx-swap="innerHTML"
    >Delete</button>
  </td>
</tr>
{% else %}
<tr>
  <td colspan="3">No completed downloads yet.</td>
</tr>
{% endfor %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_partials.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py app/templates/partials/queue_rows.html app/templates/partials/library_rows.html tests/integration/test_partials.py
git commit -m "feat: add HTMX queue and library fragments"
```

### Task 3: Add HTMX-native page markup for lookup, library, and settings

**Files:**
- Modify: `app/templates/pages/home.html`
- Modify: `app/templates/pages/library.html`
- Modify: `app/templates/pages/settings.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Extend the failing page tests to cover UI hooks**

```python
def test_home_page_exposes_lookup_and_enqueue_hooks() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="info-form"' in response.text
    assert 'id="info-result"' in response.text
    assert 'hx-post="/info/form"' in response.text


def test_library_page_exposes_search_hooks() -> None:
    with TestClient(app) as client:
        response = client.get("/library")

    assert response.status_code == 200
    assert 'id="library-search-form"' in response.text
    assert 'hx-get="/library/rows"' in response.text
    assert 'id="library-rows"' in response.text


def test_settings_page_exposes_form_and_restart_notice() -> None:
    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'id="settings-form"' in response.text
    assert 'hx-put="/settings/form"' in response.text
    assert "takes effect after restart" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: FAIL because the HTMX attributes and targets are missing

- [ ] **Step 3: Write the minimal implementation**

```html
<!-- app/templates/pages/home.html -->
{% extends "index.html" %}
{% block title %}YourTube | Download{% endblock %}
{% block content %}
<section class="panel">
  <h1>Download a video</h1>
  <form
    id="info-form"
    class="stack"
    hx-post="/info/form"
    hx-target="#info-result"
    hx-swap="innerHTML"
  >
    <label for="video-url">Video URL</label>
    <input id="video-url" type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required />
    <label><input type="checkbox" name="proxy" /> Use saved proxy</label>
    <label><input type="checkbox" name="cookies" /> Use saved cookies</label>
    <button type="submit">Fetch formats</button>
  </form>
  <div id="info-status"></div>
  <div id="info-result"></div>
</section>
{% endblock %}
```

```html
<!-- app/templates/pages/library.html -->
{% extends "index.html" %}
{% block title %}YourTube | Library{% endblock %}
{% block content %}
<section>
  <h1>Library</h1>
  <form
    id="library-search-form"
    hx-get="/library/rows"
    hx-target="#library-rows"
    hx-swap="innerHTML"
  >
    <label for="library-query">Search</label>
    <input id="library-query" name="q" value="{{ query }}" placeholder="Title or uploader" />
    <button type="submit">Search</button>
  </form>
  <div id="library-status" role="status"></div>
  <table class="data-table">
    <thead>
      <tr><th>Title</th><th>Uploader</th><th>Actions</th></tr>
    </thead>
    <tbody id="library-rows" data-partial-url="/library/rows">
      {% include "partials/library_rows.html" %}
    </tbody>
  </table>
</section>
{% endblock %}
```

```html
<!-- app/templates/pages/settings.html -->
{% extends "index.html" %}
{% block title %}YourTube | Settings{% endblock %}
{% block content %}
<section class="panel">
  <h1>Settings</h1>
  <p>Changing max concurrent downloads takes effect after restart.</p>
  <form
    id="settings-form"
    class="stack"
    hx-put="/settings/form"
    hx-target="#settings-status"
    hx-swap="innerHTML"
  >
    <label for="max-concurrent">Max concurrent</label>
    <input id="max-concurrent" name="max_concurrent" value="{{ settings_values.max_concurrent }}" />
    <label for="proxy-url">Proxy URL</label>
    <input id="proxy-url" name="proxy_url" value="{{ settings_values.proxy_url }}" />
    <label for="cookies-path">Cookies path</label>
    <input id="cookies-path" name="cookies_path" value="{{ settings_values.cookies_path }}" />
    <label for="downloads-dir">Downloads directory</label>
    <input id="downloads-dir" name="downloads_dir" value="{{ settings_values.downloads_dir }}" />
    <div class="button-row">
      <button type="submit">Save</button>
      <button type="button" id="reset-settings" hx-post="/settings/reset" hx-target="#settings-form" hx-swap="outerHTML">Reset</button>
    </div>
  </form>
  <div id="settings-status"></div>
</section>
{% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/home.html app/templates/pages/library.html app/templates/pages/settings.html tests/integration/test_pages.py
git commit -m "feat: add HTMX-native page markup"
```

### Task 4: Add HTMX mutation endpoints, response fragments, and verify the UI slice

**Files:**
- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/home.html`
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/pages/library.html`
- Modify: `app/templates/pages/settings.html`
- Create: `app/templates/partials/info_result.html`
- Create: `app/templates/partials/status_message.html`
- Modify: `tests/integration/test_pages.py`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Extend the failing tests to check HTMX mutation responses**

```python
def test_info_lookup_fragment_renders_enqueue_form(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [{"format_id": "18", "ext": "mp4", "resolution": "360p"}],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert 'id="enqueue-form"' in response.text
    assert "Example title" in response.text


def test_settings_reset_returns_updated_form(db_session_visible) -> None:
    set_settings_batch(db_session_visible, {"max_concurrent": "4"})

    with TestClient(app) as client:
        response = client.post("/settings/reset")

    assert response.status_code == 200
    assert 'value="1"' in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`
Expected: FAIL because the browser-facing HTMX mutation routes do not exist yet

- [ ] **Step 3: Write the minimal implementation**

# app/routes/pages.py
from app.services.downloader import extract_info, normalize_formats
from app.services.library import delete_from_library
from app.services.queue import cancel_job, enqueue_download
from app.schemas import DownloadCreate


@router.post("/info/form", response_class=HTMLResponse)
def info_form(
    request: Request,
    url: str = Form(...),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runtime = resolve_runtime_settings(session)
    raw = extract_info(
        url,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
    return templates.TemplateResponse(
        request,
        "partials/info_result.html",
        {
            "url": url,
            "title": raw.get("title", ""),
            "uploader": raw.get("uploader"),
            "duration": raw.get("duration"),
            "thumbnail": raw.get("thumbnail"),
            "formats": normalize_formats(raw),
        },
    )


@router.post("/downloads/form", response_class=HTMLResponse)
def downloads_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    payload = DownloadCreate(
        url=request.form()["url"],
        title=request.form().get("title"),
        uploader=request.form().get("uploader"),
        duration=int(request.form()["duration"]) if request.form().get("duration") else None,
        thumbnail=request.form().get("thumbnail"),
        video_format_id=request.form().get("video_format_id") or None,
        audio_format_id=request.form().get("audio_format_id") or None,
        subtitles=request.form().get("subtitles") == "on",
    )
    enqueue_download(session, payload)
    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": "Added to queue.", "target_id": "info-status"},
    )


@router.post("/queue/cancel/{job_id}", response_class=HTMLResponse)
def queue_cancel(job_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    cancel_job(session, job_id)
    return templates.TemplateResponse(
        request,
        "partials/queue_rows.html",
        {"rows": get_active_jobs(session)},
    )


@router.delete("/library/delete/{job_id}", response_class=HTMLResponse)
def library_delete(job_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    delete_from_library(session, job_id)
    return templates.TemplateResponse(
        request,
        "partials/library_rows.html",
        {"rows": get_library(session), "query": ""},
    )


@router.put("/settings/form", response_class=HTMLResponse)
def settings_form_put(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    form = request.form()
    set_settings_batch(
        session,
        {
            "max_concurrent": str(form["max_concurrent"]),
            "proxy_url": str(form.get("proxy_url", "")),
            "cookies_path": str(form.get("cookies_path", "")),
            "downloads_dir": str(form.get("downloads_dir", "")),
        },
    )
    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": "Settings saved.", "target_id": "settings-status"},
    )


@router.post("/settings/reset", response_class=HTMLResponse)
def settings_reset_form(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    reset_settings(session)
    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {"settings_values": get_all_settings(session)},
    )
```

```html
<!-- app/templates/partials/info_result.html -->
<section class="panel">
  <h2>{{ title or url }}</h2>
  <form hx-post="/downloads/form" hx-target="#info-status" hx-swap="innerHTML">
    <input type="hidden" name="url" value="{{ url }}" />
    <input type="hidden" name="title" value="{{ title }}" />
    <input type="hidden" name="uploader" value="{{ uploader or '' }}" />
    <input type="hidden" name="duration" value="{{ duration or '' }}" />
    <input type="hidden" name="thumbnail" value="{{ thumbnail or '' }}" />
    <label for="video-format">Video format</label>
    <select id="video-format" name="video_format_id">
      <option value="">Default</option>
      {% for item in formats %}
      <option value="{{ item.format_id }}">{{ item.format_id }} {{ item.ext }} {{ item.resolution or '' }}</option>
      {% endfor %}
    </select>
    <label for="audio-format">Audio format</label>
    <select id="audio-format" name="audio_format_id">
      <option value="">Default</option>
      {% for item in formats %}
      <option value="{{ item.format_id }}">{{ item.format_id }} {{ item.ext }}</option>
      {% endfor %}
    </select>
    <label><input type="checkbox" name="subtitles" /> Download subtitles</label>
    <button type="submit">Add to queue</button>
  </form>
</section>
```

```html
<!-- app/templates/partials/status_message.html -->
<div id="{{ target_id }}">{{ message }}</div>
```

- [ ] **Step 4: Run the UI slice tests**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py tests/integration/test_api_library.py -v`
Expected: PASS

- [ ] **Step 5: Manual smoke test**

Run: `uv run uvicorn app.main:app --reload`
Expected:
- `/` loads with the HTMX lookup form
- looking up a video renders the enqueue fragment
- enqueueing updates the status region and queue rows
- `/queue` refreshes rows and allows cancel through HTMX
- `/library` searches and deletes rows through HTMX
- `/settings` saves and resets values through HTMX

- [ ] **Step 6: Commit**

```bash
git add app/routes/pages.py app/templates/pages/home.html app/templates/pages/queue.html app/templates/pages/library.html app/templates/pages/settings.html app/templates/partials/info_result.html app/templates/partials/status_message.html tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "feat: add HTMX mutation flows for the web ui"
```

## Self-Review

- Spec coverage:
  - page routing, shared `index.html`, and local HTMX asset -> Task 1
  - queue/library HTML partial routes -> Task 2
  - HTMX-native page markup -> Task 3
  - HTMX mutation flows, response fragments, and smoke verification -> Task 4
- Placeholder scan:
  - no `TBD`, `TODO`, or implied "fill this in later" steps remain
  - every mutating step has concrete code and exact commands
- Type consistency:
  - page routes read from `get_active_jobs()`, `get_library()`, `search_library()`, and `get_all_settings()`
  - browser-facing HTML routes in `pages.py` coexist with the Phase 3A JSON endpoints in `api.py`

## Execution Handoff

Plan complete and saved to `plans/2026-06-09-yourtube-design-phase-3b.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
