# YourTube Implementation Plan — Phase 17: Preview multiple direct URLs before enqueue

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a direct-URL batch preview that fetches metadata for multiple sources, shows ready/error cards, and lets the user add individual items to the queue.

**Architecture:** Keep Phase 16’s direct batch enqueue route intact and keep the existing single-item lookup untouched. Extend `app/services/batch_preview.py` with preview dataclasses plus a `resolve_batch_preview(...)` function that resolves metadata for direct URLs only. Render the result through new batch preview partials, with each ready card posting through the existing `/downloads/form` path.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, pytest, HTMX, yt-dlp

---

## Background for the worker

- Phase 16 introduced `parse_source_urls(...)` and `/downloads/batch/form`.
- The existing lookup route in [pages.py](/Users/lanh/Developer/video-downloaders/yourtube/app/routes/pages.py:153) already knows how to call `extract_info(...)`, `normalize_formats(...)`, and `build_stream_picker_payload(...)`.
- This phase does not support playlists or enqueue-all. The usable result is “preview many direct URLs, then queue any one of them.”

---

### Task 1: Add direct batch preview resolution

**Files:**

- Modify: `app/services/batch_preview.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Write the failing preview tests**

Append to `tests/unit/test_batch_preview.py`:

```python
from app.services.batch_preview import BatchPreviewResult, resolve_batch_preview


def test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch() -> None:
    def fake_extract(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "container": "mp4",
                    "vcodec": "avc1.42001E",
                    "acodec": "mp4a.40.2",
                    "resolution": "360p",
                },
            ],
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract,
    )

    assert isinstance(result, BatchPreviewResult)
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].status == "ready"
    assert result.items[0].title == "title for https://example.com/good"
    assert result.items[1].status == "error"
    assert result.items[1].error_code == "http_forbidden"
```

- [ ] **Step 2: Run the preview unit tests to confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch -v
```

Expected: FAIL with `ImportError` for `BatchPreviewResult` or `resolve_batch_preview`.

- [ ] **Step 3: Implement direct batch preview**

Update `app/services/batch_preview.py` to:

```python
from dataclasses import dataclass
from collections.abc import Callable

from app.services.downloader import build_stream_picker_payload, normalize_formats
from app.services.error_mapper import friendly_ytdlp_error


@dataclass(frozen=True)
class BatchPreviewItem:
    source_url: str
    status: str
    title: str | None
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    picker_payload: dict | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int


def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    items: list[BatchPreviewItem] = []

    for url in parse_source_urls(raw):
        try:
            info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
        except Exception as exc:  # noqa: BLE001
            code, message = friendly_ytdlp_error(str(exc))
            items.append(
                BatchPreviewItem(
                    source_url=url,
                    status="error",
                    title=None,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    picker_payload=None,
                    error_code=code,
                    error_message=message,
                )
            )
            continue

        items.append(
            BatchPreviewItem(
                source_url=url,
                status="ready",
                title=info.get("title"),
                uploader=info.get("uploader"),
                duration=info.get("duration"),
                thumbnail=info.get("thumbnail"),
                picker_payload=build_stream_picker_payload(normalize_formats(info)),
                error_code=None,
                error_message=None,
            )
        )

    valid_count = sum(1 for item in items if item.status == "ready")
    return BatchPreviewResult(
        items=items,
        valid_count=valid_count,
        invalid_count=len(items) - valid_count,
    )
```

- [ ] **Step 4: Run the updated unit tests**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS for the parser tests and the new preview test.

- [ ] **Step 5: Commit the preview service**

Run:

```bash
git add app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: resolve direct batch preview items"
```

---

### Task 2: Add the preview route and preview cards

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/home.html`
- Create: `app/templates/partials/batch_result.html`
- Create: `app/templates/partials/batch_preview_card.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing integration tests**

Add to `tests/integration/test_pages.py`:

```python
def test_home_page_batch_form_posts_to_preview_route() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="batch-form"' in response.text
    assert 'hx-post="/info/batch/form"' in response.text


def test_batch_lookup_fragment_renders_ready_and_error_cards(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        return BatchPreviewResult(
            items=[
                BatchPreviewItem(
                    source_url="https://example.com/good",
                    status="ready",
                    title="Good title",
                    uploader="Uploader",
                    duration=15,
                    thumbnail="https://example.com/thumb.jpg",
                    picker_payload={
                        "video_streams": [],
                        "audio_streams": [],
                        "has_muxed_streams": True,
                        "expected_container_by_pair": {"|": "unknown"},
                    },
                    error_code=None,
                    error_message=None,
                ),
                BatchPreviewItem(
                    source_url="https://example.com/bad",
                    status="error",
                    title=None,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    picker_payload=None,
                    error_code="http_forbidden",
                    error_message="The server returned a 403 Forbidden response.",
                ),
            ],
            valid_count=1,
            invalid_count=1,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert "Good title" in response.text
    assert "403 Forbidden" in response.text
    assert 'hx-post="/downloads/form"' in response.text
    assert 'name="url"' in response.text
```

- [ ] **Step 2: Run the integration tests to confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_batch_form_posts_to_preview_route tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: FAIL because `/info/batch/form` and the preview partials do not exist yet.

- [ ] **Step 3: Add the route and templates**

In `app/routes/pages.py`, add:

```python
from app.services.batch_preview import resolve_batch_preview
```

and:

```python
@router.post("/info/batch/form", response_class=HTMLResponse)
def info_batch_form(
    request: Request,
    sources: str = Form(...),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runtime = resolve_runtime_settings(session)
    result = resolve_batch_preview(
        sources,
        extract_info=extract_info,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
    return templates.TemplateResponse(
        request,
        "partials/batch_result.html",
        {"result": result},
    )
```

Create `app/templates/partials/batch_preview_card.html` with:

```html
{% if item.status == "ready" %}
<article class="media-card">
  {% if item.thumbnail %}
  <img src="{{ item.thumbnail }}" alt="" class="media-card-thumb" />
  {% endif %}
  <div class="media-card-body">
    <p class="eyebrow">Detected media</p>
    <h2>{{ item.title or item.source_url }}</h2>
    <dl class="meta-grid">
      <div>
        <dt>Uploader</dt>
        <dd>{{ item.uploader or "Unknown" }}</dd>
      </div>
      <div>
        <dt>Duration</dt>
        <dd>{{ item.duration or "Unknown" }}</dd>
      </div>
    </dl>
    <form
      hx-post="/downloads/form"
      hx-target="#batch-status"
      hx-swap="innerHTML"
    >
      <input type="hidden" name="url" value="{{ item.source_url }}" />
      <input type="hidden" name="title" value="{{ item.title or '' }}" />
      <input type="hidden" name="uploader" value="{{ item.uploader or '' }}" />
      <input type="hidden" name="duration" value="{{ item.duration or '' }}" />
      <input
        type="hidden"
        name="thumbnail"
        value="{{ item.thumbnail or '' }}"
      />
      <button type="submit">Add to queue</button>
    </form>
  </div>
</article>
{% else %}
<article class="media-card">
  <div class="media-card-body">
    <p class="eyebrow">Lookup failed</p>
    <h2>{{ item.source_url }}</h2>
    <p>{{ item.error_message }}</p>
  </div>
</article>
{% endif %}
```

Create `app/templates/partials/batch_result.html` with:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} valid / {{ result.invalid_count }} invalid</p>
</section>

{% for item in result.items %} {% include "partials/batch_preview_card.html" %}
{% endfor %}
```

In `app/templates/pages/home.html`, change only the batch form to:

```html
<form
  id="batch-form"
  class="lookup-form"
  hx-post="/info/batch/form"
  hx-target="#info-result"
  hx-swap="innerHTML"
></form>
```

- [ ] **Step 4: Run the integration tests to confirm they pass**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_batch_form_posts_to_preview_route tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the preview UI**

Run:

```bash
git add app/routes/pages.py app/templates/pages/home.html app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html tests/integration/test_pages.py
git commit -m "feat: preview direct batch urls before queueing"
```

---

### Task 3: Run focused regression coverage

**Files:**

- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Run preview and single-item lookup tests together**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_home_page_batch_form_posts_to_preview_route tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v
```

Expected: PASS, proving the new preview flow does not break the original single-item lookup or enqueue flow.

- [ ] **Step 2: Commit any test-only regression fix**

If a regression appears, commit the smallest fix with:

```bash
git add <exact files touched>
git commit -m "test: cover direct batch preview regressions"
```

If no fix is needed, skip this step.
