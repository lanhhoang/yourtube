# YourTube Implementation Plan — Phase 18: Enqueue all valid direct preview items

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the direct batch preview queue every valid previewed item in one action using default format selection.

**Architecture:** Reuse the existing `DownloadCreate` path. Keep the Phase 17 per-item preview cards, add a batch-level form that posts repeated hidden metadata fields, and extend `/downloads/batch/form` so it accepts either raw `sources` text (Phase 16) or repeated metadata fields (Phase 18).

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, pytest, HTMX

---

## Background for the worker

- Phase 16 already created `/downloads/batch/form` for raw text input.
- Phase 17 renders ready cards with metadata and individual “Add to queue” buttons.
- This phase still uses default yt-dlp format selection. It does not expand playlists or show per-item stream pickers yet.

---

### Task 1: Extend the batch route to accept repeated hidden fields

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing enqueue-all integration test**

Add to `tests/integration/test_pages.py`:

```python
def test_batch_enqueue_route_creates_one_queued_download_per_valid_item(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data=[
                ("url", "https://example.com/a"),
                ("title", "Title A"),
                ("uploader", "Uploader A"),
                ("duration", "12"),
                ("thumbnail", "https://example.com/a.jpg"),
                ("url", "https://example.com/b"),
                ("title", "Title B"),
                ("uploader", "Uploader B"),
                ("duration", "24"),
                ("thumbnail", "https://example.com/b.jpg"),
            ],
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert rows[0].title == "Title A"
    assert rows[1].title == "Title B"
```

- [ ] **Step 2: Run the enqueue-all test to confirm it fails**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: FAIL because the current route only reads `sources`.

- [ ] **Step 3: Teach the route to accept both payload shapes**

In `app/routes/pages.py`, add:

```python
def _form_values(form: FormData, key: str) -> list[str]:
    values = form.getlist(key)
    out: list[str] = []
    for value in values:
        if isinstance(value, UploadFile):
            continue
        out.append(str(value))
    return out
```

Then replace `downloads_batch_form(...)` with:

```python
@router.post("/downloads/batch/form", response_class=HTMLResponse)
async def downloads_batch_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    raw_sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(raw_sources)

    if urls:
        for url in urls:
            enqueue_download(session, DownloadCreate(url=url))
        message = f"Added {len(urls)} items to queue."
        return templates.TemplateResponse(
            request,
            "partials/status_message.html",
            {"message": message, "target_id": "batch-status"},
        )

    urls = _form_values(form, "url")
    titles = _form_values(form, "title")
    uploaders = _form_values(form, "uploader")
    durations = _form_values(form, "duration")
    thumbnails = _form_values(form, "thumbnail")

    for index, url in enumerate(urls):
        enqueue_download(
            session,
            DownloadCreate(
                url=url,
                title=titles[index] or None,
                uploader=uploaders[index] or None,
                duration=int(durations[index]) if durations[index] else None,
                thumbnail=thumbnails[index] or None,
            ),
        )

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": f"Added {len(urls)} items to queue.", "target_id": "batch-status"},
    )
```

- [ ] **Step 4: Run the enqueue-all test to confirm it passes**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: PASS.

- [ ] **Step 5: Commit the dual-shape batch route**

Run:

```bash
git add app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: enqueue all direct batch preview items"
```

---

### Task 2: Add the enqueue-all form to the preview partial

**Files:**

- Modify: `app/templates/partials/batch_result.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing markup test**

Add to `tests/integration/test_pages.py`:

```python
def test_batch_lookup_fragment_renders_enqueue_all_form(monkeypatch) -> None:
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
                    error_code=None,
                    error_message=None,
                )
            ],
            valid_count=1,
            invalid_count=0,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert 'id="batch-enqueue-form"' in response.text
    assert 'hx-post="/downloads/batch/form"' in response.text
    assert 'name="title"' in response.text
```

- [ ] **Step 2: Run the markup test to confirm it fails**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form -v
```

Expected: FAIL because `batch_result.html` has no enqueue-all form yet.

- [ ] **Step 3: Add the enqueue-all form**

Replace `app/templates/partials/batch_result.html` with:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} valid / {{ result.invalid_count }} invalid</p>
</section>

<form
  id="batch-enqueue-form"
  hx-post="/downloads/batch/form"
  hx-target="#batch-status"
  hx-swap="innerHTML"
>
  {% for item in result.items if item.status == "ready" %}
  <input type="hidden" name="url" value="{{ item.source_url }}" />
  <input type="hidden" name="title" value="{{ item.title or '' }}" />
  <input type="hidden" name="uploader" value="{{ item.uploader or '' }}" />
  <input type="hidden" name="duration" value="{{ item.duration or '' }}" />
  <input type="hidden" name="thumbnail" value="{{ item.thumbnail or '' }}" />
  {% endfor %}
  <button type="submit">Enqueue all valid</button>
</form>

{% for item in result.items %} {% include "partials/batch_preview_card.html" %}
{% endfor %}
```

- [ ] **Step 4: Run the enqueue-all markup test and preview regression**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the enqueue-all UI**

Run:

```bash
git add app/templates/partials/batch_result.html tests/integration/test_pages.py
git commit -m "feat: add enqueue all to direct batch preview"
```

---

### Task 3: Run focused regression coverage

**Files:**

- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Run the direct batch regression suite**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: PASS.

- [ ] **Step 2: Run library and queue regressions**

Run:

```bash
uv run pytest tests/unit/test_library.py tests/integration/test_worker_pool.py -v
```

Expected: PASS, proving metadata-carrying queued rows still work end to end.

- [ ] **Step 3: Commit any test-only regression fix**

If a small fix is required, commit it with:

```bash
git add <exact files touched>
git commit -m "test: cover enqueue-all direct batch regressions"
```

If no fix is needed, skip this step.
