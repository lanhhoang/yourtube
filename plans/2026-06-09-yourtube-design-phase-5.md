# Phase 5: Stabilization + Runtime Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the detached-session worker crash, make YouTube extraction fully supported in the shipped runtime by bundling Node.js, and expose lightweight runtime/worker diagnostics that Phase 6 can surface in the redesigned UI.

**Architecture:** Keep the existing FastAPI + SQLAlchemy + HTMX architecture intact. Fix the worker bug by tightening the queue claim contract rather than changing global SQLAlchemy expiration semantics, centralize yt-dlp JS-runtime configuration in the downloader layer, and add a small diagnostics service that page routes can render into existing pages.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2, HTMX, yt-dlp, Docker, pytest

---

## File Structure

```
yourtube/
├── Dockerfile
├── README.md
├── app/
│   ├── main.py
│   ├── routes/
│   │   ├── api.py
│   │   └── pages.py
│   ├── services/
│   │   ├── downloader.py
│   │   ├── queue.py
│   │   └── diagnostics.py          # new
│   └── templates/
│       └── partials/
│           └── runtime_status.html # new
└── tests/
    ├── unit/
    │   ├── test_diagnostics.py     # new
    │   └── test_queue_claim.py
    └── integration/
        ├── test_worker_pool.py
        ├── test_pages.py
        └── test_api_info.py
```

Responsibilities:

- `app/services/queue.py` owns the detached-safe queue claim contract used by worker threads.
- `app/main.py` consumes the new claim result without reading ORM instances after the session closes.
- `app/services/downloader.py` owns yt-dlp runtime configuration and JS-runtime diagnostics.
- `app/services/diagnostics.py` reports worker/runtime readiness in a renderable form.
- `app/routes/pages.py` and `app/templates/partials/runtime_status.html` surface diagnostics in a lightweight UI.
- `Dockerfile` guarantees Node.js is present in the shipped runtime.

## Runtime Contract For Phase 5

- Do not solve the worker crash by setting `expire_on_commit=False` globally.
- Do not return a session-bound ORM `Download` instance from the queue claim boundary when the worker loop will use it outside the claiming session.
- The shipped Docker runtime must include `Node.js` and must run yt-dlp with an explicit JS runtime configuration.
- Diagnostics remain lightweight:
  - no separate admin area
  - no new write APIs
  - only read-only status rendering/data needed by existing pages
- Phase 5 may add one small read-only diagnostics surface if the page layer needs it, but should not disturb the Phase 3A JSON contracts beyond that.

### Task 1: Make queue claims detached-safe

**Files:**
- Modify: `app/services/queue.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_queue_claim.py`
- Test: `tests/integration/test_worker_pool.py`

- [ ] **Step 1: Write the failing detached-safe claim test**

```python
from __future__ import annotations

from app.schemas import DownloadCreate
from app.services.queue import claim_next, enqueue_download


def test_claim_next_returns_detached_safe_payload(db_session) -> None:
    created = enqueue_download(db_session, DownloadCreate(url="https://example.com/watch?v=1"))

    claimed = claim_next(db_session)

    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status == "active"
    assert claimed.url == "https://example.com/watch?v=1"
```

- [ ] **Step 2: Write the failing worker regression test**

```python
from __future__ import annotations

from app.schemas import DownloadCreate
from app.services.queue import enqueue_download


def test_worker_loop_can_run_claimed_job_without_detached_instance(
    monkeypatch, db_session_visible, tmp_path
) -> None:
    row = enqueue_download(db_session_visible, DownloadCreate(url="https://example.com/safe"))
    db_session_visible.commit()

    def fake_run_download(**kwargs):
        return str(tmp_path / "safe.mp4")

    monkeypatch.setattr("app.main.run_download", fake_run_download)

    from app.main import WorkerPool

    pool = WorkerPool()
    claimed = pool._claim_once_for_test()
    assert claimed is not None
    pool._run_job(claimed.id)

    db_session_visible.refresh(row)
    assert row.status == "done"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py -v`
Expected: FAIL because `claim_next()` still returns an ORM row and `WorkerPool` lacks a detached-safe claim helper.

- [ ] **Step 4: Introduce a detached-safe claim result**

```python
# app/services/queue.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimedDownload:
    id: int
    status: str
    url: str


def claim_next(session: Session) -> ClaimedDownload | None:
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
        .returning(Download.id, Download.status, Download.url)
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    row = result.mappings().one_or_none()
    session.commit()
    if row is None:
        return None
    return ClaimedDownload(
        id=int(row["id"]),
        status=str(row["status"]),
        url=str(row["url"]),
    )
```

- [ ] **Step 5: Update the worker loop to consume the new contract**

