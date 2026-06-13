# Phase 9: Alpine Stream Table Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current select-based format picker with explicit video/audio stream tables while preserving the existing HTMX lookup and enqueue flow.

**Architecture:** Keep the home page server-rendered. Add Alpine.js only to the lookup-result fragment for row selection, advanced-panel toggling, and expected-container display. Introduce one narrow backend helper that shapes normalized `FormatInfo` rows into a browser payload so container inference stays canonical in Python instead of being reimplemented in JavaScript.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, CSS, pytest, uv

---

## File Structure

```
yourtube/
├── app/
│   ├── routes/
│   │   └── pages.py
│   ├── services/
│   │   └── downloader.py
│   ├── templates/
│   │   ├── index.html
│   │   └── partials/
│   │       └── info_result.html
│   └── static/
│       ├── css/app.css
│       └── vendor/
│           ├── htmx.min.js
│           └── alpine.min.js
└── tests/
    ├── integration/
    │   └── test_pages.py
    └── unit/
        └── test_downloader_format.py
```

Responsibilities:

- `app/services/downloader.py` keeps stream grouping and expected-container derivation close to the existing format helpers.
- `app/routes/pages.py` passes both `formats` and the precomputed `picker_payload` into the lookup fragment.
- `app/templates/index.html` loads Alpine.js globally after HTMX so HTMX-swapped fragments can use Alpine directives immediately.
- `app/templates/partials/info_result.html` remains the enqueue form surface and preserves all existing metadata fields required by `/downloads/form`.
- `app/static/css/app.css` adds table, selected-row, empty-state, and advanced-panel styling without changing the broader editorial shell.

## Design Rules

- Keep `POST /info/form` and `POST /downloads/form` unchanged at the route-contract level.
- Preserve hidden fields for `url`, `title`, `uploader`, `duration`, and `thumbnail`.
- Show only `stream_kind == "video"` rows in the video table and only `stream_kind == "audio"` rows in the audio table.
- Do not render `muxed` rows as selectable table rows in v1. Instead, surface a short note that leaving both selections blank lets yt-dlp choose the default combined/best format.
- Keep the browser defaults blank: no video or audio row is preselected.
- Keep expected-container rules in Python and serialize the results to Alpine.

### Task 1: Load Alpine.js as a local asset

**Files:**
- Create: `app/static/vendor/alpine.min.js`
- Modify: `app/templates/index.html`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing Alpine asset test**

```python
def test_pages_load_local_alpine_asset() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        alpine = client.get("/static/vendor/alpine.min.js")

    assert response.status_code == 200
    assert "/static/vendor/alpine.min.js" in response.text
    assert alpine.status_code == 200
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_pages_load_local_alpine_asset -v`

Expected: FAIL because the asset does not exist and `index.html` only loads HTMX.

- [ ] **Step 3: Add the vendor asset and load it in the base template**

```html
<script defer src="{{ url_for('static', path='vendor/htmx.min.js') }}"></script>
<script defer src="{{ url_for('static', path='vendor/alpine.min.js') }}"></script>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_pages.py::test_pages_load_local_alpine_asset -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/vendor/alpine.min.js app/templates/index.html tests/integration/test_pages.py
git commit -m "feat: add local alpine runtime"
```

### Task 2: Add a backend helper for the stream-picker payload

**Files:**
- Modify: `app/services/downloader.py`
- Test: `tests/unit/test_downloader_format.py`

- [ ] **Step 1: Write the failing picker-payload unit tests**

```python
def test_build_stream_picker_payload_groups_video_and_audio_rows() -> None:
    formats = [
        FormatInfo(
            format_id="401",
            ext="mp4",
            stream_kind="video",
            height=2160,
            resolution="2160p",
            vcodec="av01.0.08M.08",
            acodec="none",
            container="mp4_dash",
        ),
        FormatInfo(
            format_id="140",
            ext="m4a",
            stream_kind="audio",
            abr=128.0,
            audio_channels=2,
            vcodec="none",
            acodec="mp4a.40.2",
            container="m4a_dash",
        ),
        FormatInfo(
            format_id="18",
            ext="mp4",
            stream_kind="muxed",
            resolution="360p",
            vcodec="avc1.42001E",
            acodec="mp4a.40.2",
            container="mp4",
        ),
    ]

    payload = build_stream_picker_payload(formats)

    assert [row["format_id"] for row in payload["video_streams"]] == ["401"]
    assert [row["format_id"] for row in payload["audio_streams"]] == ["140"]
    assert payload["has_muxed_streams"] is True


def test_build_stream_picker_payload_serializes_expected_container_pairs() -> None:
    formats = [
        FormatInfo(
            format_id="137",
            ext="mp4",
            stream_kind="video",
            resolution="1080p",
            vcodec="avc1.640028",
            acodec="none",
            container="mp4_dash",
        ),
        FormatInfo(
            format_id="140",
            ext="m4a",
            stream_kind="audio",
            abr=128.0,
            audio_channels=2,
            vcodec="none",
            acodec="mp4a.40.2",
            container="m4a_dash",
        ),
    ]

    payload = build_stream_picker_payload(formats)

    assert payload["expected_container_by_pair"]["|"] == "unknown"
    assert payload["expected_container_by_pair"]["137|"] == "mp4"
    assert payload["expected_container_by_pair"]["|140"] == "m4a"
    assert payload["expected_container_by_pair"]["137|140"] == "mp4"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_build_stream_picker_payload_groups_video_and_audio_rows tests/unit/test_downloader_format.py::test_build_stream_picker_payload_serializes_expected_container_pairs -v`

