# YourTube Implementation Plan — Phase 11: Remove unused JSON `/api/*` mutation endpoints

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unused JSON `/api/*` mutation surface (`app/routes/api.py`) since the in-app UI exclusively uses the HTML/HTMX routes in `app/routes/pages.py`. Keep the one real consumer — the library "Download file" link — by relocating it to `pages.py`.

**Architecture:** `app/routes/pages.py` gains a `GET /downloads/{job_id}/file` route ported from `app/routes/api.py`. `app/routes/api.py` and its dedicated Pydantic response models are deleted, along with their test files. `app/main.py` stops mounting the API router.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic, Jinja2, pytest

---

## Background for the worker

- `app/routes/api.py` defines 8 JSON endpoints under `/api/*`. Every one of
  them except `GET /api/downloads/{job_id}/file` has a working HTML/HTMX
  equivalent already in `app/routes/pages.py`:
  - `POST /api/info` → `POST /info/form`
  - `POST /api/downloads` → `POST /downloads/form`
  - `POST /api/downloads/{id}/cancel` → `POST /queue/cancel/{job_id}`
  - `DELETE /api/library/{id}` → `DELETE /library/delete/{job_id}`
  - `PUT /api/settings` → `PUT /settings/form`
  - `POST /api/settings/reset` → `POST /settings/reset`
- `GET /api/downloads/{job_id}/file` (api.py lines 97-127) is linked from
  `app/templates/partials/library_rows.html:8` as
  `<a href="/api/downloads/{{ row.id }}/file">Download file</a>` — this is a
  real, used feature with no SSR equivalent. It must be ported, not deleted.
- `app/schemas.py` defines `InfoRequest`, `InfoResponse`, `DownloadResponse`,
  `SettingsResponse`, `MutationOkResponse`, `ErrorResponse` — all used **only**
  by `app/routes/api.py` (confirmed by grep). `DownloadCreate`, `FormatInfo`,
  and `StreamKind` are used elsewhere and must be kept.
- Four integration test files exist only to test `api.py`:
  `tests/integration/test_api_info.py`, `test_api_downloads.py`,
  `test_api_settings.py`, `test_api_library.py`. `test_api_downloads.py` also
  contains the only coverage of the file-download endpoint
  (`test_download_file_serves_completed_job`,
  `test_download_file_rejects_non_done_job`) — that coverage must be ported to
  `tests/integration/test_pages.py` before the file is deleted.

---

### Task 1: Port the file-download route into `pages.py`

