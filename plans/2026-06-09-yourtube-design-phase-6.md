# Phase 6 Editorial UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing browser UI into a near-copy editorial app experience inspired by `averygan-reclip/templates/index.html`, while keeping the current page routes and HTMX behavior intact.

**Architecture:** Keep the FastAPI + Jinja2 + HTMX structure exactly as it is and treat Phase 6 as a presentation refactor. Add the missing shared stylesheet, rebuild the shared shell and page templates around a single editorial system, and redesign partial HTML so queue, library, settings, and lookup results fit the new visual language without changing backend contracts.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, SQLAlchemy 2.x, pytest, uv, Google Fonts

---

## File Structure

```
yourtube/
├── app/
│   ├── templates/
│   │   ├── index.html
│   │   ├── pages/
│   │   │   ├── home.html
│   │   │   ├── queue.html
│   │   │   ├── library.html
│   │   │   └── settings.html
│   │   └── partials/
│   │       ├── info_result.html
│   │       ├── queue_rows.html
│   │       ├── library_rows.html
│   │       ├── runtime_status.html
│   │       ├── settings_form.html
│   │       └── status_message.html
│   └── static/
│       ├── assets/
│       │   └── favicon.svg              # new
│       ├── css/
│       │   └── app.css                  # new
│       └── vendor/
│           └── htmx.min.js
├── tests/
│   └── integration/
│       ├── test_pages.py
│       └── test_partials.py
└── plans/
    ├── 2026-06-09-yourtube-design.md
    └── 2026-06-09-yourtube-design-phase-6.md
```

Responsibilities:

- `app/static/assets/favicon.svg` is the favicon for the app, which is a circle with a play button in the center.
- `app/static/css/app.css` owns the shared editorial design system: fonts, color tokens, texture, layout grid, cards, ledger rows, forms, buttons, and responsive behavior.
- `app/templates/index.html` owns the shared shell, font loading, navigation, flash region, and top-level page frame.
- `app/templates/pages/home.html` owns the landing-first homepage with a hero, downloader composer, and supporting operational modules.
- `app/templates/pages/queue.html` and `app/templates/partials/queue_rows.html` own the mixed desktop-ledger/mobile-card presentation for active work.
- `app/templates/pages/library.html` and `app/templates/partials/library_rows.html` own the archive presentation and search results.
- `app/templates/pages/settings.html`, `app/templates/partials/runtime_status.html`, and `app/templates/partials/settings_form.html` own the notebook-style control page and diagnostics presentation.
- `tests/integration/test_pages.py` covers full-page structure and route-level hooks.
- `tests/integration/test_partials.py` covers fragment-only markup and empty/result states.
- `plans/2026-06-09-yourtube-design.md` stays aligned with the new Phase 6 scope.

## Design Inputs And Constraints

- Primary visual source: `/Users/lanh/Developer/video-downloaders/averygan-reclip/templates/index.html`
- Chosen type system: `Playfair Display` for headlines and `Work Sans` for body/UI text
- Keep these routes unchanged:
  - `/`
  - `/queue`
  - `/library`
  - `/settings`
- Keep these fragment contracts unchanged:
  - `POST /info/form`
  - `POST /downloads/form`
  - `GET /queue/rows`
  - `GET /library/rows`
  - `POST /queue/cancel/{job_id}`
  - `DELETE /library/delete/{job_id}`
  - `PUT /settings/form`
  - `POST /settings/reset`
- Preserve these browser-facing target IDs where possible:
  - `#info-form`
  - `#info-result`
  - `#info-status`
  - `#queue-rows`
  - `#library-rows`
  - `#settings-form`
  - `#settings-status`

### Task 1: Install The Shared Editorial Shell

**Files:**

- Create: `app/static/css/app.css`
- Modify: `app/templates/index.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing shell and asset tests**

```python
def test_pages_extend_editorial_shell_and_load_local_assets() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        htmx = client.get("/static/vendor/htmx.min.js")
        css = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "/static/css/app.css" in response.text
    assert "Playfair Display" in response.text
    assert "Work Sans" in response.text
    assert 'class="site-header"' in response.text
    assert 'class="site-nav"' in response.text
    assert css.status_code == 200
    assert "--bg:" in css.text
    assert htmx.status_code == 200
