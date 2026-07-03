# Batch Preview Playlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch preview workflow on the home page that accepts multiple URLs or playlist sources, resolves up to 50 unique items, shows stacked preview cards with collapsed full stream pickers, and lets the user enqueue one item or all valid items.

**Architecture:** Keep the existing queue, worker, library, and file-download flow unchanged. Add one small batch-resolution service that parses source text, expands playlist entries through yt-dlp, resolves per-item metadata using the existing downloader helpers, and returns render-ready preview records. Reuse the current stream picker behavior by extracting the picker markup into a shared template partial that both the single-item and batch-item cards include.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Alpine.js, SQLAlchemy 2.x, pytest, HTMX, yt-dlp

---

## File Structure

- Create: `app/services/batch_preview.py`
  Purpose: Parse multiline source input, dedupe exact URLs, expand playlist-like sources, cap results at 50, and resolve per-item preview state with friendly errors.
- Create: `app/templates/partials/batch_result.html`
  Purpose: Render batch-level notices plus the stacked list of preview cards and the “Enqueue all valid” form.
- Create: `app/templates/partials/batch_preview_card.html`
  Purpose: Render one preview card, either valid-with-picker or invalid-with-error.
- Create: `app/templates/partials/stream_picker_form.html`
  Purpose: Shared stream-picker markup and Alpine state used by both the single-item and batch-item forms.
- Create: `tests/unit/test_batch_preview.py`
  Purpose: Lock down parsing, dedupe, playlist expansion, cap behavior, and per-item preview/error shaping.
- Modify: `app/routes/pages.py`
  Purpose: Add the batch preview route and batch enqueue-all route while preserving the existing single-item enqueue route.
- Modify: `app/templates/pages/home.html`
  Purpose: Replace the single URL input with a multiline source textarea and point it at the batch preview route.
- Modify: `app/templates/partials/info_result.html`
  Purpose: Replace inline stream-picker markup with the shared partial.
- Modify: `tests/integration/test_pages.py`
  Purpose: Cover the new home form, batch preview HTML, and batch enqueue-all behavior.

---

### Task 1: Build the batch resolution service

**Files:**

- Create: `app/services/batch_preview.py`
- Test: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_batch_preview.py` with:

```python
from __future__ import annotations

from app.services.batch_preview import (
    BatchPreviewError,
    BatchPreviewItem,
    BatchPreviewResult,
    expand_source_urls,
    parse_source_urls,
    resolve_batch_preview,
)


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


def test_expand_source_urls_flattens_playlist_entries_and_caps_at_50() -> None:
    def fake_expand(url: str) -> list[str]:
        if url == "https://example.com/list":
            return [f"https://example.com/watch?v={index}" for index in range(60)]
        return [url]

    result = expand_source_urls(
        [
            "https://example.com/list",
            "https://example.com/after",
        ],
        expand_playlist=fake_expand,
        limit=50,
    )

    assert len(result.urls) == 50
    assert result.truncated_count == 11
    assert result.urls[0] == "https://example.com/watch?v=0"
    assert result.urls[-1] == "https://example.com/watch?v=49"


def test_resolve_batch_preview_marks_lookup_failures_without_stopping_batch() -> None:
    def fake_expand(url: str) -> list[str]:
        return [url]

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
                    "format_id": "137",
                    "ext": "mp4",
                    "container": "mp4_dash",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "height": 1080,
                    "resolution": "1080p",
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "container": "m4a_dash",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "audio_channels": 2,
                },
            ],
        }

    result = resolve_batch_preview(
        "https://example.com/good\nhttps://example.com/bad",
        expand_playlist=fake_expand,
        extract_info=fake_extract,
    )

    assert isinstance(result, BatchPreviewResult)
    assert result.total_sources == 2
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.items[0].status == "ready"
    assert result.items[0].picker_payload["video_streams"][0]["format_id"] == "137"
    assert result.items[1].status == "error"
    assert result.items[1].error_code == "http_forbidden"
```

- [ ] **Step 2: Run the new unit tests and confirm they fail**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.batch_preview'`.

- [ ] **Step 3: Write the minimal batch service**

Create `app/services/batch_preview.py` with:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.downloader import build_stream_picker_payload, normalize_formats
from app.services.error_mapper import friendly_ytdlp_error


@dataclass(frozen=True)
class BatchPreviewError:
    code: str
    message: str


