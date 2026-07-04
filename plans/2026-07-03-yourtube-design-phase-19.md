# YourTube Implementation Plan — Phase 19: Expand playlists in batch preview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let batch preview accept playlist-like sources, expand them into individual preview items, dedupe them, and cap the final preview at 50 items.

**Architecture:** Reuse the existing batch preview path. Add one flat yt-dlp helper, add playlist expansion/capping helpers inside `app/services/batch_preview.py`, and pass the expander from the batch preview route. If flat playlist expansion fails, fall back to the original source so the existing metadata lookup path renders the friendly per-item error instead of returning a 500.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, yt-dlp, pytest, HTMX

---

## Current repo baseline

- `app/services/batch_preview.py` already parses direct URLs, dedupes exact source strings, resolves metadata, and marks playlist-shaped metadata as `unsupported_playlist`.
- `app/routes/pages.py` imports `parse_source_urls` for `/downloads/batch/form`; keep that import when adding playlist helpers.
- `app/templates/partials/batch_result.html` renders `ready / failed` counts and hidden `url` fields for every ready preview item. Expanded child URLs will enqueue through the existing hidden fields.
- Existing tests construct `BatchPreviewResult` without a truncation field, so `truncated_count` must default to `0` to keep older tests small.

## File structure

- Modify: `app/services/downloader.py`
  - Add `extract_flat_info(...)`, a thin yt-dlp wrapper with `extract_flat=True`.
- Modify: `app/services/batch_preview.py`
  - Add `truncated_count` to `BatchPreviewResult` with a default.
  - Add `expand_playlist_entries(...)` and `expand_source_urls(...)`.
  - Run expansion before metadata lookup in `resolve_batch_preview(...)`.
- Modify: `app/routes/pages.py`
  - Import `expand_playlist_entries` and `extract_flat_info` without removing `parse_source_urls`.
  - Pass an `expand_playlist` callback into `resolve_batch_preview(...)`.
- Modify: `app/templates/partials/batch_result.html`
  - Render a cap notice when `result.truncated_count` is non-zero.
- Modify: `tests/unit/test_batch_preview.py`
  - Cover flat playlist expansion, dedupe/cap behavior, expansion failure fallback, and resolve-time child lookup.
- Modify: `tests/integration/test_pages.py`
  - Cover route wiring and truncation notice rendering.

---

### Task 1: Add playlist expansion in the batch preview service

**Files:**

