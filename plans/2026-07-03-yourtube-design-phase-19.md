# YourTube Implementation Plan — Phase 19: Expand playlists in batch preview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the batch preview accept playlist-like sources, expand them into individual items, dedupe them, and cap the final preview at 50 items.

**Architecture:** Build playlist expansion on top of the existing batch preview service instead of inventing a second preview path. Add a flat yt-dlp extraction helper in `app/services/downloader.py`, an `expand_playlist_entries(...)` helper plus capped expansion logic in `app/services/batch_preview.py`, then pass that expander from the batch preview route.

**Tech Stack:** Python 3.12, FastAPI, yt-dlp, pytest, HTMX

---

## Background for the worker

- Phase 18 already previews direct URLs and enqueues all valid items.
- The current direct preview path treats every parsed URL as a final video URL.
- This phase adds playlist support only to batch preview. The existing single-item flow remains unchanged.

---

### Task 1: Add capped playlist expansion helpers

**Files:**

- Modify: `app/services/downloader.py`
- Modify: `app/services/batch_preview.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Write the failing playlist unit tests**

Append to `tests/unit/test_batch_preview.py`:

```python
from app.services.batch_preview import expand_playlist_entries, expand_source_urls


def test_expand_playlist_entries_returns_entry_urls_from_flat_playlist() -> None:
    def fake_extract(url: str, *, proxy: str | None = None, cookies_file: str | None = None) -> dict:
        if url == "https://example.com/list":
            return {
                "entries": [
                    {"url": "https://example.com/watch?v=1"},
                    {"url": "https://example.com/watch?v=2"},
                ]
            }
        return {"title": "single"}

    assert expand_playlist_entries("https://example.com/list", extract_info=fake_extract) == [
        "https://example.com/watch?v=1",
        "https://example.com/watch?v=2",
    ]
    assert expand_playlist_entries("https://example.com/watch?v=3", extract_info=fake_extract) == [
        "https://example.com/watch?v=3",
    ]


def test_expand_source_urls_caps_after_playlist_expansion() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [f"https://example.com/watch?v={index}" for index in range(60)]
        return [url]

    urls, truncated_count = expand_source_urls(
        ["https://example.com/list", "https://example.com/after"],
        expand_playlist=fake_expand,
        limit=50,
    )

    assert len(urls) == 50
    assert truncated_count == 11
```

- [ ] **Step 2: Run the new playlist tests to confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_expand_playlist_entries_returns_entry_urls_from_flat_playlist tests/unit/test_batch_preview.py::test_expand_source_urls_caps_after_playlist_expansion -v
```

Expected: FAIL because the helpers and return shape do not exist yet.

- [ ] **Step 3: Implement flat extraction and playlist expansion**

In `app/services/downloader.py`, add:

```python
def extract_flat_info(
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
    ydl_opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)
```

In `app/services/batch_preview.py`, add:

```python
def expand_playlist_entries(
    url: str,
    *,
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> list[str]:
    info = extract_info(url, proxy=proxy, cookies_file=cookies_file)
    entries = info.get("entries")
    if not isinstance(entries, list):
        return [url]

    urls: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_url = entry.get("url")
        if isinstance(entry_url, str) and entry_url.startswith("http"):
            urls.append(entry_url)
    return urls or [url]


def expand_source_urls(
    source_urls: list[str],
    *,
    expand_playlist: Callable[[str], list[str]],
    limit: int = 50,
) -> tuple[list[str], int]:
    seen: set[str] = set()
    expanded: list[str] = []
    truncated_count = 0

    for source_url in source_urls:
        for resolved_url in expand_playlist(source_url):
            if resolved_url in seen:
                continue
            seen.add(resolved_url)
            if len(expanded) >= limit:
                truncated_count += 1
                continue
            expanded.append(resolved_url)

    return expanded, truncated_count
```

Update `resolve_batch_preview(...)` so it accepts:

```python
def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    expand_playlist: Callable[[str], list[str]] | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
```

and uses:

```python
source_urls = parse_source_urls(raw)
expanded_urls, truncated_count = expand_source_urls(
    source_urls,
    expand_playlist=expand_playlist or (lambda url: [url]),
)
```

- [ ] **Step 4: Run the unit tests to confirm they pass**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS for parser, preview, playlist, and cap coverage.

- [ ] **Step 5: Commit the playlist helpers**

Run:

```bash
git add app/services/downloader.py app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: expand playlists in batch preview"
```

---

### Task 2: Wire playlist expansion into the route and UI

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing integration tests**

Add to `tests/integration/test_pages.py`:

```python
def test_batch_lookup_route_expands_playlist_sources(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        assert "https://example.com/list" in raw
        return BatchPreviewResult(
            items=[
                BatchPreviewItem(
                    source_url="https://example.com/watch?v=1",
                    status="ready",
                    title="Episode 1",
                    uploader="Uploader",
                    duration=10,
                    thumbnail="https://example.com/1.jpg",
                    error_code=None,
                    error_message=None,
                )
            ],
            valid_count=1,
            invalid_count=0,
            truncated_count=0,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/list"})

    assert response.status_code == 200
    assert "Episode 1" in response.text


def test_batch_result_renders_truncation_notice(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewResult

    def fake_resolve_batch_preview(raw: str, **_kwargs):
        return BatchPreviewResult(items=[], valid_count=0, invalid_count=0, truncated_count=7)

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/list"})

    assert response.status_code == 200
    assert "Skipped 7 item(s) because the batch limit is 50." in response.text
```

- [ ] **Step 2: Run the integration tests to confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_route_expands_playlist_sources tests/integration/test_pages.py::test_batch_result_renders_truncation_notice -v
```

Expected: FAIL because `truncated_count` is not yet part of the result shape and the route does not pass an expander.

- [ ] **Step 3: Update the route and template**

In `app/routes/pages.py`, add:

```python
from app.services.batch_preview import expand_playlist_entries, resolve_batch_preview
from app.services.downloader import extract_flat_info
```

and update `info_batch_form(...)` to call:

```python
result = resolve_batch_preview(
    sources,
    extract_info=extract_info,
    expand_playlist=lambda url: expand_playlist_entries(
        url,
        extract_info=extract_flat_info,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    ),
    proxy=runtime.proxy_url if proxy else None,
    cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
)
```

Update `app/templates/partials/batch_result.html` so the header becomes:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} valid / {{ result.invalid_count }} invalid</p>
  {% if result.truncated_count %}
  <p>
    Skipped {{ result.truncated_count }} item(s) because the batch limit is 50.
  </p>
  {% endif %}
</section>
```

- [ ] **Step 4: Run the integration tests to confirm they pass**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_route_expands_playlist_sources tests/integration/test_pages.py::test_batch_result_renders_truncation_notice -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the playlist route wiring**

Run:

```bash
git add app/routes/pages.py app/templates/partials/batch_result.html tests/integration/test_pages.py
git commit -m "feat: preview playlist entries in batch flow"
```

---

### Task 3: Run focused regression coverage

**Files:**

- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Run the playlist-aware regression suite**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_batch_lookup_route_expands_playlist_sources tests/integration/test_pages.py::test_batch_result_renders_truncation_notice tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: PASS.

- [ ] **Step 2: Run worker and queue regressions**

Run:

```bash
uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py tests/integration/test_partials.py -v
```

Expected: PASS, proving playlist-expanded items still become ordinary queued jobs.

- [ ] **Step 3: Commit any test-only regression fix**

If a small fix is needed, commit it with:

```bash
git add <exact files touched>
git commit -m "test: cover playlist batch preview regressions"
```

If no fix is needed, skip this step.