@dataclass(frozen=True)
class ExpandedSources:
    urls: list[str]
    truncated_count: int


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
    total_sources: int
    expanded_sources: int
    valid_count: int
    invalid_count: int
    truncated_count: int


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


def expand_source_urls(
    urls: list[str],
    *,
    expand_playlist: Callable[[str], list[str]],
    limit: int = 50,
) -> ExpandedSources:
    seen: set[str] = set()
    expanded: list[str] = []
    skipped = 0
    for source_url in urls:
        for resolved_url in expand_playlist(source_url):
            if resolved_url in seen:
                continue
            seen.add(resolved_url)
            if len(expanded) >= limit:
                skipped += 1
                continue
            expanded.append(resolved_url)
    return ExpandedSources(urls=expanded, truncated_count=skipped)


def resolve_batch_preview(
    raw: str,
    *,
    expand_playlist: Callable[[str], list[str]],
    extract_info: Callable[..., dict],
    proxy: str | None = None,
    cookies_file: str | None = None,
) -> BatchPreviewResult:
    parsed_urls = parse_source_urls(raw)
    expanded = expand_source_urls(parsed_urls, expand_playlist=expand_playlist)
    items: list[BatchPreviewItem] = []

    for url in expanded.urls:
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

        formats = normalize_formats(info)
        items.append(
            BatchPreviewItem(
                source_url=url,
                status="ready",
                title=info.get("title"),
                uploader=info.get("uploader"),
                duration=info.get("duration"),
                thumbnail=info.get("thumbnail"),
                picker_payload=build_stream_picker_payload(formats),
                error_code=None,
                error_message=None,
            )
        )

    valid_count = sum(1 for item in items if item.status == "ready")
    invalid_count = len(items) - valid_count
    return BatchPreviewResult(
        items=items,
        total_sources=len(parsed_urls),
        expanded_sources=len(expanded.urls),
        valid_count=valid_count,
        invalid_count=invalid_count,
        truncated_count=expanded.truncated_count,
    )
```

- [ ] **Step 4: Run the unit tests and confirm they pass**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS for all four tests.

- [ ] **Step 5: Commit the service foundation**

Run:

```bash
git add app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: add batch preview resolution service"
```

---

### Task 2: Add playlist expansion to the batch service

**Files:**

- Modify: `app/services/batch_preview.py`
- Modify: `app/services/downloader.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Add a failing unit test for yt-dlp playlist expansion**

Append to `tests/unit/test_batch_preview.py`:

```python
from app.services.batch_preview import expand_playlist_entries


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
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_expand_playlist_entries_returns_entry_urls_from_flat_playlist -v
```

Expected: FAIL with `ImportError` for `expand_playlist_entries`.

- [ ] **Step 3: Implement playlist expansion with flat extraction**

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
```

Also update `resolve_batch_preview()` callers later to pass `expand_playlist_entries(..., extract_info=extract_flat_info, ...)`.

- [ ] **Step 4: Run the unit file and confirm all tests still pass**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS, including the new playlist test.

- [ ] **Step 5: Commit the playlist expansion helper**

Run:

```bash
git add app/services/batch_preview.py app/services/downloader.py tests/unit/test_batch_preview.py
git commit -m "feat: expand playlist sources for batch preview"
```

---

### Task 3: Rework the home page and preview partials

**Files:**

- Modify: `app/templates/pages/home.html`
- Modify: `app/templates/partials/info_result.html`
- Create: `app/templates/partials/stream_picker_form.html`
- Create: `app/templates/partials/batch_result.html`
- Create: `app/templates/partials/batch_preview_card.html`
- Modify: `app/routes/pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing page tests**

Add to `tests/integration/test_pages.py`:

```python
def test_home_page_uses_multiline_batch_lookup_form() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'id="source-input"' in response.text
    assert 'name="sources"' in response.text
    assert '<textarea' in response.text
    assert 'hx-post="/info/batch/form"' in response.text


def test_batch_lookup_fragment_renders_ready_and_error_cards(monkeypatch) -> None:
    def fake_resolve_batch_preview(raw: str, **_kwargs):
        from app.services.batch_preview import BatchPreviewItem, BatchPreviewResult

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
                        "has_muxed_streams": False,
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
            total_sources=2,
            expanded_sources=2,
            valid_count=1,
            invalid_count=1,
            truncated_count=0,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert "Good title" in response.text
    assert "403 Forbidden" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert "Enqueue all valid" in response.text
```