**Files:**
- Modify: `app/routes/pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing tests**

Add to the end of `tests/integration/test_pages.py`:

```python
def test_download_file_serves_completed_job(db_session_visible, tmp_path: Path) -> None:
    file_path = tmp_path / "video.mp4"
    file_path.write_bytes(b"data")
    row = Download(
        url="https://example.com/done",
        status="done",
        progress=100.0,
        file_path=str(file_path),
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/downloads/{row.id}/file")

    assert response.status_code == 200
    assert response.content == b"data"


def test_download_file_rejects_non_done_job(db_session_visible) -> None:
    row = Download(url="https://example.com/queued", status="queued", progress=0.0)
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get(f"/downloads/{row.id}/file")

    assert response.status_code == 409


def test_download_file_returns_404_for_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.get("/downloads/9999/file")

    assert response.status_code == 404
```

Check the top of `tests/integration/test_pages.py` for existing imports of
`Path` (from `pathlib`) and `Download` (from `app.models`) and `TestClient`
(from `fastapi.testclient`) and `app` (from `app.main`). Add any that are
missing — `tmp_path` is a built-in pytest fixture and needs no import.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_pages.py -k download_file -v`

Expected: FAIL with 404 (route `/downloads/{job_id}/file` does not exist yet,
so FastAPI returns 404 for all three — the "rejects_non_done_job" and
"returns_404_for_unknown_id" tests may appear to pass by accident; the
"serves_completed_job" test must FAIL with a non-200 status).

- [ ] **Step 3: Add the route to `pages.py`**

In `app/routes/pages.py`, add to the imports:

```python
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
```

(merge into the existing `from fastapi import ...` and
`from fastapi.responses import ...` lines rather than duplicating them)

and add:

```python
from app.models import Download
```

Then add this route in the "HTMX fragment routes" section (near
`library_rows`):

```python
@router.get("/downloads/{job_id}/file")
def download_file(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    """Stream the completed file for a ``done`` job.

    Returns 404 when the row is missing, 409 when the job is not yet
    ready, and 404 when the on-disk file has been moved or deleted.
    """
    row = session.get(Download, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Download not found.")
    if row.status != "done" or not row.file_path:
        raise HTTPException(status_code=409, detail="Download is not ready.")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is missing.")
    return FileResponse(path)
```

`Path` is already imported at the top of `pages.py` (`from pathlib import Path`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -k download_file -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: serve completed download files from pages routes"
```

---

### Task 2: Point the library template at the new route

**Files:**
- Modify: `app/templates/partials/library_rows.html`
- Test: `tests/integration/test_partials.py`

- [ ] **Step 1: Write the failing test**

Find the existing `test_library_rows_partial_renders_archive_entries` test in
`tests/integration/test_partials.py`. Add an assertion that the rendered HTML
links to the new path. If the existing test doesn't render a `done` row with
an `id`, add a new test:

```python
def test_library_rows_partial_links_to_pages_file_route(db_session_visible) -> None:
    row = Download(
        url="https://example.com/done",
        title="Done",
        status="done",
        progress=100.0,
        file_path="/tmp/done.mp4",
    )
    db_session_visible.add(row)
    db_session_visible.commit()
    db_session_visible.refresh(row)

    with TestClient(app) as client:
        response = client.get("/library/rows")

    assert response.status_code == 200
    assert f'href="/downloads/{row.id}/file"' in response.text
    assert f'href="/api/downloads/{row.id}/file"' not in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_partials.py -k pages_file_route -v`

Expected: FAIL — `href="/api/downloads/{row.id}/file"` is still present (the
"not in" assertion fails) and `href="/downloads/{row.id}/file"` is absent.

- [ ] **Step 3: Update the template**

In `app/templates/partials/library_rows.html`, change line 8:

```diff
-    <a href="/api/downloads/{{ row.id }}/file">Download file</a>
+    <a href="/downloads/{{ row.id }}/file">Download file</a>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_partials.py -k pages_file_route -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/partials/library_rows.html tests/integration/test_partials.py
git commit -m "feat: link library downloads to pages file route"
```

---

### Task 3: Remove `app/routes/api.py` and its router registration

**Files:**
- Modify: `app/main.py`
- Delete: `app/routes/api.py`
- Delete: `tests/integration/test_api_info.py`, `tests/integration/test_api_downloads.py`, `tests/integration/test_api_settings.py`, `tests/integration/test_api_library.py`

- [ ] **Step 1: Remove the router import and registration from `app/main.py`**

```diff
-from app.routes.api import router as api_router
 from app.routes.pages import router as pages_router
```

```diff
-app.include_router(api_router)
 app.include_router(pages_router)
```

- [ ] **Step 2: Delete the API route module and its tests**

```bash
git rm app/routes/api.py
git rm tests/integration/test_api_info.py tests/integration/test_api_downloads.py tests/integration/test_api_settings.py tests/integration/test_api_library.py
```

(Task 1 already ported the file-download coverage out of
`test_api_downloads.py` into `test_pages.py`, so no coverage is lost.)

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS, with the 4 deleted files no longer collected. If any other
test imports from `app.routes.api`, fix or remove that import (grep first:
`grep -rn "routes.api\|routes import api" tests/ app/`).

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: remove unused JSON api router"
```

---

### Task 4: Remove API-only Pydantic schemas

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Confirm nothing else references the schemas being removed**

Run: `grep -rn "InfoRequest\|InfoResponse\|DownloadResponse\|SettingsResponse\|MutationOkResponse\|ErrorResponse" app/ tests/`

Expected: no matches outside `app/schemas.py` (Task 3 already removed the only
consumer, `app/routes/api.py`).

- [ ] **Step 2: Remove the unused classes from `app/schemas.py`**

Delete the `InfoRequest`, `InfoResponse`, `DownloadResponse`, `ErrorResponse`,
`SettingsResponse`, and `MutationOkResponse` class definitions. Keep
`DownloadCreate`, `StreamKind`, and `FormatInfo` — they're used by
`app/services/downloader.py` and `app/routes/pages.py`.

The file should retain this structure (imports may need trimming — check that
`ConfigDict` is still used; if not, remove it from the `pydantic` import):

```python
"""Pydantic request and response contracts.

These schemas are the *only* types used in route signatures and responses.
ORM instances from ``app.models`` must never be returned directly to clients.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DownloadCreate(BaseModel):
    """Request body for enqueuing a new download."""

    url: str = Field(..., min_length=1)
    title: str | None = None
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    video_format_id: str | None = None
    audio_format_id: str | None = None
    output_template: str | None = None
    audio_bitrate: str | None = None
    subtitles: bool = False


type StreamKind = Literal["video", "audio", "muxed"]


class FormatInfo(BaseModel):
    """A single format entry returned by the format picker."""

    format_id: str
    ext: str
    stream_kind: StreamKind = "muxed"
    audio_channels: int | None = None
    resolution: str | None = None
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None
    vbr: float | None = None
    filesize: int | None = None
    tbr: float | None = None
    format_note: str | None = None
    container: str | None = None
```

`datetime` import: check whether it's still used anywhere in the file after
the removals (it was only used by the removed `DownloadResponse`); remove the
`from datetime import datetime` import if unused.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/schemas.py
git commit -m "feat: remove unused API-only schemas"
```

---

## Self-Review Notes

- **Spec coverage:** all 8 `/api/*` endpoints accounted for — 6 removed
  (HTML equivalents exist), 1 relocated to `pages.py` (file download), 1
  (`GET /api/settings`, JSON read) had no SSR equivalent and no consumer —
  it's removed along with the rest of `api.py` in Task 3 since nothing reads
  it (grep confirms no template or test outside `test_api_settings.py`
  references it).
- **Placeholder scan:** no TBD/TODO; every step has concrete code.
- **Type consistency:** `Download`, `FileResponse`, `HTTPException`,
  `Path` — all match real names from `app/models.py` and FastAPI/Starlette.
