# Phase 3: Web App + Worker Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full FastAPI web app, HTML UI, API routes, and in-process worker pool on top of the Phase 2 services.

**Architecture:** FastAPI serves Jinja templates and JSON/HTML partial APIs. Lifespan applies Alembic migrations, requeues stranded work, loads runtime settings, and starts worker threads. Routes depend on SQLAlchemy sessions and translate between ORM models and Pydantic schemas.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2, htmx, yt-dlp, pytest

---

## File Structure (this phase adds)

```
yourtube/
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── pages.py
│   │   └── api.py
│   ├── static/
│   │   └── css/app.css
│   └── templates/
│       ├── base.html
│       ├── components/
│       ├── pages/
│       └── partials/
└── tests/
    └── integration/
        ├── test_pages.py
        ├── test_api_info.py
        ├── test_api_downloads_create.py
        ├── test_api_downloads_active.py
        ├── test_api_downloads_library.py
        ├── test_api_downloads_cancel.py
        ├── test_api_downloads_delete.py
        ├── test_api_downloads_file.py
        ├── test_api_settings_get.py
        ├── test_api_settings_put.py
        ├── test_api_settings_reset.py
        └── test_startup_recovery.py
```

### Task 1: Full app bootstrap and worker pool

**Files:**
- Modify: `app/main.py`
- Create: `tests/integration/test_startup_recovery.py`

- [ ] **Step 1: Write failing startup recovery test**

Cover:

- migrations run on app startup
- `active` rows are requeued to `queued`
- worker pool reads `max_concurrent`

- [ ] **Step 2: Implement worker pool in `app/main.py`**

Add:

```python
class WorkerPool:
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

Lifespan order:

1. `alembic upgrade head`
2. `requeue_active_on_startup(session)`
3. load concurrency from settings
4. start worker threads

- [ ] **Step 3: Run test**

Run: `uv run pytest tests/integration/test_startup_recovery.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/integration/test_startup_recovery.py
git commit -m "feat: add worker pool bootstrap and startup recovery"
```

### Task 2: Page routes, templates, and styles

**Files:**
- Create: `app/routes/pages.py`
- Create: `app/static/css/app.css`
- Create: `app/templates/base.html`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/queue.html`
- Create: `app/templates/pages/library.html`
- Create: `app/templates/pages/settings.html`
- Create: `app/templates/partials/queue_rows.html`
- Create: `app/templates/partials/library_rows.html`
- Create: `tests/integration/test_pages.py`

- [ ] **Step 1: Write failing page tests**

Cover:

- `/`
- `/queue`
- `/library`
- `/settings`
- `/health`

- [ ] **Step 2: Implement page routes**

`app/routes/pages.py` should render the page templates and keep `/health` JSON-based.

- [ ] **Step 3: Implement base layout and pages**

Include:

- sidebar navigation
- URL input and format picker shell on home page
- queue polling container
- library list and search UI
- settings form shell

- [ ] **Step 4: Implement stylesheet**

Keep styling intentional but lightweight. Preserve existing visual direction from the earlier plan where practical.

- [ ] **Step 5: Run page tests**

Run: `uv run pytest tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/pages.py app/static/css/app.css app/templates tests/integration/test_pages.py
git commit -m "feat: add page routes templates and styles"
```

### Task 3: API routes

**Files:**
- Create: `app/routes/api.py`
- Create: `tests/integration/test_api_info.py`
- Create: `tests/integration/test_api_downloads_create.py`
- Create: `tests/integration/test_api_downloads_active.py`
- Create: `tests/integration/test_api_downloads_library.py`
- Create: `tests/integration/test_api_downloads_cancel.py`
- Create: `tests/integration/test_api_downloads_delete.py`
- Create: `tests/integration/test_api_downloads_file.py`
- Create: `tests/integration/test_api_settings_get.py`
- Create: `tests/integration/test_api_settings_put.py`
- Create: `tests/integration/test_api_settings_reset.py`

- [ ] **Step 1: Write failing API tests**

Cover:

- `/api/info`
- create download
- active queue list
- library list/search
- cancel
- delete
- file serving
- get/update/reset settings

- [ ] **Step 2: Implement `app/routes/api.py`**

Use service layer functions from Phase 2. Route rules:

- `POST /api/info` returns normalized format metadata
- `POST /api/downloads` inserts queued work
- `GET /api/downloads/active` returns queued and active jobs
- `GET /api/downloads/library` returns completed jobs
- `POST /api/downloads/{id}/cancel` initiates cancellation
- `DELETE /api/downloads/{id}` deletes completed library items
- `GET /api/downloads/{id}/file` serves the completed file
- settings routes persist through `settings.py`

- [ ] **Step 3: Wire partial rendering for queue and library**

Support htmx polling responses for the queue and library views.

- [ ] **Step 4: Run API tests**

Run: `uv run pytest tests/integration/test_api_*.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/api.py tests/integration/test_api_info.py tests/integration/test_api_downloads_create.py tests/integration/test_api_downloads_active.py tests/integration/test_api_downloads_library.py tests/integration/test_api_downloads_cancel.py tests/integration/test_api_downloads_delete.py tests/integration/test_api_downloads_file.py tests/integration/test_api_settings_get.py tests/integration/test_api_settings_put.py tests/integration/test_api_settings_reset.py
git commit -m "feat: add web api routes for downloads and settings"
```

## Self-Review (Phase 3)

- Web app is now the main product path.
- Lifespan and worker startup order is explicit.
- API contracts rely on Pydantic schemas, not ORM instances directly.

## End of Phase 3

Deliverable: `uv run uvicorn app.main:app` serves the complete web app with queue, library, settings, and worker integration.