- [ ] **Step 2: Run the page tests and confirm they fail**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_uses_multiline_batch_lookup_form tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: FAIL because the page still has `name="url"` and `/info/batch/form` does not exist.

- [ ] **Step 3: Extract the shared stream picker partial**

Create `app/templates/partials/stream_picker_form.html` with:

```html
<input type="hidden" name="video_format_id" :value="selectedVideoId" />
<input type="hidden" name="audio_format_id" :value="selectedAudioId" />

<script>
  function streamPicker(payload) {
    return {
      videoStreams: payload.video_streams,
      audioStreams: payload.audio_streams,
      expectedContainerByPair: payload.expected_container_by_pair,
      hasMuxedStreams: payload.has_muxed_streams,
      selectedVideoId: "",
      selectedAudioId: "",
      advancedOpen: false,
      streamPickerOpen: false,
      selectVideo(formatId) {
        this.selectedVideoId =
          this.selectedVideoId === formatId ? "" : formatId;
      },
      selectAudio(formatId) {
        this.selectedAudioId =
          this.selectedAudioId === formatId ? "" : formatId;
      },
      pairKey() {
        return `${this.selectedVideoId}|${this.selectedAudioId}`;
      },
      expectedContainer() {
        return this.expectedContainerByPair[this.pairKey()] || "unknown";
      },
    };
  }
</script>

<button
  type="button"
  class="advanced-toggle"
  @click="streamPickerOpen = !streamPickerOpen"
  :aria-expanded="streamPickerOpen.toString()"
>
  Formats
</button>

<section class="stream-section" x-cloak x-show="streamPickerOpen">
  <div class="stream-section-head">
    <h3>Video Streams</h3>
    <p>
      Pick a video-only stream or leave blank for yt-dlp's default selection.
    </p>
  </div>
  <template x-if="videoStreams.length">
    <table class="stream-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Resolution</th>
          <th>Container</th>
          <th>Video Codec</th>
        </tr>
      </thead>
      <tbody>
        <template x-for="item in videoStreams" :key="item.format_id">
          <tr
            :class="{ 'is-selected': selectedVideoId === item.format_id }"
            @click="selectVideo(item.format_id)"
          >
            <td x-text="item.format_id"></td>
            <td x-text="item.resolution || '-'"></td>
            <td x-text="item.ext || '-'"></td>
            <td x-text="item.vcodec || '-'"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </template>
  <template x-if="!videoStreams.length">
    <p class="stream-empty">
      No video-only streams were exposed for this item.
    </p>
  </template>
</section>

<section class="stream-section" x-cloak x-show="streamPickerOpen">
  <div class="stream-section-head">
    <h3>Audio Streams</h3>
    <p>
      Pick an audio-only stream or leave blank for yt-dlp's default selection.
    </p>
  </div>
  <template x-if="audioStreams.length">
    <table class="stream-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Bitrate</th>
          <th>Channels</th>
          <th>Container</th>
        </tr>
      </thead>
      <tbody>
        <template x-for="item in audioStreams" :key="item.format_id">
          <tr
            :class="{ 'is-selected': selectedAudioId === item.format_id }"
            @click="selectAudio(item.format_id)"
          >
            <td x-text="item.format_id"></td>
            <td x-text="item.abr ? `${item.abr} kbps` : '-'"></td>
            <td x-text="item.audio_channels || '-'"></td>
            <td x-text="item.ext || '-'"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </template>
  <template x-if="!audioStreams.length">
    <p class="stream-empty">
      No audio-only streams were exposed for this item.
    </p>
  </template>
</section>

<p class="stream-hint">
  Expected container:
  <strong x-text="expectedContainer()"></strong>
</p>

<template x-if="hasMuxedStreams">
  <p class="stream-note">
    Default format selection remains available if you leave both tables
    unselected.
  </p>
</template>

<button
  type="button"
  class="advanced-toggle"
  @click="advancedOpen = !advancedOpen"
  :aria-expanded="advancedOpen.toString()"
>
  Advanced options
</button>

<section class="advanced-panel" x-cloak x-show="advancedOpen">
  <label><input type="checkbox" name="subtitles" /> Download subtitles</label>
  <label for="output-template">Output template</label>
  <input
    id="output-template"
    name="output_template"
    placeholder="%(title)s.%(ext)s"
  />
  <label for="audio-bitrate">Audio bitrate</label>
  <input id="audio-bitrate" name="audio_bitrate" placeholder="192K" />
</section>
```