Expected: FAIL because `build_stream_picker_payload` does not exist yet.

- [ ] **Step 3: Add the minimal helper in `app/services/downloader.py`**

```python
def build_stream_picker_payload(formats: list[FormatInfo]) -> dict[str, object]:
    video_streams = [f for f in formats if f.stream_kind == "video"]
    audio_streams = [f for f in formats if f.stream_kind == "audio"]
    has_muxed_streams = any(f.stream_kind == "muxed" for f in formats)

    def _row(item: FormatInfo) -> dict[str, object]:
        return {
            "format_id": item.format_id,
            "ext": item.ext,
            "resolution": item.resolution,
            "height": item.height,
            "vcodec": item.vcodec,
            "acodec": item.acodec,
            "abr": item.abr,
            "audio_channels": item.audio_channels,
            "container": item.container,
        }

    expected_container_by_pair: dict[str, str] = {"|": "unknown"}
    for video in video_streams:
        expected_container_by_pair[f"{video.format_id}|"] = infer_expected_container(video, None)
    for audio in audio_streams:
        expected_container_by_pair[f"|{audio.format_id}"] = infer_expected_container(None, audio)
    for video in video_streams:
        for audio in audio_streams:
            key = f"{video.format_id}|{audio.format_id}"
            expected_container_by_pair[key] = infer_expected_container(video, audio)

    return {
        "video_streams": [_row(item) for item in video_streams],
        "audio_streams": [_row(item) for item in audio_streams],
        "has_muxed_streams": has_muxed_streams,
        "expected_container_by_pair": expected_container_by_pair,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_downloader_format.py::test_build_stream_picker_payload_groups_video_and_audio_rows tests/unit/test_downloader_format.py::test_build_stream_picker_payload_serializes_expected_container_pairs -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/downloader.py tests/unit/test_downloader_format.py
git commit -m "feat: add stream picker payload helper"
```

### Task 3: Pass the picker payload through the lookup fragment route