```

- [ ] **Step 2: Run the shell test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_pages_extend_editorial_shell_and_load_local_assets -v`

Expected: FAIL because `app/static/css/app.css` does not exist yet and the current base template does not load the new fonts or shell classes.

- [ ] **Step 3: Add the shared stylesheet and rebuild the base layout**

```html
<!-- app/templates/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}YourTube{% endblock %}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Work+Sans:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
    <link rel="stylesheet" href="{{ url_for('static', path='css/app.css') }}" />
    <script
      defer
      src="{{ url_for('static', path='vendor/htmx.min.js') }}"
    ></script>
  </head>
  <body>
    <div class="page-noise"></div>
    <header class="site-header">
      <div class="site-header-inner">
        <a class="site-brand" href="/">YourTube</a>
        <nav class="site-nav">
          <a href="/">Home</a>
          <a href="/queue">Queue</a>
          <a href="/library">Library</a>
          <a href="/settings">Settings</a>
        </nav>
      </div>
    </header>
    <main class="page-shell">{% block content %}{% endblock %}</main>
    <section id="flash-region"></section>
  </body>
</html>
```

```css
/* app/static/css/app.css */
:root {
  --bg: #f4f1eb;
  --fg: #33312d;
  --muted: #8e897c;
  --line: #ddd7ce;
  --card: #fffdf9;
  --accent: #e25a2c;
  --accent-hover: #c9491f;
  --success: #2f7d4d;
  --warning: #a86920;
  --error: #b43a32;
  --radius-lg: 18px;
  --radius-md: 12px;
  --shadow-soft: 0 14px 40px rgba(51, 49, 45, 0.06);
}

body {
  margin: 0;
  font-family: "Work Sans", sans-serif;
  background: var(--bg);
  color: var(--fg);
}

.site-brand,
h1,
h2,
h3 {
  font-family: "Playfair Display", serif;
}

.page-shell {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 20px 80px;
}
```

- [ ] **Step 4: Run the shell test to verify it passes**

Run: `uv run pytest tests/integration/test_pages.py::test_pages_extend_editorial_shell_and_load_local_assets -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/css/app.css app/templates/index.html tests/integration/test_pages.py
git commit -m "feat: add editorial shell for phase 6"
```

### Task 2: Rebuild The Homepage As A Landing-First Downloader

**Files:**

- Modify: `app/templates/pages/home.html`
- Modify: `app/templates/partials/info_result.html`
- Modify: `app/templates/partials/status_message.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing homepage and lookup tests**

```python
def test_home_page_renders_landing_first_editorial_sections() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Download with editorial calm." in response.text
    assert 'id="info-form"' in response.text
    assert 'id="info-result"' in response.text
    assert "Recent workflow" in response.text


def test_info_lookup_fragment_renders_editorial_media_card(monkeypatch) -> None:
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
    assert 'class="media-card"' in response.text
    assert "Example title" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert 'name="subtitles"' in response.text
```

- [ ] **Step 2: Run the homepage tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py::test_home_page_renders_landing_first_editorial_sections tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v`

Expected: FAIL because the home page still renders the old single-panel layout and the lookup fragment has no editorial card classes or supporting sections.

- [ ] **Step 3: Replace the home page and lookup fragment markup**

```html
<!-- app/templates/pages/home.html -->
{% extends "index.html" %} {% block title %}YourTube | Home{% endblock %} {%
block content %}
<section class="hero-panel">
  <p class="eyebrow">Your personal media desk</p>
  <h1>Download with editorial calm.</h1>
  <p class="hero-copy">
    Look up a video, inspect formats, and send it to the queue without leaving
    the main page.
  </p>
</section>

<section class="composer-panel">
  <div class="panel-heading">
    <h2>Fetch a source</h2>
    <p>Paste a YouTube URL, then choose the exact formats you want.</p>
  </div>
  <form
    id="info-form"
    class="lookup-form"
    hx-post="/info/form"
    hx-target="#info-result"
    hx-swap="innerHTML"
  >
    <label for="video-url">Video URL</label>
    <input
      id="video-url"
      type="url"
      name="url"
      placeholder="https://www.youtube.com/watch?v=..."
      required
    />
    <div class="toggle-row">
      <label><input type="checkbox" name="proxy" /> Use saved proxy</label>
      <label><input type="checkbox" name="cookies" /> Use saved cookies</label>
    </div>
    <button type="submit">Fetch formats</button>
  </form>
  <div id="info-status"></div>
  <div id="info-result" class="lookup-result-slot"></div>
</section>

<section class="support-grid">
  <article class="support-card">
    <h2>Recent workflow</h2>
    <p>
      Queue, library, and runtime diagnostics stay one click away from the main
      composer.
    </p>
  </article>
</section>
{% endblock %}
```