Then replace the inline picker block in `app/templates/partials/info_result.html` with:

```html
<form
  id="enqueue-form"
  x-data="streamPicker({{ picker_payload|tojson }})"
  hx-post="/downloads/form"
  hx-target="#info-status"
  hx-swap="innerHTML"
>
  <input type="hidden" name="url" value="{{ url }}" />
  <input type="hidden" name="title" value="{{ title }}" />
  <input type="hidden" name="uploader" value="{{ uploader or '' }}" />
  <input type="hidden" name="duration" value="{{ duration or '' }}" />
  <input type="hidden" name="thumbnail" value="{{ thumbnail or '' }}" />
  {% include "partials/stream_picker_form.html" %}
  <button type="submit">Add to queue</button>
</form>
```

- [ ] **Step 4: Add the batch preview route and templates**

In `app/routes/pages.py`, add imports:

```python
from app.services.batch_preview import resolve_batch_preview, expand_playlist_entries
from app.services.downloader import extract_flat_info
```

Add the route:

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
        expand_playlist=lambda url: expand_playlist_entries(
            url,
            extract_info=extract_flat_info,
            proxy=runtime.proxy_url if proxy else None,
            cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
        ),
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
<article
  class="media-card"
  x-data="streamPicker({{ item.picker_payload|tojson }})"
>
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
      hx-target="#info-status"
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
      {% include "partials/stream_picker_form.html" %}
      <button type="submit">Add to queue</button>
    </form>
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="url"
      value="{{ item.source_url }}"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="title"
      value="{{ item.title or '' }}"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="uploader"
      value="{{ item.uploader or '' }}"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="duration"
      value="{{ item.duration or '' }}"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="thumbnail"
      value="{{ item.thumbnail or '' }}"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="video_format_id"
      :value="selectedVideoId"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="audio_format_id"
      :value="selectedAudioId"
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="output_template"
      value=""
    />
    <input
      form="batch-enqueue-form"
      type="hidden"
      name="audio_bitrate"
      value=""
    />
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
  {% if result.truncated_count %}
  <p>
    Skipped {{ result.truncated_count }} item(s) because the batch limit is 50.
  </p>
  {% endif %}
</section>

<form
  id="batch-enqueue-form"
  hx-post="/downloads/batch/form"
  hx-target="#info-status"
  hx-swap="innerHTML"
>
  <button type="submit">Enqueue all valid</button>
</form>

{% for item in result.items %} {% include "partials/batch_preview_card.html" %}
{% endfor %}
```

Finally, in `app/templates/pages/home.html`, replace the single input form with:

```html
<form
  id="info-form"
  class="lookup-form"
  hx-post="/info/batch/form"
  hx-target="#info-result"
  hx-swap="innerHTML"
>
  <label for="source-input">Sources</label>
  <textarea
    id="source-input"
    name="sources"
    rows="5"
    placeholder="Paste one or more URLs, or a playlist URL"
    required
  ></textarea>
  <div class="toggle-row">
    <label><input type="checkbox" name="proxy" /> Use saved proxy</label>
    <label><input type="checkbox" name="cookies" /> Use saved cookies</label>
  </div>
  <button type="submit">Preview batch</button>
</form>
```

- [ ] **Step 5: Run the page tests and confirm they pass**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_home_page_uses_multiline_batch_lookup_form tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards -v
```

Expected: PASS for both tests, with the batch preview fragment rendering `id="batch-enqueue-form"` and picker-backed hidden fields.

- [ ] **Step 6: Commit the preview UI**

Run:

```bash
git add app/routes/pages.py app/templates/pages/home.html app/templates/partials/info_result.html app/templates/partials/stream_picker_form.html app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html tests/integration/test_pages.py
git commit -m "feat: add batch preview home workflow"
```

---

