# Phase 3B: Server-Rendered UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the server-rendered web UI, HTML partials, and browser interactions on top of the completed Phase 3A backend.

**Architecture:** Page routes render Jinja templates and thin partial endpoints return HTML fragments for queue and library refreshes. A small static JavaScript module owns JSON form submissions and progressive enhancement, while Phase 3A APIs remain the source of truth for all mutations.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, htmx, vanilla JavaScript, CSS, pytest

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
│   │   └── js/app.js
│   └── templates/
│       ├── base.html
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

- `app/routes/pages.py` owns page and partial rendering.
- `app/static/js/app.js` owns info lookup, enqueue, settings save/reset, and delete/cancel button wiring.
- `app/templates/partials/*.html` own table-row fragments used by HTMX refreshes.

### Task 1: Add page routes and base layout

**Files:**
- Create: `app/routes/pages.py`
- Modify: `app/main.py`
- Create: `app/templates/base.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing page tests**

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    ("path", "expected_text"),
    [
        ("/", "Download a video"),
        ("/queue", "Active Queue"),
        ("/library", "Library"),
        ("/settings", "Settings"),
    ],
)
def test_page_routes_render_html(path: str, expected_text: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert expected_text in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: FAIL with `404 Not Found` for page routes

- [ ] **Step 3: Write minimal implementation**

```python
# app/routes/pages.py
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/home.html", {"request": request})


@router.get("/queue", response_class=HTMLResponse)
def queue_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/queue.html", {"request": request})


@router.get("/library", response_class=HTMLResponse)
def library_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/library.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/settings.html", {"request": request})
```

```html
<!-- app/templates/base.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}YourTube{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='css/app.css') }}" />
    <script defer src="{{ url_for('static', path='js/app.js') }}"></script>
  </head>
  <body>
    <nav>
      <a href="/">Home</a>
      <a href="/queue">Queue</a>
      <a href="/library">Library</a>
      <a href="/settings">Settings</a>
    </nav>
    <main>{% block content %}{% endblock %}</main>
  </body>
</html>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py app/main.py app/templates/base.html app/templates/pages/home.html app/templates/pages/queue.html app/templates/pages/library.html app/templates/pages/settings.html tests/integration/test_pages.py
git commit -m "feat: add page routes and base layout"
```

### Task 2: Add queue and library partial routes

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


def test_queue_rows_partial_renders_html() -> None:
    with TestClient(app) as client:
        response = client.get("/queue/rows")
    assert response.status_code == 200
    assert "<tr" in response.text


def test_library_rows_partial_accepts_search_query() -> None:
    with TestClient(app) as client:
        response = client.get("/library/rows", params={"q": "test"})
    assert response.status_code == 200
    assert "<tbody" not in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_partials.py -v`
Expected: FAIL with `404 Not Found` for partial routes

- [ ] **Step 3: Write minimal implementation**

```python
# app/routes/pages.py
@router.get("/queue/rows", response_class=HTMLResponse)
def queue_rows(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    rows = get_active_jobs(session)
    return templates.TemplateResponse(
        "partials/queue_rows.html",
        {"request": request, "rows": rows},
    )


@router.get("/library/rows", response_class=HTMLResponse)
def library_rows(
    request: Request,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    rows = search_library(session, q) if q else get_library(session)
    return templates.TemplateResponse(
        "partials/library_rows.html",
        {"request": request, "rows": rows},
    )
```

```html
<!-- app/templates/partials/queue_rows.html -->
{% for row in rows %}
<tr>
  <td>{{ row.title or row.url }}</td>
  <td>{{ row.status }}</td>
  <td>{{ "%.1f"|format(row.progress) }}%</td>
</tr>
{% else %}
<tr><td colspan="3">No queued or active downloads.</td></tr>
{% endfor %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_partials.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py app/templates/partials/queue_rows.html app/templates/partials/library_rows.html tests/integration/test_partials.py
git commit -m "feat: add queue and library html partials"
```

### Task 3: Add browser behavior and styling

**Files:**
- Create: `app/static/css/app.css`
- Create: `app/static/js/app.js`
- Modify: `app/templates/pages/home.html`
- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/pages/library.html`
- Modify: `app/templates/pages/settings.html`

- [ ] **Step 1: Add the home page form shell**

```html
{% extends "base.html" %}
{% block title %}YourTube | Download{% endblock %}
{% block content %}
<section>
  <h1>Download a video</h1>
  <form id="info-form">
    <input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required />
    <label><input type="checkbox" name="proxy" /> Use saved proxy</label>
    <label><input type="checkbox" name="cookies" /> Use saved cookies</label>
    <button type="submit">Fetch formats</button>
  </form>
  <div id="info-result"></div>
  <div id="enqueue-result"></div>
</section>
{% endblock %}
```

- [ ] **Step 2: Add the queue, library, and settings page shells**

```html
<!-- app/templates/pages/queue.html -->
{% extends "base.html" %}
{% block content %}
<section>
  <h1>Active Queue</h1>
  <table hx-get="/queue/rows" hx-trigger="load, every 2s" hx-target="#queue-rows">
    <tbody id="queue-rows"></tbody>
  </table>
</section>
{% endblock %}
```

```html
<!-- app/templates/pages/settings.html -->
{% extends "base.html" %}
{% block content %}
<section>
  <h1>Settings</h1>
  <form id="settings-form">
    <input name="max_concurrent" />
    <input name="proxy_url" />
    <input name="cookies_path" />
    <input name="downloads_dir" />
    <button type="submit">Save</button>
    <button type="button" id="reset-settings">Reset</button>
  </form>
  <p id="settings-status"></p>
</section>
{% endblock %}
```

- [ ] **Step 3: Add minimal JavaScript for JSON API calls**

```javascript
const infoForm = document.querySelector("#info-form");
const settingsForm = document.querySelector("#settings-form");

if (infoForm) {
  infoForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(infoForm);
    const response = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: form.get("url"),
        proxy: form.get("proxy") === "on",
        cookies: form.get("cookies") === "on"
      })
    });
    const data = await response.json();
    document.querySelector("#info-result").textContent = data.title ?? data.detail?.message ?? "No result";
  });
}

if (settingsForm) {
  settingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(settingsForm).entries());
    const response = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    document.querySelector("#settings-status").textContent = response.ok ? "Saved" : "Save failed";
  });
}
```

- [ ] **Step 4: Add minimal stylesheet**

```css
:root {
  --bg: #f5efe4;
  --panel: #fffaf2;
  --ink: #1d1a16;
  --accent: #a64b2a;
  --muted: #6b6257;
}

body {
  margin: 0;
  font-family: "Iowan Old Style", "Palatino Linotype", serif;
  color: var(--ink);
  background: radial-gradient(circle at top, #fff6df, var(--bg));
}

main {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem;
}
```

- [ ] **Step 5: Verify the UI routes still render**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/static/css/app.css app/static/js/app.js app/templates/pages/home.html app/templates/pages/queue.html app/templates/pages/library.html app/templates/pages/settings.html
git commit -m "feat: add browser interactions and styling for web ui"
```

## Self-Review (Phase 3B)

- UI work depends only on the stable JSON contracts from Phase 3A.
- Partial HTML routes are explicit instead of mixing JSON and HTML in the same handlers.
- Browser behavior stays small and local; no client framework is introduced.

## End of Phase 3B

Deliverable: `uv run uvicorn app.main:app` serves the full web UI with queue polling, library search, settings forms, and JSON-backed interactions.
