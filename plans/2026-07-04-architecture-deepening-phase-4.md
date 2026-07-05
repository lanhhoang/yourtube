# Architecture Deepening Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the stream-selection contract explicit without changing route, picker, or yt-dlp selection behavior.

**Architecture:** Keep the existing field names, route behavior, and template UX intact, but introduce `app/services/stream_selection.py` as the single source of truth for stream field names plus scalar and repeated form parsing. Wire `enqueue_intake` and the preview templates to the new contract so the hidden-field convention is explicit and tested. Empty selected stream ids should normalize to `None` before creating `DownloadCreate`; that preserves downstream yt-dlp behavior while making the typed contract cleaner.

**Tech Stack:** Python 3.12, FastAPI, Starlette `FormData`, Jinja2, pytest, Alpine.js

---

## File Structure

- Create: `app/services/stream_selection.py`
  Purpose: Own stream field names and typed scalar/repeated form parsing.
- Create: `tests/unit/test_stream_selection.py`
  Purpose: Lock down the explicit stream-selection contract.
- Modify: `app/services/enqueue_intake.py`
  Purpose: Consume typed stream selection instead of hard-coded field lookups.
- Modify: `tests/unit/test_enqueue_intake.py`
  Purpose: Lock down empty single-form stream field normalization through the intake seam.
- Modify: `app/routes/pages.py`
  Purpose: Pass shared stream field names into the preview template contexts.
- Modify: `app/templates/partials/info_result.html`
  Purpose: Consume the shared field names for single-preview forms.
- Modify: `app/templates/partials/batch_preview_card.html`
  Purpose: Consume the shared field names for batch-preview forms.
- Modify: `app/templates/partials/stream_picker_form.html`
  Purpose: Render hidden-input names from the explicit contract.

---

### Task 1: Add an explicit stream-selection contract module

**Files:**

- Create: `app/services/stream_selection.py`
- Create: `tests/unit/test_stream_selection.py`

- [ ] **Step 1: Write the failing stream-selection tests**

Create `tests/unit/test_stream_selection.py` with:

```python
from __future__ import annotations

from starlette.datastructures import FormData

from app.services.stream_selection import (
    STREAM_FIELDS,
    selection_from_form,
    selection_values_from_form,
)


def test_stream_fields_define_the_public_contract() -> None:
    assert STREAM_FIELDS.video_format_id == "video_format_id"
    assert STREAM_FIELDS.audio_format_id == "audio_format_id"
    assert STREAM_FIELDS.output_template == "output_template"
    assert STREAM_FIELDS.audio_bitrate == "audio_bitrate"
    assert STREAM_FIELDS.subtitles == "subtitles"


def test_selection_from_form_reads_existing_field_names() -> None:
    form = FormData(
        [
            ("video_format_id", "137"),
            ("audio_format_id", "140"),
            ("output_template", "%(title)s.%(ext)s"),
            ("audio_bitrate", "128"),
            ("subtitles", "on"),
        ]
    )

    selection = selection_from_form(form)

    assert selection.video_format_id == "137"
    assert selection.audio_format_id == "140"
    assert selection.output_template == "%(title)s.%(ext)s"
    assert selection.audio_bitrate == "128"
    assert selection.subtitles is True


def test_selection_from_form_normalizes_empty_stream_values() -> None:
    form = FormData(
        [
            ("video_format_id", ""),
            ("audio_format_id", ""),
            ("output_template", ""),
            ("audio_bitrate", ""),
        ]
    )

    selection = selection_from_form(form)

    assert selection.video_format_id is None
    assert selection.audio_format_id is None
    assert selection.output_template is None
    assert selection.audio_bitrate is None
    assert selection.subtitles is False


def test_selection_values_from_form_preserves_repeated_values_for_batch_alignment() -> None:
    form = FormData(
        [
            ("video_format_id", "137"),
            ("video_format_id", ""),
            ("audio_format_id", "140"),
            ("audio_format_id", "251"),
        ]
    )

    values = selection_values_from_form(form)

    assert values.video_format_ids == ["137", ""]
    assert values.audio_format_ids == ["140", "251"]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.stream_selection'`.

- [ ] **Step 3: Write the explicit stream-selection contract**

