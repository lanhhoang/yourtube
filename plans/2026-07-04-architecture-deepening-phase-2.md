# Architecture Deepening Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move browser enqueue parsing out of `app/routes/pages.py` into a dedicated module without changing enqueue behavior.

**Architecture:** Keep the existing routes and queue service intact, but move form-to-`DownloadCreate` shaping into `app/services/enqueue_intake.py`. The new seam owns single enqueue parsing, raw-source batch parsing, preview-row batch parsing, duration coercion, and `target_id` normalization.

**Tech Stack:** Python 3.12, FastAPI, Starlette `FormData`, SQLAlchemy 2.x, pytest

---

## File Structure

- Create: `app/services/enqueue_intake.py`
  Purpose: Own browser form parsing for single and batch enqueue flows.
- Create: `tests/unit/test_enqueue_intake.py`
  Purpose: Lock down single and batch form parsing away from the route layer.
- Modify: `app/routes/pages.py`
  Purpose: Delegate enqueue parsing to the new module and keep route handlers thin.

---

### Task 1: Add a dedicated enqueue-intake module

**Files:**
- Create: `app/services/enqueue_intake.py`
- Create: `tests/unit/test_enqueue_intake.py`

- [ ] **Step 1: Write the failing enqueue-intake tests**

Create `tests/unit/test_enqueue_intake.py` with:

```python
from __future__ import annotations

from starlette.datastructures import FormData

from app.services.enqueue_intake import build_batch_downloads, build_single_download


def test_build_single_download_returns_payload_and_target_id() -> None:
    form = FormData(
        [
            ("url", "https://example.com/watch?v=1"),
            ("title", "Example"),
            ("duration", "42"),
            ("target_id", "batch-status"),
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("subtitles", "on"),
        ]
    )

    payload, target_id = build_single_download(form)

    assert payload.url == "https://example.com/watch?v=1"
    assert payload.title == "Example"
    assert payload.duration == 42
    assert payload.video_format_id == "137"
    assert payload.audio_format_id == "140"
    assert payload.subtitles is True
    assert target_id == "batch-status"


def test_build_single_download_falls_back_to_info_status() -> None:
    form = FormData([("url", "https://example.com/watch?v=1"), ("target_id", "wrong")])

    _payload, target_id = build_single_download(form)

    assert target_id == "info-status"


def test_build_batch_downloads_prefers_raw_sources_and_dedupes_urls() -> None:
    form = FormData([("sources", "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b")])

    payloads = build_batch_downloads(form)

    assert [payload.url for payload in payloads] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_build_batch_downloads_uses_preview_rows_when_sources_are_empty() -> None:
    form = FormData(
        [
            ("url", "https://example.com/a"),
            ("url", "https://example.com/b"),
            ("title", "Title A"),
            ("title", "Title B"),
            ("duration", "12"),
            ("duration", "24"),
            ("video_format_id", "137"),
            ("video_format_id", ""),
            ("audio_format_id", "140"),
            ("audio_format_id", "251"),
        ]
    )

    payloads = build_batch_downloads(form)

    assert len(payloads) == 2
    assert payloads[0].title == "Title A"
    assert payloads[0].duration == 12
    assert payloads[0].video_format_id == "137"
    assert payloads[0].audio_format_id == "140"
    assert payloads[1].title == "Title B"
    assert payloads[1].duration == 24
    assert payloads[1].video_format_id is None
    assert payloads[1].audio_format_id == "251"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_enqueue_intake.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.enqueue_intake'`.

- [ ] **Step 3: Write the minimal enqueue-intake module**

Create `app/services/enqueue_intake.py` with:

```python
from __future__ import annotations

from itertools import zip_longest

from starlette.datastructures import FormData, UploadFile

from app.schemas import DownloadCreate
from app.services.batch_preview import parse_source_urls


def _form_str(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


def _form_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


def build_single_download(form: FormData) -> tuple[DownloadCreate, str]:
    duration_raw = _form_str(form, "duration")
    target_id = _form_str(form, "target_id")
    if target_id != "batch-status":
        target_id = "info-status"
    payload = DownloadCreate(
        url=_form_str(form, "url") or "",
        title=_form_str(form, "title"),
        uploader=_form_str(form, "uploader"),
        duration=int(duration_raw) if duration_raw else None,
        thumbnail=_form_str(form, "thumbnail"),
        video_format_id=_form_str(form, "video_format_id"),
        audio_format_id=_form_str(form, "audio_format_id"),
        output_template=_form_str(form, "output_template"),
        audio_bitrate=_form_str(form, "audio_bitrate"),
        subtitles=form.get("subtitles") == "on",
    )
    return payload, target_id


def build_batch_downloads(form: FormData) -> list[DownloadCreate]:
    raw_sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(raw_sources)
    if urls:
        return [DownloadCreate(url=url) for url in urls]

    payloads: list[DownloadCreate] = []
    for url, title, uploader, duration, thumbnail, video_id, audio_id in zip_longest(
        _form_values(form, "url"),
        _form_values(form, "title"),
        _form_values(form, "uploader"),
        _form_values(form, "duration"),
        _form_values(form, "thumbnail"),
        _form_values(form, "video_format_id"),
        _form_values(form, "audio_format_id"),
        fillvalue="",
    ):
        if not url:
            continue
        payloads.append(
            DownloadCreate(
                url=url,
                title=title or None,
                uploader=uploader or None,
                duration=int(duration) if duration else None,
                thumbnail=thumbnail or None,
                video_format_id=video_id or None,
                audio_format_id=audio_id or None,
            )
        )
    return payloads
```

- [ ] **Step 4: Run the new tests and verify they pass**

Run:

```bash
uv run pytest tests/unit/test_enqueue_intake.py -v
```

Expected: PASS.

---

### Task 2: Delegate enqueue routes to the new seam

**Files:**
- Modify: `app/routes/pages.py`

- [ ] **Step 1: Import and use the new intake helpers**

In `app/routes/pages.py`, add:

```python
from app.services.enqueue_intake import build_batch_downloads, build_single_download
```

Replace the single enqueue route body with:

```python
    payload, target_id = build_single_download(form)
    enqueue_download(session, payload)
```

Replace the batch enqueue route body with:

```python
    payloads = build_batch_downloads(form)
    for payload in payloads:
        enqueue_download(session, payload)

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {
            "message": f"Added {len(payloads)} items to queue.",
            "target_id": "batch-status",
        },
    )
```

- [ ] **Step 2: Delete route-local form parsing helpers**

Remove these imports:

```python
from itertools import zip_longest
from starlette.datastructures import FormData, UploadFile
```

Remove these functions:

```python
def _form_str(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


def _form_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]
```

- [ ] **Step 3: Run the focused route tests**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids tests/integration/test_pages.py::test_batch_preview_card_enqueue_posts_metadata_to_queue -v
```

Expected: PASS.

---

### Task 3: Verify the phase is atomic and usable

**Files:**
- Modify: none expected

- [ ] **Step 1: Run the phase-local verification**

Run:

```bash
uv run pytest tests/unit/test_enqueue_intake.py tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids tests/integration/test_pages.py::test_batch_preview_card_enqueue_posts_metadata_to_queue -v
uv run ruff check .
uv run ty check .
```

Expected: PASS and both quality checks report `All checks passed!`.

- [ ] **Step 2: Commit the phase**

```bash
git add app/services/enqueue_intake.py app/routes/pages.py tests/unit/test_enqueue_intake.py
git commit -m "refactor: extract enqueue intake parsing"
```

- [ ] **Step 3: Confirm the worktree is clean**

Run:

```bash
git status --short
```

Expected: clean worktree.