```python
# app/main.py
class WorkerPool:
    def _claim_once_for_test(self):
        with SessionLocal() as session:
            return claim_next(session)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            claimed = self._claim_once_for_test()
            if claimed is None:
                self._stop_event.wait(1.0)
                continue
            self._run_job(claimed.id)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/queue.py app/main.py tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py
git commit -m "fix: make queue claims detached-safe for workers"
```

### Task 2: Bundle Node.js and configure yt-dlp explicitly

**Files:**
- Modify: `app/services/downloader.py`
- Modify: `Dockerfile`
- Test: `tests/unit/test_downloader_runtime_resolution.py`
- Test: `tests/integration/test_api_info.py`

- [ ] **Step 1: Write the failing downloader runtime test**

```python
from __future__ import annotations

from app.services.downloader import build_ytdlp_options


def test_build_ytdlp_options_sets_explicit_node_runtime(tmp_path) -> None:
    options = build_ytdlp_options(
        skip_download=True,
        output_dir=str(tmp_path),
        js_runtime="node",
    )

    assert options["extractor_args"]["youtube"]["player_client"] == ["default"]
    assert options["js_runtimes"] == {"node": "node"}
```

- [ ] **Step 2: Write the failing API regression test**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_info_lookup_uses_configured_js_runtime(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeYDL:
        def __init__(self, options):
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url, download):
            return {"url": url, "title": "Video", "formats": []}

    monkeypatch.setattr("yt_dlp.YoutubeDL", FakeYDL)

    with TestClient(app) as client:
        response = client.post("/api/info", json={"url": "https://example.com/v", "proxy": False, "cookies": False})

    assert response.status_code == 200
    assert captured["options"]["js_runtimes"] == {"node": "node"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py tests/integration/test_api_info.py -v`
Expected: FAIL because downloader options are built inline and do not set explicit JS runtime configuration.

- [ ] **Step 4: Extract reusable yt-dlp option construction**

```python
# app/services/downloader.py
def build_ytdlp_options(
    *,
    skip_download: bool,
    output_dir: str,
    output_template: str | None = None,
    format_selector: str | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hooks: list[ProgressHook] | None = None,
    js_runtime: str = "node",
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "noprogress": True,
        "skip_download": skip_download,
        "extractor_args": {"youtube": {"player_client": ["default"]}},
        "js_runtimes": {js_runtime: js_runtime},
    }
    if not skip_download:
        options["outtmpl"] = _output_template(output_template, output_dir)
    if format_selector:
        options["format"] = format_selector
    if proxy:
        options["proxy"] = proxy
    if cookies_file:
        options["cookiefile"] = cookies_file
    if subtitles:
        options["writesubtitles"] = True
    if progress_hooks:
        options["progress_hooks"] = progress_hooks
    return options
```

- [ ] **Step 5: Reuse the builder in both info lookup and downloads**

```python
# app/services/downloader.py
def extract_info(
    url: str,
    *,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    import yt_dlp

    ydl_opts = build_ytdlp_options(
        skip_download=True,
        output_dir="",
        proxy=proxy,
        cookies_file=cookies_file,
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)
```

```python
def run_download(
    url: str,
    video_format_id: str | None = None,
    audio_format_id: str | None = None,
    output_template: str | None = None,
    output_dir: str = "",
    audio_bitrate: str | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
    subtitles: bool = False,
    progress_hook: YtdlpProgress | None = None,
) -> str:
    fmt = _format_selector(video_format_id, audio_format_id, audio_bitrate=audio_bitrate)
    ydl_opts = build_ytdlp_options(
        skip_download=False,
        output_dir=output_dir,
        output_template=output_template,
        format_selector=fmt,
        proxy=proxy,
        cookies_file=cookies_file,
        subtitles=subtitles,
        progress_hooks=[_wrapped],
    )
```

- [ ] **Step 6: Add Node.js to the runtime image**

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_runtime_resolution.py tests/integration/test_api_info.py -v`
Expected: PASS

- [ ] **Step 8: Verify the runtime image contains Node.js**

Run: `docker build -t yourtube:phase5 . && docker run --rm yourtube:phase5 node --version`
Expected: PASS with a Node.js version string on stdout

- [ ] **Step 9: Commit**

```bash
git add app/services/downloader.py Dockerfile tests/unit/test_downloader_runtime_resolution.py tests/integration/test_api_info.py
git commit -m "fix: bundle node runtime for yt-dlp"
```

### Task 3: Add lightweight diagnostics service and UI surface

**Files:**
- Create: `app/services/diagnostics.py`
- Modify: `app/routes/pages.py`
- Create: `app/templates/partials/runtime_status.html`
- Test: `tests/unit/test_diagnostics.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing diagnostics unit test**

```python
from __future__ import annotations

from app.services.diagnostics import collect_runtime_diagnostics


def test_collect_runtime_diagnostics_reports_missing_node(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None if name == "node" else "/usr/bin/ffmpeg")

    status = collect_runtime_diagnostics(workers_enabled=True)

    assert status.js_runtime_ready is False
    assert status.level == "warning"
    assert "Node.js" in status.messages[0]
```

- [ ] **Step 2: Write the failing page rendering test**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_settings_page_renders_runtime_status(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.pages.collect_runtime_diagnostics",
        lambda workers_enabled: type(
            "Status",
            (),
            {
                "level": "warning",
                "messages": ["Node.js runtime missing."],
                "js_runtime_ready": False,
                "workers_enabled": workers_enabled,
            },
        )(),
    )

    with TestClient(app) as client:
        response = client.get("/settings")

    assert response.status_code == 200
    assert "Node.js runtime missing." in response.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_diagnostics.py tests/integration/test_pages.py -v`
Expected: FAIL because diagnostics service and rendered status partial do not exist.

- [ ] **Step 4: Implement the diagnostics service**

```python
# app/services/diagnostics.py
from __future__ import annotations

from dataclasses import dataclass
import shutil


@dataclass(frozen=True)
class RuntimeDiagnostics:
    level: str
    messages: list[str]
    js_runtime_ready: bool
    workers_enabled: bool


def collect_runtime_diagnostics(*, workers_enabled: bool) -> RuntimeDiagnostics:
    node_present = shutil.which("node") is not None
    messages: list[str] = []
    if not node_present:
        messages.append("Node.js runtime missing. YouTube extraction may be incomplete.")
    if not workers_enabled:
        messages.append("Background workers are disabled. New downloads will not start automatically.")
    level = "ok" if not messages else "warning"
    return RuntimeDiagnostics(
        level=level,
        messages=messages,
        js_runtime_ready=node_present,
        workers_enabled=workers_enabled,
    )
```

- [ ] **Step 5: Render diagnostics on the settings page**

```python
# app/routes/pages.py
from app.config import settings
from app.services.diagnostics import collect_runtime_diagnostics


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {
            "settings_values": get_all_settings(session),
            "runtime_status": collect_runtime_diagnostics(workers_enabled=settings.workers_enabled),
        },
    )
```

```html
<!-- app/templates/partials/runtime_status.html -->
{% if runtime_status.messages %}
<section class="status-panel status-panel-{{ runtime_status.level }}">
  <h2>Runtime status</h2>
  <ul>
    {% for message in runtime_status.messages %}
    <li>{{ message }}</li>
    {% endfor %}
  </ul>
</section>
{% endif %}
```

- [ ] **Step 6: Include the partial from `app/templates/pages/settings.html`**

```html
<section class="panel">
  <h1>Settings</h1>
  {% include "partials/runtime_status.html" %}
  {% include "partials/settings_form.html" %}
  <div id="settings-status"></div>
</section>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_diagnostics.py tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/diagnostics.py app/routes/pages.py app/templates/partials/runtime_status.html app/templates/pages/settings.html tests/unit/test_diagnostics.py tests/integration/test_pages.py
git commit -m "feat: add lightweight runtime diagnostics"
```

### Task 4: Document the new runtime contract and run regression checks

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the deployment documentation**

Add a short Phase 5 note to `README.md` covering:

- worker crash fixed by detached-safe queue claiming
- Docker image now bundles `Node.js`
- settings page shows runtime warnings when the environment is degraded

- [ ] **Step 2: Run the targeted regression suite**

Run: `uv run pytest tests/unit/test_queue_claim.py tests/unit/test_downloader_runtime_resolution.py tests/unit/test_diagnostics.py tests/integration/test_worker_pool.py tests/integration/test_api_info.py tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 3: Run the broader worker/settings suite**

Run: `uv run pytest tests/integration/test_worker_lifecycle.py tests/integration/test_startup_recovery.py tests/integration/test_api_settings.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: describe phase 5 runtime and diagnostics behavior"
```

## Self-Review (Phase 5)

- The worker/session crash is addressed at the queue claim boundary, not by broad session policy changes.
- Node.js is part of the runtime contract and is verified in Docker, not just documented.
- Diagnostics are small, read-only, and reusable by the future redesign.
- Tests cover the exact failure mode that produced the detached-instance error log.

## End of Phase 5

Deliverable: worker threads can claim and run jobs without detached-instance failures, the shipped runtime includes Node.js for yt-dlp YouTube extraction, and the app exposes lightweight diagnostics for degraded runtime or disabled workers.
