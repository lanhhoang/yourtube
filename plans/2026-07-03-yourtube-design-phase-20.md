# YourTube Implementation Plan — Phase 20: Add exact format selection to batch preview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each ready batch preview card the same video/audio stream selection capability as the existing single-item lookup, and make enqueue-all preserve those selected stream ids.

**Architecture:** First extract the current single-item stream picker into a shared partial and prove the single-item flow still works through that shared markup. Then embed the shared picker in each ready batch card under a collapsed “Formats” section, and bind per-card selected stream ids into both the per-item enqueue form and the batch enqueue-all form.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Alpine.js, pytest, HTMX

---

## Background for the worker

- The single-item lookup in [info_result.html](/Users/lanh/Developer/video-downloaders/yourtube/app/templates/partials/info_result.html:1) already renders the full picker inline.
- Batch preview currently queues items with default format selection only.
- This phase is the highest-complexity slice because it introduces shared Alpine state and batch form wiring.

---

### Task 1: Extract the shared stream picker and keep the single-item flow passing

**Files:**

- Create: `app/templates/partials/stream_picker_form.html`
- Modify: `app/templates/partials/info_result.html`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing single-item picker regression test**

Add to `tests/integration/test_pages.py`:

```python
def test_info_lookup_fragment_still_renders_stream_picker_markup_after_extraction(monkeypatch) -> None:
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
            ],
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
```

- [ ] **Step 2: Run the single-item regression test**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_still_renders_stream_picker_markup_after_extraction -v
```

Expected: PASS before refactor, then PASS again after the extraction.

- [ ] **Step 3: Extract the shared picker partial**

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
      streamPickerOpen: true,
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

- [ ] **Step 4: Run the single-item regression tests**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_still_renders_stream_picker_markup_after_extraction tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the shared picker extraction**

Run:

```bash
git add app/templates/partials/stream_picker_form.html app/templates/partials/info_result.html tests/integration/test_pages.py
git commit -m "refactor: extract shared stream picker partial"
```

---

### Task 2: Add collapsed per-item batch pickers and picker-aware enqueue-all

**Files:**

- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing batch picker tests**

Add to `tests/integration/test_pages.py`:

```python
def test_batch_lookup_fragment_renders_collapsed_format_picker(monkeypatch) -> None:
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
                        "video_streams": [
                            {"format_id": "137", "resolution": "1080p", "ext": "mp4", "vcodec": "avc1"}
                        ],
                        "audio_streams": [
                            {"format_id": "140", "abr": 128.0, "audio_channels": 2, "ext": "m4a"}
                        ],
                        "has_muxed_streams": False,
                        "expected_container_by_pair": {"137|140": "mp4", "|": "unknown"},
                    },
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
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert "Formats" in response.text
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert 'form="batch-enqueue-form"' in response.text
```

- [ ] **Step 2: Run the batch picker test to confirm it fails**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker -v
```

Expected: FAIL because the batch card does not include the shared picker yet.

- [ ] **Step 3: Embed the shared picker in each ready batch card**

Replace the ready branch in `app/templates/partials/batch_preview_card.html` with:

```html
{% if item.status == "ready" %}
<article
  class="media-card"
  x-data="streamPicker({{ item.picker_payload|tojson }})"
  x-init="streamPickerOpen = false"
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

    <button
      type="button"
      class="advanced-toggle"
      @click="streamPickerOpen = !streamPickerOpen"
      :aria-expanded="streamPickerOpen.toString()"
    >
      Formats
    </button>

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
```

Update the metadata branch in `downloads_batch_form(...)` so it also reads:

```python
video_ids = _form_values(form, "video_format_id")
audio_ids = _form_values(form, "audio_format_id")
output_templates = _form_values(form, "output_template")
audio_bitrates = _form_values(form, "audio_bitrate")
```

and passes them into `DownloadCreate(...)`:

```python
video_format_id=video_ids[index] or None,
audio_format_id=audio_ids[index] or None,
output_template=output_templates[index] or None,
audio_bitrate=audio_bitrates[index] or None,
```

- [ ] **Step 4: Run the batch picker tests and route regression**

Run:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit the batch picker support**

Run:

```bash
git add app/templates/partials/batch_preview_card.html app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: add exact format selection to batch preview"
```

---

### Task 3: Run focused regression coverage

**Files:**

- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Run the full batch page regression suite**

Run:

```bash
uv run pytest tests/unit/test_batch_preview.py tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup tests/integration/test_pages.py::test_info_lookup_fragment_still_renders_stream_picker_markup_after_extraction tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_item -v
```

Expected: PASS.

- [ ] **Step 2: Run worker and partial regressions**

Run:

```bash
uv run pytest tests/integration/test_partials.py tests/unit/test_library.py tests/integration/test_worker_pool.py -v
```

Expected: PASS, proving picker-selected batch rows still fit the queue, worker, and library behavior.

- [ ] **Step 3: Commit any test-only regression fix**

If a small fix is needed, commit it with:

```bash
git add <exact files touched>
git commit -m "test: cover exact-format batch preview regressions"
```

If no fix is needed, skip this step.