```html
<!-- app/templates/partials/info_result.html -->
<section class="media-card">
  {% if thumbnail %}
  <img src="{{ thumbnail }}" alt="" class="media-card-thumb" />
  {% endif %}
  <div class="media-card-body">
    <p class="eyebrow">Detected media</p>
    <h2>{{ title or url }}</h2>
    <dl class="meta-grid">
      <div>
        <dt>Uploader</dt>
        <dd>{{ uploader or "Unknown" }}</dd>
      </div>
      <div>
        <dt>Duration</dt>
        <dd>{{ duration or "Unknown" }}</dd>
      </div>
    </dl>
    <form
      id="enqueue-form"
      hx-post="/downloads/form"
      hx-target="#info-status"
      hx-swap="innerHTML"
    >
      <input type="hidden" name="url" value="{{ url }}" />
      <input type="hidden" name="title" value="{{ title }}" />
      <input type="hidden" name="uploader" value="{{ uploader or '' }}" />
      <input type="hidden" name="duration" value="{{ duration or '' }}" />
      <input type="hidden" name="thumbnail" value="{{ thumbnail or '' }}" />
      <label for="video-format">Video format</label>
      <select id="video-format" name="video_format_id">
        <option value="">Default</option>
        {% for item in formats %}
        <option value="{{ item.format_id }}">
          {{ item.format_id }} {{ item.ext }} {{ item.resolution or '' }}
        </option>
        {% endfor %}
      </select>
      <label for="audio-format">Audio format</label>
      <select id="audio-format" name="audio_format_id">
        <option value="">Default</option>
        {% for item in formats %}
        <option value="{{ item.format_id }}">
          {{ item.format_id }} {{ item.ext }}
        </option>
        {% endfor %}
      </select>
      <label
        ><input type="checkbox" name="subtitles" /> Download subtitles</label
      >
      <button type="submit">Add to queue</button>
    </form>
  </div>
</section>
```

- [ ] **Step 4: Run the homepage tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py::test_home_page_renders_landing_first_editorial_sections tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/home.html app/templates/partials/info_result.html app/templates/partials/status_message.html tests/integration/test_pages.py
git commit -m "feat: redesign homepage and lookup result for phase 6"
```

### Task 3: Convert Queue And Library Into Editorial Operational Pages

**Files:**

- Modify: `app/templates/pages/queue.html`
- Modify: `app/templates/pages/library.html`
- Modify: `app/templates/partials/queue_rows.html`
- Modify: `app/templates/partials/library_rows.html`
- Test: `tests/integration/test_pages.py`
- Test: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing queue and library tests**

```python
def test_queue_page_renders_ledger_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/queue")

    assert response.status_code == 200
    assert "Queue ledger" in response.text
    assert 'id="queue-rows"' in response.text
    assert "Queued and active downloads update automatically." in response.text


def test_library_page_renders_archive_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/library")

    assert response.status_code == 200
    assert "Archive library" in response.text
    assert 'id="library-search-form"' in response.text
    assert 'id="library-rows"' in response.text


def test_queue_rows_partial_renders_editorial_entries(db_session_visible) -> None:
    first = Download(url="https://example.com/a", title="First", status="queued", progress=0.0)
    second = Download(url="https://example.com/b", title="Second", status="active", progress=42.5)
    db_session_visible.add_all([first, second])
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/queue/rows")

    assert response.status_code == 200
    assert "<tbody" not in response.text
    assert 'class="queue-entry"' in response.text
    assert 'hx-post="/queue/cancel/' in response.text


