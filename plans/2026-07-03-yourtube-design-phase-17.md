# YourTube Phase 17: Preview Multiple Direct URLs Before Enqueue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a direct-URL batch preview flow that resolves metadata for multiple URLs, shows ready/error cards, and lets the user enqueue one ready item at a time.

**Architecture:** Keep the existing single-item lookup route and the Phase 16 `/downloads/batch/form` direct-enqueue route intact. Extend `app/services/batch_preview.py` with preview result dataclasses and a `resolve_batch_preview(...)` helper, add a new `/info/batch/form` HTMX route, and render preview cards that reuse the existing `/downloads/form` enqueue endpoint with the same hidden metadata fields as the single-item flow.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, pytest, HTMX, yt-dlp

---

## File Structure

- Modify: `app/services/batch_preview.py`
  Purpose: Keep `parse_source_urls(...)` and add the direct-only preview resolver plus small result dataclasses.
- Modify: `app/routes/pages.py`
  Purpose: Add the batch preview route and import the new resolver without changing the existing single-item or Phase 16 enqueue routes.
- Modify: `app/templates/pages/home.html`
  Purpose: Point the batch form at the preview route and render preview output in a batch-specific result slot.
- Create: `app/templates/partials/batch_result.html`
  Purpose: Render the batch summary and include one card per preview item.
- Create: `app/templates/partials/batch_preview_card.html`
  Purpose: Render either a ready preview card with an enqueue form or an error card with a friendly message.
- Modify: `tests/unit/test_batch_preview.py`
  Purpose: Lock down direct preview success and partial-failure behavior.
- Modify: `tests/integration/test_pages.py`
  Purpose: Cover the new preview route, the updated home form wiring, and the ready/error preview markup.

## Scope Notes

- This phase is direct URLs only.
- Do not add playlist expansion, batch cap logic, enqueue-all, or stream picker reuse here.
- Do not remove or repurpose `/downloads/batch/form`; later phases still build on it.

### Task 1: Add direct batch preview resolution

**Files:**

- Modify: `app/services/batch_preview.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/unit/test_batch_preview.py`:

```python
from app.services.batch_preview import (
    BatchPreviewResult,
    resolve_batch_preview,
)


def test_resolve_batch_preview_returns_ready_items_for_valid_direct_urls() -> None:
    def fake_extract(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict:
        assert proxy is None
        assert cookies_file is None
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/a\nhttps://example.com/b",
        extract_info=fake_extract,
    )

    assert isinstance(result, BatchPreviewResult)
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert [item.source_url for item in result.items] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert [item.status for item in result.items] == ["ready", "ready"]
    assert result.items[0].title == "title for https://example.com/a"


def test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch() -> None:
    def fake_extract(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict:
        if url.endswith("bad"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        extract_info=fake_extract,
    )

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].status == "ready"
    assert result.items[0].title == "title for https://example.com/good"
    assert result.items[1].status == "error"
    assert result.items[1].error_code == "http_forbidden"
    assert result.items[1].error_message == "The server returned a 403 Forbidden response."
```

- [ ] **Step 2: Run the unit tests to confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_resolve_batch_preview_returns_ready_items_for_valid_direct_urls tests/unit/test_batch_preview.py::test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch -v
```

Expected: FAIL with `ImportError` because `BatchPreviewResult` and `resolve_batch_preview` do not exist yet.

- [ ] **Step 3: Implement the minimal preview resolver**

Replace `app/services/batch_preview.py` with:

```python
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.error_mapper import friendly_ytdlp_error


@dataclass(frozen=True)
class BatchPreviewItem:
    source_url: str
    status: str
    title: str | None
    uploader: str | None
    duration: int | None
    thumbnail: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int