**Files:**
- Modify: `app/routes/pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing fragment-context test**

```python
def test_info_lookup_fragment_renders_stream_picker_markup(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {
                    "format_id": "401",
                    "ext": "mp4",
                    "container": "mp4_dash",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "height": 2160,
                    "resolution": "2160p",
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
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "container": "mp4",
                    "vcodec": "avc1.42001E",
                    "acodec": "mp4a.40.2",
                    "resolution": "360p",
                },
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert 'x-data="streamPicker(' in response.text
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert 'name="title"' in response.text
    assert 'name="uploader"' in response.text
    assert 'name="duration"' in response.text
    assert 'name="thumbnail"' in response.text
    assert "Default format selection remains available" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v`

Expected: FAIL because `/info/form` does not pass a picker payload and the fragment still renders `<select>` controls.

- [ ] **Step 3: Add the route-level payload wiring**

```python
from app.services.downloader import (
    build_stream_picker_payload,
    extract_info,
    normalize_formats,
)


@router.post("/info/form", response_class=HTMLResponse)
def info_form(
    request: Request,
    url: str = Form(...),
    proxy: str | None = Form(default=None),
    cookies: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runtime = resolve_runtime_settings(session)
    raw = extract_info(
        url,
        proxy=runtime.proxy_url if proxy else None,
        cookies_file=str(runtime.cookies_path) if cookies and runtime.cookies_path else None,
    )
    formats = normalize_formats(raw)
    return templates.TemplateResponse(
        request,
        "partials/info_result.html",
        {
            "url": url,
            "title": raw.get("title", ""),
            "uploader": raw.get("uploader"),
            "duration": raw.get("duration"),
            "thumbnail": raw.get("thumbnail"),
            "formats": formats,
            "picker_payload": build_stream_picker_payload(formats),
        },
    )
```

- [ ] **Step 4: Run the test to verify it still fails for the right reason**

Run: `uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v`

Expected: FAIL because the template has not been rewritten yet, but there should be no route exception.

- [ ] **Step 5: Commit**

```bash
git add app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: wire picker payload into info fragment"
```

### Task 4: Replace the select picker with Alpine-powered stream tables

**Files:**
- Modify: `app/templates/partials/info_result.html`
- Modify: `app/static/css/app.css`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Expand the fragment test to lock the final markup contract**

```python
def test_info_lookup_fragment_renders_stream_picker_markup(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {
                    "format_id": "401",
                    "ext": "mp4",
                    "container": "mp4_dash",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "height": 2160,
                    "resolution": "2160p",
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
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "container": "mp4",
                    "vcodec": "avc1.42001E",
                    "acodec": "mp4a.40.2",
                    "resolution": "360p",
                },
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert 'x-data="streamPicker(' in response.text
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert "Expected container" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert 'name="title"' in response.text
    assert 'name="uploader"' in response.text
    assert 'name="duration"' in response.text
    assert 'name="thumbnail"' in response.text
    assert 'name="output_template"' in response.text
    assert 'name="audio_bitrate"' in response.text
    assert 'name="subtitles"' in response.text
    assert "Default format selection remains available" in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v`

Expected: FAIL because the fragment still uses `<select>` controls and has no Alpine component.

- [ ] **Step 3: Rewrite the fragment around an inline Alpine component**

```html
<section class="media-card">
  {% if thumbnail %}
  <img src="{{ thumbnail }}" alt="" class="media-card-thumb" />
  {% endif %}
  <div class="media-card-body">
    <p class="eyebrow">Detected media</p>
    <h2>{{ title or url }}</h2>
    <dl class="meta-grid">
      <div>
        <dt>Uploader</dt>
        <dd>{{ uploader or "Unknown" }}</dd>
      </div>
      <div>
        <dt>Duration</dt>
        <dd>{{ duration or "Unknown" }}</dd>
      </div>
    </dl>

    <form
      id="enqueue-form"
      x-data="streamPicker({{ picker_payload|tojson|safe }})"
      hx-post="/downloads/form"
      hx-target="#info-status"
      hx-swap="innerHTML"
    >
      <input type="hidden" name="url" value="{{ url }}" />
      <input type="hidden" name="title" value="{{ title }}" />
      <input type="hidden" name="uploader" value="{{ uploader or '' }}" />
      <input type="hidden" name="duration" value="{{ duration or '' }}" />
      <input type="hidden" name="thumbnail" value="{{ thumbnail or '' }}" />
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
            selectVideo(formatId) {
              this.selectedVideoId = this.selectedVideoId === formatId ? "" : formatId;
            },
            selectAudio(formatId) {
              this.selectedAudioId = this.selectedAudioId === formatId ? "" : formatId;
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

      <section class="stream-section">
        <div class="stream-section-head">
          <h3>Video Streams</h3>
          <p>Pick a video-only stream or leave blank for yt-dlp's default selection.</p>
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
          <p class="stream-empty">No video-only streams were exposed for this item.</p>
        </template>
      </section>

      <section class="stream-section">
        <div class="stream-section-head">
          <h3>Audio Streams</h3>
          <p>Pick an audio-only stream or leave blank for yt-dlp's default selection.</p>
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
          <p class="stream-empty">No audio-only streams were exposed for this item.</p>
        </template>
      </section>

      <p class="stream-hint">
        Expected container:
        <strong x-text="expectedContainer()"></strong>
      </p>

      <template x-if="hasMuxedStreams">
        <p class="stream-note">
          Default format selection remains available if you leave both tables unselected.
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

      <section class="advanced-panel" x-show="advancedOpen">
        <label><input type="checkbox" name="subtitles" /> Download subtitles</label>
        <label for="output-template">Output template</label>
        <input id="output-template" name="output_template" placeholder="%(title)s.%(ext)s" />
        <label for="audio-bitrate">Audio bitrate</label>
        <input id="audio-bitrate" name="audio_bitrate" placeholder="192K" />
      </section>

      <button type="submit">Add to queue</button>
    </form>
  </div>
</section>
```

- [ ] **Step 4: Add the minimal supporting styles**

```css
.stream-section {
  display: grid;
  gap: 10px;
}

.stream-section + .stream-section {
  margin-top: 6px;
}

.stream-section-head p,
.stream-empty,
.stream-note,
.stream-hint {
  margin: 0;
  color: var(--muted);
  line-height: 1.5;
}

.stream-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.stream-table th,
.stream-table td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--line);
}

.stream-table tbody tr {
  cursor: pointer;
  background: #fff;
}

.stream-table tbody tr.is-selected {
  background: rgba(226, 90, 44, 0.12);
}

.advanced-toggle {
  background: transparent;
  color: var(--fg);
  border-color: var(--line-strong);
}

.advanced-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--card-alt);
}
```

- [ ] **Step 5: Run the page tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/partials/info_result.html app/static/css/app.css tests/integration/test_pages.py
git commit -m "feat: replace format selects with alpine-powered stream tables"
```

### Task 5: Verify the full Phase 9 slice

**Files:**
- Modify: none
- Test: `tests/unit/test_downloader_format.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Run the narrow unit and integration suite**

Run: `uv run pytest tests/unit/test_downloader_format.py tests/integration/test_pages.py -v`

Expected: PASS for Alpine asset loading, picker payload generation, and stream-table fragment rendering.

- [ ] **Step 2: Smoke-check for accidental route-contract regressions**

Run: `uv run pytest tests/integration/test_api_info.py -v`

Expected: PASS because Phase 9 adds page-facing payload shaping only and does not change the JSON API.