- Modify: `app/services/downloader.py`
- Modify: `app/services/batch_preview.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Extend the unit-test imports**

Replace the import at the top of `tests/unit/test_batch_preview.py`:

```python
from app.services.batch_preview import parse_source_urls
```

with:

```python
from app.services.batch_preview import (
    expand_playlist_entries,
    expand_source_urls,
    parse_source_urls,
    resolve_batch_preview,
)
```

- [ ] **Step 2: Add failing playlist expansion tests**

Append to `tests/unit/test_batch_preview.py`:

```python
def test_expand_playlist_entries_returns_entry_urls_from_flat_playlist() -> None:
    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        assert proxy is None
        assert cookies_file is None
        if url == "https://example.com/list":
            return {
                "entries": [
                    {"url": "https://example.com/watch?v=1"},
                    {"webpage_url": "https://example.com/watch?v=2"},
                    {"url": "not-a-full-url"},
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


def test_expand_source_urls_dedupes_and_caps_after_playlist_expansion() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [f"https://example.com/watch?v={index}" for index in range(60)]
        return [url]

    urls, truncated_count = expand_source_urls(
        ["https://example.com/list", "https://example.com/watch?v=1", "https://example.com/after"],
        expand_playlist=fake_expand,
        limit=50,
    )

    assert len(urls) == 50
    assert urls[0] == "https://example.com/watch?v=0"
    assert urls[-1] == "https://example.com/watch?v=49"
    assert truncated_count == 11


def test_expand_source_urls_falls_back_to_source_when_expansion_fails() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/bad-list":
            raise RuntimeError("HTTP Error 403: Forbidden")
        return [url]

    urls, truncated_count = expand_source_urls(
        ["https://example.com/bad-list"],
        expand_playlist=fake_expand,
    )

    assert urls == ["https://example.com/bad-list"]
    assert truncated_count == 0


def test_resolve_batch_preview_expands_playlist_before_metadata_lookup() -> None:
    looked_up: list[str] = []

    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return ["https://example.com/watch?v=1", "https://example.com/watch?v=2"]
        return [url]

    def fake_extract(
        url: str,
        *,
        proxy: str | None = None,
        cookies_file: str | None = None,
    ) -> dict:
        looked_up.append(url)
        return {
            "title": f"title for {url}",
            "uploader": "Uploader",
            "duration": 12,
            "thumbnail": "https://example.com/thumb.jpg",
        }

    result = resolve_batch_preview(
        "https://example.com/list",
        extract_info=fake_extract,
        expand_playlist=fake_expand,
    )

    assert looked_up == ["https://example.com/watch?v=1", "https://example.com/watch?v=2"]
    assert [item.source_url for item in result.items] == looked_up
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert result.truncated_count == 0
```

- [ ] **Step 3: Run the new unit tests and confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_expand_playlist_entries_returns_entry_urls_from_flat_playlist tests/unit/test_batch_preview.py::test_expand_source_urls_dedupes_and_caps_after_playlist_expansion tests/unit/test_batch_preview.py::test_expand_source_urls_falls_back_to_source_when_expansion_fails tests/unit/test_batch_preview.py::test_resolve_batch_preview_expands_playlist_before_metadata_lookup -v
```

Expected: FAIL because `expand_playlist_entries`, `expand_source_urls`, and `truncated_count` do not exist yet.

- [ ] **Step 4: Add the flat yt-dlp helper**

In `app/services/downloader.py`, add this function immediately after `extract_info(...)`:

```python
def extract_flat_info(
    url: str,
    *,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    """Return yt-dlp metadata with playlist entries flattened."""
    import yt_dlp  # local import to keep module import cheap

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

- [ ] **Step 5: Update `BatchPreviewResult`**

In `app/services/batch_preview.py`, replace:

```python
@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int
```

with:

```python
@dataclass(frozen=True)
class BatchPreviewResult:
    items: list[BatchPreviewItem]
    valid_count: int
    invalid_count: int
    truncated_count: int = 0
```

- [ ] **Step 6: Add expansion helpers**

In `app/services/batch_preview.py`, add this code after `parse_source_urls(...)`:

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
        for key in ("webpage_url", "url"):
            entry_url = entry.get(key)
            if isinstance(entry_url, str) and entry_url.startswith("http"):
                urls.append(entry_url)
                break
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
        try:
            resolved_urls = expand_playlist(source_url)
        except Exception:  # noqa: BLE001 - fallback lets metadata lookup render the friendly error
            resolved_urls = [source_url]

        for resolved_url in resolved_urls:
            if resolved_url in seen:
                continue
            seen.add(resolved_url)
            if len(expanded) >= limit:
                truncated_count += 1
                continue
            expanded.append(resolved_url)

    return expanded, truncated_count
```

- [ ] **Step 7: Expand sources before metadata lookup**

In `app/services/batch_preview.py`, replace the `resolve_batch_preview(...)` function with:

```python
def resolve_batch_preview(
    raw: str,
    *,
    extract_info: Callable[..., dict],
    expand_playlist: Callable[[str], list[str]] | None = None,
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    items: list[BatchPreviewItem] = []
    source_urls = parse_source_urls(raw)
    expanded_urls, truncated_count = expand_source_urls(
        source_urls,
        expand_playlist=expand_playlist or (lambda url: [url]),
    )

    for url in expanded_urls:
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

        if info.get("_type") == "playlist" or isinstance(info.get("entries"), list):
            items.append(
                BatchPreviewItem(
                    source_url=url,
                    status="error",
                    title=None,
                    uploader=None,
                    duration=None,
                    thumbnail=None,
                    error_code="unsupported_playlist",
                    error_message="Playlist previews are not supported yet.",
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
        truncated_count=truncated_count,
    )
```

- [ ] **Step 8: Run the batch preview unit tests**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit the service changes**

Run:

```bash
git add app/services/downloader.py app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: expand playlists in batch preview service"
```

---

### Task 2: Wire playlist expansion into the route and truncation UI

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Add a failing route wiring test**

Append to `tests/integration/test_pages.py`:

```python
def test_batch_lookup_route_passes_playlist_expander(monkeypatch) -> None:
    from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

    def fake_expand_playlist_entries(url: str, **kwargs) -> list[str]:
        assert url == "https://example.com/list"
        assert kwargs["extract_info"] is fake_extract_flat_info
        return ["https://example.com/watch?v=1"]

    def fake_extract_flat_info(url: str, **_kwargs) -> dict:
        return {"entries": [{"url": "https://example.com/watch?v=1"}]}

    def fake_resolve_batch_preview(raw: str, **kwargs):
        assert raw == "https://example.com/list"
        assert kwargs["expand_playlist"]("https://example.com/list") == [
            "https://example.com/watch?v=1"
        ]
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
        )

    monkeypatch.setattr(
        "app.routes.pages.expand_playlist_entries",
        fake_expand_playlist_entries,
        raising=False,
    )
    monkeypatch.setattr(
        "app.routes.pages.extract_flat_info",
        fake_extract_flat_info,
        raising=False,
    )
    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/list"})

    assert response.status_code == 200
    assert "Episode 1" in response.text
```

- [ ] **Step 2: Add a failing truncation notice test**

Append to `tests/integration/test_pages.py`:

```python
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

- [ ] **Step 3: Run the new route/template tests and confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_route_passes_playlist_expander tests/integration/test_pages.py::test_batch_result_renders_truncation_notice -v
```

Expected: FAIL. The first test fails because the route does not pass `expand_playlist`; the second fails because the template does not render `truncated_count` yet.

- [ ] **Step 4: Update imports in `app/routes/pages.py`**

Replace:

```python
from app.services.batch_preview import parse_source_urls, resolve_batch_preview
```

with:

```python
from app.services.batch_preview import (
    expand_playlist_entries,
    parse_source_urls,
    resolve_batch_preview,
)
```

Replace:

```python
from app.services.downloader import (
    build_stream_picker_payload,
    extract_info,
    normalize_formats,
)
```

with:

```python
from app.services.downloader import (
    build_stream_picker_payload,
    extract_flat_info,
    extract_info,
    normalize_formats,
)
```

- [ ] **Step 5: Pass the playlist expander from `info_batch_form(...)`**

In `app/routes/pages.py`, replace the body of `info_batch_form(...)` with:

```python
    runtime = resolve_runtime_settings(session)
    proxy_url = runtime.proxy_url if proxy else None
    cookies_file = str(runtime.cookies_path) if cookies and runtime.cookies_path else None
    result = resolve_batch_preview(
        sources,
        extract_info=extract_info,
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=proxy_url,
            cookies_file=cookies_file,
        ),
        proxy=proxy_url,
        cookies_file=cookies_file,
    )
    return templates.TemplateResponse(
        request,
        "partials/batch_result.html",
        {"result": result},
    )
```

- [ ] **Step 6: Render the truncation notice**

In `app/templates/partials/batch_result.html`, replace the opening section:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} ready / {{ result.invalid_count }} failed</p>
</section>
```

with:

```html
<section class="support-card">
  <h2>Batch preview</h2>
  <p>{{ result.valid_count }} ready / {{ result.invalid_count }} failed</p>
  {% if result.truncated_count %}
  <p>
    Skipped {{ result.truncated_count }} item(s) because the batch limit is 50.
  </p>
  {% endif %}
</section>
```

- [ ] **Step 7: Run the route/template tests**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_route_passes_playlist_expander tests/integration/test_pages.py::test_batch_result_renders_truncation_notice -v
```

Expected: PASS.

- [ ] **Step 8: Run existing batch route regressions**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item -v
```

Expected: PASS.

- [ ] **Step 9: Commit the route and template changes**

Run:

```bash
git add app/routes/pages.py app/templates/partials/batch_result.html tests/integration/test_pages.py
git commit -m "feat: preview playlist entries in batch flow"
```

---

### Task 3: Final focused verification

**Files:**

- No planned code changes.

- [ ] **Step 1: Run all batch preview tests**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_batch_lookup_route_passes_playlist_expander tests/integration/test_pages.py::test_batch_result_renders_truncation_notice tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item -v
```

Expected: PASS.

- [ ] **Step 2: Run queue/worker regressions**

Run:

```bash
uv run pytest tests/unit/test_queue_claim.py tests/integration/test_worker_pool.py tests/integration/test_partials.py -v
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check app tests
```

Expected: `All checks passed!`

If any command fails, stop and fix the task that introduced the regression before continuing.
