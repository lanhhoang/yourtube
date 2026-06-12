# Phase 9: Alpine Stream Table Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current select-based format picker with table-based `Video Streams` and `Audio Streams` sections, using Alpine.js for local UI state while keeping HTMX request flow intact.

**Architecture:** The home page remains server-rendered and HTMX-driven. Alpine.js is introduced only inside the lookup-result fragment and owns transient state: selected rows, current expected-container label, and advanced-section visibility. No queue, library, or settings routes move to client-side rendering.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, CSS, pytest, uv

**Alpine.js feature use cases:**

```
dropdowns
modals
tooltips
popovers
accordions
expand/collapse sections
mobile menus
sidebar toggle

toggle flags (open, active)
selected item index
stepper / wizard step
tab selection
simple counters
boolean UI flags

input binding (x-model)
live preview
character counters
enable/disable submit
loading states
show/hide password
inline hints
conditional fields
multi-step forms (UI only)

loading indicators (with HTMX)
disable buttons during request
optimistic UI hints (light)
reset form after submit
UI reactions to server response

click handling
keyboard events
escape to close modal
click outside detection
focus management
scroll handling
refs (x-ref usage)

fade in/out
slide animations
modal transitions
accordion transitions

client-side filtering (small datasets)
client-side sorting (small datasets)
search-as-you-type (local only)
toggle views (grid/list)

dark mode toggle
theme switcher
copy to clipboard
toast notifications (simple)
progress indicators
timers
countdowns

dropdown components
modal components
tabs components
alert/banner components

enhancing server-rendered HTML
attaching behavior to HTMX partials
sprinkling JS into templates

Alpine.store() for small shared state
reusable x-data factories
```

---

## File Structure

```
yourtube/
├── app/
│   ├── templates/
│   │   ├── index.html
│   │   ├── pages/home.html
│   │   └── partials/info_result.html
│   └── static/
│       ├── css/app.css
│       └── vendor/alpine.min.js
└── tests/
    └── integration/
        └── test_pages.py
```

Responsibilities:

- `app/templates/index.html` loads Alpine.js after HTMX.
- `app/templates/partials/info_result.html` becomes the Alpine state root and renders stream tables plus hidden form fields.
- `app/static/css/app.css` owns table, selected-row, advanced-panel, and hint styling.

### Task 1: Install Alpine.js as a local vendor dependency

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

Expected: FAIL because the asset does not exist and the base template does not load it yet.

- [ ] **Step 3: Add the vendor asset and load it in the base template**

```html
<script defer src="{{ url_for('static', path='vendor/htmx.min.js') }}"></script>
<script
  defer
  src="{{ url_for('static', path='vendor/alpine.min.js') }}"
></script>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/integration/test_pages.py::test_pages_load_local_alpine_asset -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/vendor/alpine.min.js app/templates/index.html tests/integration/test_pages.py
git commit -m "feat: add local alpine runtime"
```

### Task 2: Replace the select picker with stream tables and hidden fields

**Files:**

- Modify: `app/templates/partials/info_result.html`
- Modify: `app/static/css/app.css`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing table-picker test**

```python
def test_info_lookup_fragment_renders_video_and_audio_stream_tables(monkeypatch) -> None:
    def fake_extract_info(url: str, **_kwargs):
        return {
            "url": url,
            "title": "Example title",
            "uploader": "Uploader",
            "duration": 123,
            "formats": [
                {"format_id": "401", "ext": "mp4", "container": "mp4_dash", "vcodec": "avc1", "acodec": "none", "height": 2160},
                {"format_id": "140", "ext": "m4a", "container": "m4a_dash", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128.0, "audio_channels": 2},
            ],
            "captions": {},
        }

    monkeypatch.setattr("app.routes.pages.extract_info", fake_extract_info)

    with TestClient(app) as client:
        response = client.post("/info/form", data={"url": "https://example.com/watch?v=1"})

    assert response.status_code == 200
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert 'name="video_format_id"' in response.text
    assert 'name="audio_format_id"' in response.text
    assert 'x-data="streamPicker(' in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_video_and_audio_stream_tables -v`

Expected: FAIL because the fragment still renders `<select>` controls and no Alpine state root.

- [ ] **Step 3: Rewrite the fragment around Alpine state and stream tables**

```html
<form
  id="enqueue-form"
  x-data="streamPicker({{ picker_payload|tojson|safe }})"
  hx-post="/downloads/form"
  hx-target="#info-status"
  hx-swap="innerHTML"
>
  <input type="hidden" name="url" value="{{ url }}" />
  <input type="hidden" name="video_format_id" :value="selectedVideoId" />
  <input type="hidden" name="audio_format_id" :value="selectedAudioId" />

  <section id="video-streams" class="stream-section">
    <h3>Video Streams</h3>
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
            <td x-text="item.ext"></td>
            <td x-text="item.vcodec || '-'"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </section>
</form>
```

- [ ] **Step 4: Add the collapsed advanced panel and container hint styles**

```css
.stream-table {
  width: 100%;
  border-collapse: collapse;
}

.stream-table tr.is-selected {
  background: rgba(226, 90, 44, 0.12);
}

.advanced-panel[hidden] {
  display: none;
}
```

- [ ] **Step 5: Run the page tests to verify they pass**

Run: `uv run pytest tests/integration/test_pages.py -v`

Expected: PASS for stream-table rendering and Alpine markup.

- [ ] **Step 6: Commit**

```bash
git add app/templates/partials/info_result.html app/static/css/app.css tests/integration/test_pages.py
git commit -m "feat: replace format selects with alpine-powered stream tables"
```