def test_library_rows_partial_renders_archive_entries(db_session_visible) -> None:
    row = Download(
        url="https://example.com/done",
        title="Saved clip",
        uploader="Uploader",
        status="done",
        progress=100.0,
    )
    db_session_visible.add(row)
    db_session_visible.commit()

    with TestClient(app) as client:
        response = client.get("/library/rows")

    assert response.status_code == 200
    assert 'class="library-entry"' in response.text
    assert "Saved clip" in response.text
    assert 'hx-delete="/library/delete/' in response.text
```

- [ ] **Step 2: Run the queue and library tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_renders_ledger_shell tests/integration/test_pages.py::test_library_page_renders_archive_shell tests/integration/test_partials.py::test_queue_rows_partial_renders_editorial_entries tests/integration/test_partials.py::test_library_rows_partial_renders_archive_entries -v`

Expected: FAIL because queue and library still render table-first markup and row fragments still use `<tr>` output only.

- [ ] **Step 3: Replace queue and library markup with ledger/archive layouts**

```html
<!-- app/templates/pages/queue.html -->
{% extends "index.html" %} {% block title %}YourTube | Queue{% endblock %} {%
block content %}
<section class="page-panel">
  <div class="panel-heading">
    <p class="eyebrow">Operations</p>
    <h1>Queue ledger</h1>
    <p>Queued and active downloads update automatically.</p>
  </div>
  <div id="queue-status"></div>
  <div class="queue-ledger">
    <div class="ledger-head">
      <span>Title</span><span>Status</span><span>Progress</span
      ><span>Action</span>
    </div>
    <div
      id="queue-rows"
      hx-get="/queue/rows"
      hx-trigger="load, every 2s"
      hx-swap="innerHTML"
    >
      {% include "partials/queue_rows.html" %}
    </div>
  </div>
</section>
{% endblock %}
```