def parse_source_urls(raw: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for part in re.split(r"\s+|,\s*(?=https?://)", raw):
        url = part.strip()
        if not url or not url.startswith("http"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


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

- [ ] **Step 4: Run the unit tests to confirm they pass**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS for the three parser tests plus the two new preview tests.

- [ ] **Step 5: Commit the batch preview service**

Run:

```bash
git add app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: resolve direct batch preview items"
```

### Task 2: Add the preview route and preview templates

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/home.html`
- Create: `app/templates/partials/batch_result.html`
- Create: `app/templates/partials/batch_preview_card.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/integration/test_pages.py`:

```python
def test_batch_lookup_fragment_renders_ready_and_error_cards(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        assert raw == "https://example.com/good\nhttps://example.com/bad"
        return BatchPreviewResult(
            items=[
                BatchPreviewItem(
                    source_url="https://example.com/good",
                    status="ready",
                    title="Good title",
                    uploader="Uploader",
                    duration=15,
                    thumbnail="https://example.com/thumb.jpg",
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
                    error_code="http_forbidden",
                    error_message="The server returned a 403 Forbidden response.",
                ),
            ],
            valid_count=1,
            invalid_count=1,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post(
            "/info/batch/form",
            data={"sources": "https://example.com/good\nhttps://example.com/bad"},
        )

    assert response.status_code == 200
    assert "Batch preview" in response.text
    assert "1 ready / 1 failed" in response.text
    assert "Good title" in response.text
    assert "403 Forbidden" in response.text
    assert 'hx-post="/downloads/form"' in response.text
    assert 'hx-target="#batch-status"' in response.text
    assert 'name="url"' in response.text
    assert 'name="title"' in response.text
    assert 'name="uploader"' in response.text
    assert 'name="duration"' in response.text
    assert 'name="thumbnail"' in response.text
```

- [ ] **Step 2: Run the integration tests to confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: FAIL because `/info/batch/form`, `#batch-result`, and the new preview partials do not exist yet.

- [ ] **Step 3: Implement the preview route**

Update the import block in `app/routes/pages.py` to:

```python
from app.services.batch_preview import parse_source_urls, resolve_batch_preview
```

Add this route immediately after `info_form(...)`:

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

- [ ] **Step 4: Implement the batch templates**

Create `app/templates/partials/batch_result.html` with:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} ready / {{ result.invalid_count }} failed</p>
</section>

{% for item in result.items %} {% include "partials/batch_preview_card.html" %}
{% endfor %}
```

Create `app/templates/partials/batch_preview_card.html` with:

```html
{% if item.status == "ready" %}
<section class="media-card">
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
</section>
{% else %}
<section class="media-card">
  <div class="media-card-body">
    <p class="eyebrow">Lookup failed</p>
    <h2>{{ item.source_url }}</h2>
    <p>{{ item.error_message }}</p>
  </div>
</section>
{% endif %}
```

- [ ] **Step 5: Rewire the home page batch form**

Replace the batch form section in `app/templates/pages/home.html` with:

```html
<section class="composer-panel">
  <div class="panel-heading">
    <h2>Queue many sources</h2>
    <p>
      Paste direct video URLs to preview them before adding anything to the
      queue.
    </p>
  </div>
  <form
    id="batch-form"
    class="lookup-form"
    hx-post="/info/batch/form"
    hx-target="#batch-result"
    hx-swap="innerHTML"
  >
    <label for="batch-sources">Sources</label>
    <textarea
      id="batch-sources"
      name="sources"
      rows="5"
      placeholder="https://example.com/a&#10;https://example.com/b"
      required
    ></textarea>
    <div class="toggle-row">
      <label><input type="checkbox" name="proxy" /> Use saved proxy</label>
      <label><input type="checkbox" name="cookies" /> Use saved cookies</label>
    </div>
    <button type="submit">Preview batch</button>
  </form>
  <div id="batch-status"></div>
  <div id="batch-result" class="lookup-result-slot"></div>
</section>
```

- [ ] **Step 6: Run the integration tests to confirm they pass**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS.

- [ ] **Step 7: Commit the preview route and templates**

Run:

```bash
git add app/routes/pages.py app/templates/pages/home.html app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html tests/integration/test_pages.py
git commit -m "feat: preview direct batch urls before queueing"
```

### Task 3: Run focused regression coverage

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v
```

Expected: PASS. This proves the new batch preview flow works, the old direct batch enqueue route still works, and the single-item lookup flow still renders its existing enqueue form.

- [ ] **Step 2: Run the full page and partial coverage touched by this phase**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py tests/integration/test_partials.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit any regression-only test fix if needed**

If the regression suite exposes a small test-only issue, commit it with:

```bash
git add tests/unit/test_batch_preview.py tests/integration/test_pages.py tests/integration/test_partials.py
git commit -m "test: cover direct batch preview regressions"
```

If no further changes are needed after the previous commit, skip this step.

## Self-Review Notes

- Spec coverage: direct-only preview, partial failure handling, home form rewiring, and per-item enqueue are all covered. Playlist expansion, enqueue-all, and stream pickers are intentionally excluded because they belong to later phases.
- Placeholder scan: no `TODO`, `TBD`, or implicit “handle it somehow” steps remain.
- Type consistency: the plan uses `BatchPreviewItem`, `BatchPreviewResult`, and `resolve_batch_preview(...)` consistently across unit tests, route code, and template tests.
