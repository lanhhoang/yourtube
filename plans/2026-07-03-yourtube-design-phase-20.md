# YourTube Implementation Plan - Phase 20: Add exact format selection to batch preview

> **For agentic workers:** implement task-by-task. Keep commits small and run the listed checks before each commit.

**Goal:** Give each ready batch preview card the same video/audio stream selection capability as the existing single-item lookup, and make enqueue-all preserve the selected stream ids.

**Current baseline:** phase 19 is merged, the worktree is clean, and the focused baseline checks pass. The previous phase 20 plan was not ready because `BatchPreviewItem` does not yet carry `picker_payload`, the proposed `x-data="..."` attributes would be unsafe with JSON, the batch card replacement dropped `target_id`, and enqueue-all tests did not prove selected stream ids are saved.

**Architecture:** Reuse the existing single-item picker by extracting its markup into one shared partial. Teach batch preview items to carry a picker payload built from the same `normalize_formats()` and `build_stream_picker_payload()` helpers as `/info/form`. Render the picker collapsed inside each ready batch card. Keep per-item enqueue and enqueue-all as separate forms: per-item posts to `/downloads/form`; enqueue-all uses `form="batch-enqueue-form"` hidden inputs scoped to each card's Alpine picker state.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Alpine.js, pytest, HTMX

---

## Task 1: Extract the existing single-item stream picker

**Files:**

- Create: `app/templates/partials/stream_picker_form.html`
- Modify: `app/templates/partials/info_result.html`
- Use existing tests in `tests/integration/test_pages.py`

- [ ] **Step 1: Run the existing single-item picker regression**

```bash
uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v
```

Expected: PASS before extraction.

- [ ] **Step 2: Move the picker markup into a shared partial**

Create `app/templates/partials/stream_picker_form.html` by moving the existing hidden `video_format_id` / `audio_format_id` inputs, `streamPicker(payload)` script, stream tables, expected-container hint, muxed-stream note, and advanced-options panel out of `app/templates/partials/info_result.html`.

Add `streamPickerOpen: true` to the returned Alpine state and put `x-show="streamPickerOpen"` on the two stream sections. Leave `advancedOpen` behavior unchanged.

- [ ] **Step 3: Replace the inline single-item picker with the include**

Keep the single-quoted JSON-bearing Alpine attribute:

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

- [ ] **Step 4: Re-run the single-item regression**

```bash
uv run pytest tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup -v
```

Expected: PASS.

- [ ] **Step 5: Commit the extraction**

```bash
git add app/templates/partials/stream_picker_form.html app/templates/partials/info_result.html
git commit -m "refactor: extract shared stream picker partial"
```

---

## Task 2: Attach stream picker payloads to batch preview items

**Files:**

- Modify: `app/services/batch_preview.py`
- Modify: `tests/unit/test_batch_preview.py`

- [ ] **Step 1: Add a failing service test**

Add a test proving ready batch items expose picker payload data built from their extracted formats:

```python
def test_resolve_batch_preview_attaches_stream_picker_payload_to_ready_items() -> None:
    def fake_extract(url: str, **_kwargs) -> dict:
        return {
            "title": "Ready",
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "resolution": "1080p",
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128.0,
                    "audio_channels": 2,
                },
            ],
        }

    result = resolve_batch_preview("https://example.com/a", extract_info=fake_extract)

    payload = result.items[0].picker_payload
    assert payload["video_streams"][0]["format_id"] == "137"
    assert payload["audio_streams"][0]["format_id"] == "140"
    assert payload["expected_container_by_pair"]["137|140"] == "mp4"
```

Run it and confirm it fails:

```bash
uv run pytest tests/unit/test_batch_preview.py::test_resolve_batch_preview_attaches_stream_picker_payload_to_ready_items -v
```

- [ ] **Step 2: Add `picker_payload` to `BatchPreviewItem`**

In `app/services/batch_preview.py`:

- Import `field` from `dataclasses`.
- Import `StreamPickerPayload`, `build_stream_picker_payload`, and `normalize_formats` from `app.services.downloader`.
- Add a small `_empty_picker_payload()` default factory returning empty stream lists, `has_muxed_streams: False`, and `expected_container_by_pair: {"|": "unknown"}`.
- Add `picker_payload: StreamPickerPayload = field(default_factory=_empty_picker_payload)` after `error_message` on `BatchPreviewItem` so existing tests that construct items directly keep working.
- In the ready-item branch, build `formats = normalize_formats(info)` and pass `picker_payload=build_stream_picker_payload(formats)`.

- [ ] **Step 3: Run batch preview unit coverage**

```bash
uv run pytest tests/unit/test_batch_preview.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit the service change**

```bash
git add app/services/batch_preview.py tests/unit/test_batch_preview.py
git commit -m "feat: attach stream picker payloads to batch previews"
```

---

## Task 3: Render collapsed batch pickers and preserve selected ids

**Files:**

- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/routes/pages.py`
- Modify: `tests/integration/test_pages.py`

- [ ] **Step 1: Add failing integration tests**