Create `app/services/stream_selection.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from starlette.datastructures import FormData, UploadFile


@dataclass(frozen=True)
class StreamFieldNames:
    video_format_id: str = "video_format_id"
    audio_format_id: str = "audio_format_id"
    output_template: str = "output_template"
    audio_bitrate: str = "audio_bitrate"
    subtitles: str = "subtitles"


@dataclass(frozen=True)
class StreamSelection:
    video_format_id: str | None
    audio_format_id: str | None
    output_template: str | None
    audio_bitrate: str | None
    subtitles: bool


@dataclass(frozen=True)
class StreamSelectionValues:
    video_format_ids: list[str]
    audio_format_ids: list[str]


STREAM_FIELDS = StreamFieldNames()


def _str_value(form: FormData, key: str) -> str | None:
    value = form.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value) or None


def _str_values(form: FormData, key: str) -> list[str]:
    return [str(value) for value in form.getlist(key) if not isinstance(value, UploadFile)]


def selection_from_form(form: FormData) -> StreamSelection:
    return StreamSelection(
        video_format_id=_str_value(form, STREAM_FIELDS.video_format_id),
        audio_format_id=_str_value(form, STREAM_FIELDS.audio_format_id),
        output_template=_str_value(form, STREAM_FIELDS.output_template),
        audio_bitrate=_str_value(form, STREAM_FIELDS.audio_bitrate),
        subtitles=form.get(STREAM_FIELDS.subtitles) == "on",
    )


def selection_values_from_form(form: FormData) -> StreamSelectionValues:
    return StreamSelectionValues(
        video_format_ids=_str_values(form, STREAM_FIELDS.video_format_id),
        audio_format_ids=_str_values(form, STREAM_FIELDS.audio_format_id),
    )
```

- [ ] **Step 4: Run the new tests and verify they pass**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py -v
```

Expected: PASS.

---

### Task 2: Wire intake and templates to the shared contract

**Files:**

- Modify: `app/services/enqueue_intake.py`
- Modify: `tests/unit/test_enqueue_intake.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/info_result.html`
- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/stream_picker_form.html`

- [ ] **Step 1: Make enqueue intake consume typed stream selection**

In `app/services/enqueue_intake.py`, add:

```python
from app.services.stream_selection import selection_from_form, selection_values_from_form
```

Replace the stream-related fields in `build_single_download()` with:

```python
    selection = selection_from_form(form)
```

and:

```python
        video_format_id=selection.video_format_id,
        audio_format_id=selection.audio_format_id,
        output_template=selection.output_template,
        audio_bitrate=selection.audio_bitrate,
        subtitles=selection.subtitles,
```

Add a focused unit assertion to `tests/unit/test_enqueue_intake.py` that empty single-form stream fields become `None`:

```python
def test_build_single_download_normalizes_empty_stream_fields() -> None:
    form = FormData(
        [
            ("url", "https://example.com/watch?v=1"),
            ("video_format_id", ""),
            ("audio_format_id", ""),
            ("output_template", ""),
            ("audio_bitrate", ""),
        ]
    )

    payload, _target_id = build_single_download(form)

    assert payload.video_format_id is None
    assert payload.audio_format_id is None
    assert payload.output_template is None
    assert payload.audio_bitrate is None
```

Also replace the hard-coded repeated batch stream field lookups with:

```python
    selection_values = selection_values_from_form(form)
```

and use `selection_values.video_format_ids` / `selection_values.audio_format_ids` in the `zip_longest()` call.

- [ ] **Step 2: Pass the explicit field names into preview templates**

In `app/routes/pages.py`, add:

```python
from app.services.stream_selection import STREAM_FIELDS
```

Include `stream_fields` in the single-preview and batch-preview template contexts:

```python
            "stream_fields": STREAM_FIELDS,
```

- [ ] **Step 3: Replace hard-coded template field names**

In `app/templates/partials/info_result.html`, `app/templates/partials/batch_preview_card.html`, and `app/templates/partials/stream_picker_form.html`, replace literal stream field names:

```html
name="video_format_id" name="audio_format_id" name="output_template"
name="audio_bitrate" name="subtitles"
```

with:

```html
name="{{ stream_fields.video_format_id }}" name="{{
stream_fields.audio_format_id }}" name="{{ stream_fields.output_template }}"
name="{{ stream_fields.audio_bitrate }}" name="{{ stream_fields.subtitles }}"
```

- [ ] **Step 4: Run the focused verification**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py tests/unit/test_enqueue_intake.py tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids -v
```

Expected: PASS.

---

### Task 3: Verify the phase is atomic and usable

**Files:**

- Modify: none expected

- [ ] **Step 1: Run the phase-local verification**

Run:

```bash
uv run pytest tests/unit/test_stream_selection.py tests/unit/test_enqueue_intake.py tests/integration/test_pages.py::test_info_lookup_fragment_renders_stream_picker_markup tests/integration/test_pages.py::test_batch_lookup_fragment_renders_collapsed_format_picker tests/integration/test_pages.py::test_batch_enqueue_route_preserves_preview_selected_stream_ids tests/integration/test_pages.py::test_batch_preview_card_enqueue_posts_metadata_to_queue -v
```

Expected: PASS.

- [ ] **Step 2: Commit the phase**

```bash
git add app/services/stream_selection.py app/services/enqueue_intake.py app/routes/pages.py app/templates/partials/info_result.html app/templates/partials/batch_preview_card.html app/templates/partials/stream_picker_form.html tests/unit/test_stream_selection.py tests/unit/test_enqueue_intake.py
git commit -m "refactor: make stream selection contract explicit"
```

- [ ] **Step 3: Confirm the worktree is clean**

Run:

```bash
git status --short
```

Expected: clean worktree.
