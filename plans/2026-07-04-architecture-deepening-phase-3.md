# Architecture Deepening Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify single and batch preview lookup behind one service module without changing preview rendering behavior.

**Architecture:** Keep the existing route URLs, templates, and batch-preview output shape intact, but move preview lookup policy into `app/services/preview.py`. The new seam owns single lookup, batch lookup orchestration, playlist expansion wiring, and stream-picker payload shaping while routes become thin render adapters.

**Tech Stack:** Python 3.12, FastAPI, pytest, yt-dlp

---

## File Structure

- Create: `app/services/preview.py`
  Purpose: Own single and batch preview lookup policy.
- Create: `tests/unit/test_preview.py`
  Purpose: Lock down the new preview seam away from routes.
- Modify: `app/routes/pages.py`
  Purpose: Delegate single and batch preview lookups to the new module.
- Modify: `tests/integration/test_pages.py`
  Purpose: Keep route coverage focused on rendering and seam wiring.

---

### Task 1: Add a shared preview service module

**Files:**
- Create: `app/services/preview.py`
- Create: `tests/unit/test_preview.py`

- [ ] **Step 1: Write the failing preview tests**

Create `tests/unit/test_preview.py` with:

```python
from __future__ import annotations

from app.services.preview import resolve_batch_preview, resolve_single_preview


def test_resolve_single_preview_builds_picker_payload() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_single_preview(
        "https://example.com/watch?v=1",
        extract_info=fake_extract_info,
    )

    assert result.url == "https://example.com/watch?v=1"
    assert result.title == "Example title"
    assert result.picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.picker_payload["audio_streams"][0]["format_id"] == "140"


def test_resolve_batch_preview_keeps_existing_batch_behavior() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2"},
            ],
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract_info,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.items[1].error_code == "http_forbidden"


def test_resolve_batch_preview_expands_playlists_with_flat_lookup() -> None:
    def fake_extract_info(url: str, **_kwargs) -> dict:
        return {
            "title": "Episode 1",
            "uploader": "Uploader",
            "duration": 10,
            "thumbnail": "https://example.com/1.jpg",
            "formats": [],
        }

    result = resolve_batch_preview(
        "https://example.com/list",
        extract_info=fake_extract_info,
        expand_playlist_entries=lambda url, **_kwargs: ["https://example.com/watch?v=1"],
        extract_flat_info=lambda url, **_kwargs: {"entries": [{"url": "https://example.com/watch?v=1"}]},
    )

    assert result.valid_count == 1
    assert result.items[0].source_url == "https://example.com/watch?v=1"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_preview.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.preview'`.

- [ ] **Step 3: Write the shared preview module**

Create `app/services/preview.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.services.batch_preview import BatchPreviewResult, expand_playlist_entries
from app.services.downloader import (
    StreamPickerPayload,
    build_stream_picker_payload,
    extract_flat_info,
    normalize_formats,
)


@dataclass(frozen=True)
class SinglePreviewResult:
    url: str
    title: str
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    picker_payload: StreamPickerPayload


def resolve_single_preview(
    url: str,
    *,
    extract_info,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> SinglePreviewResult:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    formats = normalize_formats(info)
    return SinglePreviewResult(
        url=url,
        title=info.get("title", ""),
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        picker_payload=build_stream_picker_payload(formats),
    )


def resolve_batch_preview(
    raw: str,
    *,
    extract_info,
    expand_playlist_entries=expand_playlist_entries,
    extract_flat_info=extract_flat_info,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    from app.services.batch_preview import resolve_batch_preview as resolve_existing_batch_preview

    return resolve_existing_batch_preview(
        raw,
        extract_info=extract_info,
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=proxy,
            cookies_file=cookies_file,
        ),
        proxy=proxy,
        cookies_file=cookies_file,
    )
```

- [ ] **Step 4: Run the new tests and verify they pass**

Run:

```bash
uv run pytest tests/unit/test_preview.py -v
```

Expected: PASS.

---

### Task 2: Delegate preview routes to the new seam

**Files:**
- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Replace direct preview wiring in the routes**

In `app/routes/pages.py`, replace:

```python
from app.services.batch_preview import (
    expand_playlist_entries,
    parse_source_urls,
    resolve_batch_preview,
)
from app.services.downloader import (
    build_stream_picker_payload,
    extract_flat_info,
    extract_info,
    normalize_formats,
)
```

with:

```python
from app.services.downloader import extract_info
from app.services.preview import resolve_batch_preview, resolve_single_preview
```

Replace the single preview route body with:

```python
    result = resolve_single_preview(
        url,
        extract_info=extract_info,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
```

Update the template context to:

```python
        {
            "url": result.url,
            "title": result.title,
            "uploader": result.uploader,
            "duration": result.duration,
            "thumbnail": result.thumbnail,
            "picker_payload": result.picker_payload,
        },
```

Replace the batch preview route body with:

```python
    result = resolve_batch_preview(
        sources,
        extract_info=extract_info,
        proxy=proxy_url,
        cookies_file=cookies_file,
    )
```

- [ ] **Step 2: Add a route-level seam test for single preview lookup**

In `tests/integration/test_pages.py`, add:

```python
def test_info_lookup_route_uses_preview_service(monkeypatch) -> None:
    from app.services.preview import SinglePreviewResult

    def fake_resolve_single_preview(url: str, **_kwargs):
        assert url == "https://example.com/watch?v=1"
        return SinglePreviewResult(
            url=url,
            title="Example title",
            uploader="Uploader",
            duration=123,
            thumbnail="https://example.com/thumb.jpg",
            picker_payload={
                "video_streams": [],
                "audio_streams": [],
                "has_muxed_streams": True,
                "expected_container_by_pair": {"|": "unknown"},
            },
        )

    monkeypatch.setattr("app.routes.pages.resolve_single_preview", fake_resolve_single_preview)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert "Example title" in response.text
```

Keep the existing batch-preview route patches unchanged.

- [ ] **Step 3: Run the focused route tests**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_info_lookup_route_uses_preview_service tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS.

---

### Task 3: Verify the phase is atomic and usable

**Files:**
- Modify: none expected

- [ ] **Step 1: Run the phase-local verification**

Run:

```bash
uv run pytest tests/unit/test_preview.py tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_info_lookup_route_uses_preview_service tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker -v
```

Expected: PASS.

- [ ] **Step 2: Commit the phase**

```bash
git add app/services/preview.py app/routes/pages.py tests/unit/test_preview.py tests/integration/test_pages.py
git commit -m "refactor: unify preview lookup"
```

- [ ] **Step 3: Confirm the worktree is clean**

Run:

```bash
git status --short
```

Expected: clean worktree.