Add one markup test for the collapsed picker:

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
                    error_code=None,
                    error_message=None,
                    picker_payload={
                        "video_streams": [
                            {
                                "format_id": "137",
                                "resolution": "1080p",
                                "ext": "mp4",
                                "vcodec": "avc1",
                            }
                        ],
                        "audio_streams": [
                            {
                                "format_id": "140",
                                "abr": 128.0,
                                "audio_channels": 2,
                                "ext": "m4a",
                            }
                        ],
                        "has_muxed_streams": False,
                        "expected_container_by_pair": {"137|140": "mp4", "|": "unknown"},
                    },
                )
            ],
            valid_count=1,
            invalid_count=0,
        )

    monkeypatch.setattr("app.routes.pages.resolve_batch_preview", fake_resolve_batch_preview)

    with TestClient(app) as client:
        response = client.post("/info/batch/form", data={"sources": "https://example.com/good"})

    assert response.status_code == 200
    assert "Formats" in response.text
    assert "Video Streams" in response.text
    assert "Audio Streams" in response.text
    assert 'x-init="streamPickerOpen = false"' in response.text
    assert 'form="batch-enqueue-form"' in response.text
    assert 'name="target_id" value="batch-status"' in response.text
```

Add or update a route test proving enqueue-all stores selected ids:

```python
def test_batch_enqueue_route_preserves_preview_selected_stream_ids(db_session_visible) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/downloads/batch/form",
            data={
                "url": ["https://example.com/a", "https://example.com/b"],
                "title": ["Title A", "Title B"],
                "video_format_id": ["137", ""],
                "audio_format_id": ["140", "251"],
            },
        )

    assert response.status_code == 200
    rows = db_session_visible.query(Download).order_by(Download.id).all()
    assert rows[0].video_format_id == "137"
    assert rows[0].audio_format_id == "140"
    assert rows[1].video_format_id is None
    assert rows[1].audio_format_id == "251"
```

Run both tests and confirm they fail:

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids -v
```

- [ ] **Step 2: Remove duplicated enqueue-all metadata from `batch_result.html`**

Keep only the batch enqueue form shell and submit button. The per-card hidden inputs will attach to this form with the HTML `form` attribute:

```html
{% if result.valid_count %}
<form
  id="batch-enqueue-form"
  hx-post="/downloads/batch/form"
  hx-target="#batch-status"
  hx-swap="innerHTML"
>
  <button type="submit">Enqueue all valid</button>
</form>
{% endif %}
```

- [ ] **Step 3: Embed the shared picker in ready batch cards**

Wrap the ready card in Alpine state using single quotes:

```html
<section
  class="media-card"
  x-data="streamPicker({{ item.picker_payload|tojson }})"
  x-init="streamPickerOpen = false"
></section>
```

Add a `Formats` toggle before the per-item form:

```html
<button
  type="button"
  class="advanced-toggle"
  @click="streamPickerOpen = !streamPickerOpen"
  :aria-expanded="streamPickerOpen.toString()"
>
  Formats
</button>
```

Keep the per-item enqueue form, include the shared picker inside it, and preserve the batch status target:

```html
<input type="hidden" name="target_id" value="batch-status" />
{% include "partials/stream_picker_form.html" %}
<button type="submit">Add to queue</button>
```

Add enqueue-all hidden inputs inside the same Alpine scope, outside the per-item form, and attach them to `batch-enqueue-form`:

```html
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
```

- [ ] **Step 4: Persist selected ids in `downloads_batch_form()`**

In `app/routes/pages.py`, read format-id lists alongside metadata:

```python
video_ids = _form_values(form, "video_format_id")
audio_ids = _form_values(form, "audio_format_id")
```

Add this narrow helper near `_form_values()`:

```python
def _form_value_at(values: list[str], index: int) -> str | None:
    if index >= len(values):
        return None
    return values[index] or None
```

Loop with `enumerate(zip_longest(...))` and pass the matching indexed values into `DownloadCreate`:

```python
video_format_id=_form_value_at(video_ids, index),
audio_format_id=_form_value_at(audio_ids, index),
```

- [ ] **Step 5: Run focused batch integration coverage**

```bash
uv run pytest tests/integration/test_pages.py::test_batch_lookup_fragment_renders_ready_and_error_cards tests/integration/test_pages.py::test_batch_lookup_fragment_renders_enqueue_all_form tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_preview_card_enqueue_posts_metadata_to_queue tests/integration/test_pages.py::test_batch_enqueue_route_creates_one_queued_download_per_valid_preview_item tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids -v
```

Expected: PASS.

- [ ] **Step 6: Commit the batch picker support**

```bash
git add app/templates/partials/batch_preview_card.html app/templates/partials/batch_result.html app/routes/pages.py tests/integration/test_pages.py
git commit -m "feat: add exact format selection to batch preview"
```

---

## Task 4: Run final focused regression coverage

- [ ] **Step 1: Run service, format, and page regressions**

```bash
uv run pytest tests/unit/test_batch_preview.py tests/unit/test_downloader_format.py tests/integration/test_pages.py -v
```

Expected: PASS.

- [ ] **Step 2: Run worker and partial regressions**

```bash
uv run pytest tests/integration/test_partials.py tests/unit/test_library.py tests/integration/test_worker_pool.py -v
```

Expected: PASS, proving selected batch rows still fit the queue, worker, and library behavior.

- [ ] **Step 3: Commit any test-only follow-up**

Only if a small test-only correction is needed:

```bash
git add <exact files touched>
git commit -m "test: cover exact-format batch preview regressions"
```

Otherwise skip this step.