```html
<!-- app/templates/partials/queue_rows.html -->
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

```html
<!-- app/templates/pages/library.html -->
{% extends "index.html" %} {% block title %}YourTube | Library{% endblock %} {%
block content %}
<section class="page-panel">
  <div class="panel-heading">
    <p class="eyebrow">Archive</p>
    <h1>Archive library</h1>
    <p>Search completed downloads by title or uploader.</p>
  </div>
  <form
    id="library-search-form"
    class="library-search"
    hx-get="/library/rows"
    hx-target="#library-rows"
    hx-swap="innerHTML"
  >
    <label for="library-query">Search</label>
    <input
      id="library-query"
      name="q"
      value="{{ query }}"
      placeholder="Title or uploader"
    />
    <button type="submit">Search</button>
  </form>
  <div id="library-status" role="status"></div>
  <div id="library-rows" class="library-list" data-partial-url="/library/rows">
    {% include "partials/library_rows.html" %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 4: Run the queue and library tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py::test_queue_page_renders_ledger_shell tests/integration/test_pages.py::test_library_page_renders_archive_shell tests/integration/test_partials.py::test_queue_rows_partial_renders_editorial_entries tests/integration/test_partials.py::test_library_rows_partial_renders_archive_entries -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/queue.html app/templates/pages/library.html app/templates/partials/queue_rows.html app/templates/partials/library_rows.html tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "feat: redesign queue and library for phase 6"
```

### Task 4: Restyle Settings, Diagnostics, And Message States

**Files:**

- Modify: `app/templates/pages/settings.html`
- Modify: `app/templates/partials/runtime_status.html`
- Modify: `app/templates/partials/settings_form.html`
- Modify: `app/templates/partials/status_message.html`
- Test: `tests/integration/test_pages.py`
- Test: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing settings and status tests**

```python
def test_settings_page_renders_editorial_control_room() -> None:
    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert "Control settings" in response.text
    assert 'id="settings-form"' in response.text
    assert 'id="settings-status"' in response.text
    assert "takes effect after restart" in response.text


def test_settings_page_renders_runtime_status(monkeypatch) -> None:
    class _FakeStatus:
        def __init__(self) -> None:
            self.level = "warning"
            self.messages = ["Node.js runtime missing."]
            self.js_runtime_ready = False
            self.workers_enabled = True

    monkeypatch.setattr(
        "app.routes.pages.collect_runtime_diagnostics", lambda *, workers_enabled: _FakeStatus()
    )

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert 'class="status-card status-card-warning"' in response.text
    assert "Node.js runtime missing." in response.text
```

- [ ] **Step 2: Run the settings tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py::test_settings_page_renders_editorial_control_room tests/integration/test_pages.py::test_settings_page_renders_runtime_status -v`

Expected: FAIL because the settings page still uses the old panel markup and the diagnostics partial still renders the older `status-panel` structure.

- [ ] **Step 3: Replace settings, diagnostics, and flash markup**

```html
<!-- app/templates/pages/settings.html -->
{% extends "index.html" %} {% block title %}YourTube | Settings{% endblock %} {%
block content %}
<section class="page-panel">
  <div class="panel-heading">
    <p class="eyebrow">Control room</p>
    <h1>Control settings</h1>
    <p>Changing max concurrent downloads takes effect after restart.</p>
  </div>
  {% include "partials/runtime_status.html" %} {% include
  "partials/settings_form.html" %}
  <div id="settings-status"></div>
</section>
{% endblock %}
```

```html
<!-- app/templates/partials/runtime_status.html -->
{% if runtime_status.messages %}
<section class="status-card status-card-{{ runtime_status.level }}">
  <p class="eyebrow">Runtime status</p>
  <ul class="status-list">
    {% for message in runtime_status.messages %}
    <li>{{ message }}</li>
    {% endfor %}
  </ul>
</section>
{% endif %}
```

```html
<!-- app/templates/partials/status_message.html -->
<div id="{{ target_id }}" class="flash-card flash-card-success">
  {{ message }}
</div>
```

- [ ] **Step 4: Run the settings tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py::test_settings_page_renders_editorial_control_room tests/integration/test_pages.py::test_settings_page_renders_runtime_status -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/settings.html app/templates/partials/runtime_status.html app/templates/partials/settings_form.html app/templates/partials/status_message.html tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "feat: redesign settings and status surfaces for phase 6"
```

### Task 5: Verify Responsive Markup And Full Browser Test Coverage

**Files:**

- Modify: `tests/integration/test_pages.py`
- Modify: `tests/integration/test_partials.py`

- [ ] **Step 1: Add the final regression and empty-state tests**

```python
def test_partials_render_explicit_empty_states() -> None:
    with TestClient(app) as client:
        queue = client.get("/queue/rows")
        library = client.get("/library/rows")

    assert "No queued or active downloads." in queue.text
    assert 'class="empty-state"' in queue.text
    assert "No completed downloads yet." in library.text
    assert 'class="empty-state"' in library.text


def test_settings_reset_returns_updated_form(db_session_visible) -> None:
    set_settings_batch(db_session_visible, {"max_concurrent": "4"})

    with TestClient(app) as client:
        response = client.post("/settings/reset")

    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'id="settings-form"' in response.text
    assert 'value="1"' in response.text
```

- [ ] **Step 2: Run the focused page and partial suites**

Run: `uv run pytest tests/integration/test_pages.py tests/integration/test_partials.py -v`

Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -q`

Expected: PASS with no regressions outside the UI refactor.

- [ ] **Step 4: Manual browser smoke check**

Run: `uv run uvicorn app.main:app --reload`

Verify:

- `/` hero, composer, and info-result card render correctly on desktop and narrow mobile width
- `/queue` polling refreshes ledger entries and cancel still works
- `/library` search and delete still work inside the new archive layout
- `/settings` save/reset/runtime status all render correctly

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "test: finish phase 6 UI regression coverage"
```

## Self-Review

- Spec coverage:
  - shared editorial shell -> Task 1
  - landing-first homepage -> Task 2
  - queue/library operational redesign -> Task 3
  - settings/runtime/status redesign -> Task 4
  - final regression coverage and smoke verification -> Task 5
- Placeholder scan:
  - no `TODO`
  - no route additions
  - no backend contract changes
- Type consistency:
  - page routes remain in `app.routes.pages`
  - existing HTMX endpoint paths stay unchanged
  - tests continue using `TestClient(app)` and existing `Download` / `set_settings_batch` helpers

## Execution Handoff

Plan complete and saved to `plans/2026-06-09-yourtube-design-phase-6.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
