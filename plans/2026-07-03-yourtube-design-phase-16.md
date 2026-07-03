# YourTube Implementation Plan — Phase 16: Queue multiple direct URLs with defaults

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the home page accept multiple direct URLs and enqueue them in one action using the existing default yt-dlp selection path.

**Architecture:** Preserve the current single-URL lookup and exact-format flow. Add a small parser in `app/services/batch_preview.py` for whitespace/comma/newline-separated URLs, then add a new `/downloads/batch/form` HTMX route that converts each parsed URL into the existing `DownloadCreate` payload and reuses `enqueue_download(...)`.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, pytest, HTMX

---

## Background for the worker

- The current home page only renders one lookup form in [home.html](/Users/lanh/Developer/video-downloaders/yourtube/app/templates/pages/home.html:1) posting `url` to `/info/form`.
- The existing enqueue path already accepts one `DownloadCreate` payload through `downloads_form()` in [pages.py](/Users/lanh/Developer/video-downloaders/yourtube/app/routes/pages.py:167).
- This phase does not preview metadata, expand playlists, or expose format controls. The usable result is “paste many URLs, queue many jobs.”

---

### Task 1: Add a reusable direct-URL parser

**Files:**

- Create: `app/services/batch_preview.py`
- Test: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Write the failing parser tests**

Create `tests/unit/test_batch_preview.py` with:

```python
from __future__ import annotations

from app.services.batch_preview import parse_source_urls


def test_parse_source_urls_splits_on_whitespace_commas_and_newlines() -> None:
    raw = """
    https://example.com/a
    https://example.com/b, https://example.com/c

    https://example.com/d
    """

    assert parse_source_urls(raw) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]


def test_parse_source_urls_dedupes_exact_urls_in_first_seen_order() -> None:
    raw = "https://example.com/a https://example.com/a\nhttps://example.com/b,https://example.com/a"

    assert parse_source_urls(raw) == [
        "https://example.com/a",
        "https://example.com/b",
    ]
```

- [ ] **Step 2: Run the parser tests to confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.batch_preview'`.

- [ ] **Step 3: Write the minimal parser implementation**

Create `app/services/batch_preview.py` with:

```python
from __future__ import annotations


def parse_source_urls(raw: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for part in raw.replace(",", " ").split():
        url = part.strip()
        if not url or not url.startswith("http"):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls
```

- [ ] **Step 4: Run the parser tests to confirm they pass**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the parser**

Run:

```bash
git add app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: add batch url parser"
```

---

### Task 2: Add batch enqueue route and home form

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/home.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing page and route tests**

Add to `tests/integration/test_pages.py`:

```python
def test_home_page_renders_batch_enqueue_panel() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="batch-form"' in response.text
    assert 'name="sources"' in response.text
    assert 'hx-post="/downloads/batch/form"' in response.text


def test_batch_enqueue_route_creates_one_queued_download_per_unique_url(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data={
                "sources": "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b",
            },
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert all(row.status == "queued" for row in rows)
    assert "Added 2 items to queue." in response.text
```

- [ ] **Step 2: Run the new integration tests to confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url -v
```

Expected: FAIL because `batch-form` and `/downloads/batch/form` do not exist yet.

- [ ] **Step 3: Add the route and the batch form**

In `app/routes/pages.py`, add:

```python
from app.services.batch_preview import parse_source_urls
```

and the route:

```python
@router.post("/downloads/batch/form", response_class=HTMLResponse)
async def downloads_batch_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    sources = _form_str(form, "sources") or ""
    urls = parse_source_urls(sources)

    for url in urls:
        enqueue_download(session, DownloadCreate(url=url))

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": f"Added {len(urls)} items to queue.", "target_id": "batch-status"},
    )
```

In `app/templates/pages/home.html`, keep the existing single-item composer and append:

```html
<section class="composer-panel">
  <div class="panel-heading">
    <h2>Queue many sources</h2>
    <p>
      Paste direct video URLs and send them to the queue with default settings.
    </p>
  </div>
  <form
    id="batch-form"
    class="lookup-form"
    hx-post="/downloads/batch/form"
    hx-target="#batch-status"
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
    <button type="submit">Add all to queue</button>
  </form>
  <div id="batch-status"></div>
</section>
```

- [ ] **Step 4: Run the integration tests to confirm they pass**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the route and page changes**

Run:

```bash
git add app/routes/pages.py app/templates/pages/home.html tests/integration/test_pages.py
git commit -m "feat: queue multiple direct urls from home"
```

---

### Task 3: Run focused regression coverage

**Files:**

- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Run the batch and existing single-item page tests**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_home_page_renders_batch_enqueue_panel tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_unique_url tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v
```

Expected: PASS, proving the new batch queue form did not break the single-item lookup and enqueue flow.

- [ ] **Step 2: Run queue regression coverage**

Run:

```bash
uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py -v
```

Expected: PASS, proving queued rows created by the batch route still fit the existing worker lifecycle.

- [ ] **Step 3: Commit any test-only follow-up**

If a regression requires a small fix, commit it with:

```bash
git add <exact files touched>
git commit -m "test: cover direct batch enqueue regressions"
```

If no fix is needed, skip this step.