### Task 4: Add enqueue-all support for valid batch items

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/schemas.py`
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
                ("video_format_id", ""),
                ("audio_format_id", ""),
                ("output_template", ""),
                ("audio_bitrate", ""),
                ("url", "https://example.com/b"),
                ("title", "Title B"),
                ("uploader", "Uploader B"),
                ("duration", "24"),
                ("thumbnail", "https://example.com/b.jpg"),
                ("video_format_id", ""),
                ("audio_format_id", ""),
                ("output_template", ""),
                ("audio_bitrate", ""),
            ],
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert all(row.status == "queued" for row in rows)
```

- [ ] **Step 2: Run the enqueue-all test and confirm it fails**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: FAIL with HTTP 404 for `/downloads/batch/form`.

- [ ] **Step 3: Add a tiny batch payload builder and route**

In `app/schemas.py`, add:

```python
class BatchDownloadCreate(BaseModel):
    items: list[DownloadCreate]
```

In `app/routes/pages.py`, add helpers:

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

Add the route:

```python
@router.post("/downloads/batch/form", response_class=HTMLResponse)
async def downloads_batch_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    form = await request.form()
    urls = _form_values(form, "url")
    titles = _form_values(form, "title")
    uploaders = _form_values(form, "uploader")
    durations = _form_values(form, "duration")
    thumbnails = _form_values(form, "thumbnail")
    video_ids = _form_values(form, "video_format_id")
    audio_ids = _form_values(form, "audio_format_id")
    output_templates = _form_values(form, "output_template")
    audio_bitrates = _form_values(form, "audio_bitrate")

    for index, url in enumerate(urls):
        payload = DownloadCreate(
            url=url,
            title=titles[index] or None,
            uploader=uploaders[index] or None,
            duration=int(durations[index]) if durations[index] else None,
            thumbnail=thumbnails[index] or None,
            video_format_id=video_ids[index] or None,
            audio_format_id=audio_ids[index] or None,
            output_template=output_templates[index] or None,
            audio_bitrate=audio_bitrates[index] or None,
            subtitles=False,
        )
        enqueue_download(session, payload)

    return templates.TemplateResponse(
        request,
        "partials/status_message.html",
        {"message": f"Added {len(urls)} items to queue.", "target_id": "info-status"},
    )
```

- [ ] **Step 4: Run the enqueue-all test and a focused regression for single-item enqueue**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item tests/integration/test_pages.py::test_info_lookup_fragment_renders_editorial_media_card -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit enqueue-all support**

Run:

```bash
git add app/routes/pages.py app/schemas.py tests/integration/test_pages.py
git commit -m "feat: add batch enqueue-all route"
```

---

### Task 5: Run the narrow regression suite and finish

**Files:**

- Modify: `plans/2026-07-03-batch-preview-playlist-implementation.md`

- [ ] **Step 1: Run the targeted suite**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py -v
```

Expected: PASS for the new unit and integration coverage.

- [ ] **Step 2: Run existing queue/library regressions that the batch flow depends on**

Run:

```bash
uv run pytest tests/integration/test_partials.py tests/unit/test_library.py tests/integration/test_worker_pool.py -v
```

Expected: PASS, proving the new batch flow did not disturb queue rows, library behavior, or worker completion logic.

- [ ] **Step 3: Mark the plan status in git**

Run:

```bash
git status --short
```

Expected: clean working tree, or only unrelated user changes outside this feature.

- [ ] **Step 4: Commit any last test-only fixes**

If Task 5 exposed a real regression, fix it with the smallest possible diff and commit it with:

```bash
git add <exact files touched>
git commit -m "test: cover batch preview regressions"
```

If no fixes were needed, skip this step.

---

## Self-Review

- Spec coverage:
  - Multi-URL paste, exact dedupe, playlist expansion, and 50-item cap are covered in Task 1 and Task 2.
  - Stacked preview cards with per-item success/error states are covered in Task 3.
  - Collapsed full stream picker reuse is covered in Task 3.
  - Single-item enqueue reuse plus batch enqueue-all are covered in Task 3 and Task 4.
  - No queue/worker/library changes beyond regression coverage are covered in Task 4 and Task 5.
- Placeholder scan:
  - No `TODO`, `TBD`, or “appropriate handling” filler remains.
  - Every code-changing step includes concrete code or concrete markup.
- Type consistency:
  - `BatchPreviewItem`, `BatchPreviewResult`, `ExpandedSources`, `parse_source_urls`, `expand_source_urls`, `expand_playlist_entries`, and `resolve_batch_preview` use the same names throughout the plan.
