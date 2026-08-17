# YouTube Playlist Download — Phase 4: Selected Enqueue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add page-local row selection and bulk enqueue while preserving each video's metadata, format choices, and advanced options.

**Architecture:** Keep the existing individual row forms for single-item actions. The existing page-level bulk form becomes a selected-row form: ready rows render checked `selected_index` controls and indexed hidden fields, while Alpine state mirrors each row's format and advanced choices into that form. `build_batch_downloads` parses the indexed mode and retains the existing raw-source and legacy unindexed preview fallbacks; the queue service and database stay unchanged.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, Alpine.js, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

**Current-repo state:** Phase 3 is merged at `HEAD` (`22663b0`). The current page-level `#batch-enqueue-form` submits every ready row through repeated unindexed fields, while each card also has its own individual enqueue form. `build_batch_downloads` already supports raw direct-URL submissions and the legacy unindexed preview payload, but it does not yet filter selected rows or carry advanced fields. Baseline checks are green: `233` tests, Ruff, and ty.

## Global constraints

- Selection is page-local; navigation does not persist selections or format choices across pages.
- Ready rows are checked by default. Error rows are never selectable and never become queue jobs.
- The new bulk form uses `selected_index` plus indexed names based on the zero-based page-item position:
  `url_0`, `title_0`, `uploader_0`, `duration_0`, `thumbnail_0`,
  `video_format_id_0`, `audio_format_id_0`, `output_template_0`,
  `audio_bitrate_0`, and `subtitles_0`.
- Consume unique non-negative decimal `selected_index` values in submitted order; ignore malformed, duplicate, or missing indexed rows. A missing URL never creates a job.
- A selected row preserves all five stream-selection values: video format, audio format, output template, audio bitrate, and subtitles.
- If no row is selected, create no jobs and return the clear status message `No videos selected.`
- Preserve raw direct-URL batch submissions and individual enqueue behavior.
- Preserve the current legacy unindexed preview payload when no `selected_index` field is submitted; this keeps existing callers and tests working while the rendered UI moves to indexed fields.
- Do not add dependencies, migrations, playlist state, cross-page selection, or queue-service changes. Do not change CSS unless implementation verification shows the existing layout cannot accommodate the checkbox.

## Files

- Modify: `app/services/enqueue_intake.py`
- Modify: `app/services/stream_selection.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/stream_picker_form.html`
- Test: `tests/unit/test_enqueue_intake.py`
- Test: `tests/unit/test_stream_selection.py`
- Test: `tests/integration/test_pages.py`

## Interfaces and parsing contract

Extend the existing `selection_from_form` helper with an optional field suffix, preserving its current no-suffix behavior:

```python
selection_from_form(form, suffix="_0")
```

`build_batch_downloads(form)` uses these modes in order:

1. If `selected_index` is present, parse indexed rows in the order of the submitted indices. Use `selection_from_form(form, suffix=f"_{index}")` for the five per-row selection values. Ignore invalid/duplicate indices and rows without an indexed URL. Do not fall through to raw sources when the submitted form is explicitly in selected-index mode.
2. If no `selected_index` is present and `sources` contains URLs, retain the current deduplicated raw direct-URL path.
3. If neither selected indices nor raw sources are present, retain the current repeated unindexed preview-row fallback. With no usable rows it returns an empty list.

The route keeps `POST /downloads/batch/form` and enqueues one existing `DownloadCreate` per returned payload. It returns `No videos selected.` when the payload list is empty; otherwise it retains the existing `Added N items to queue.` message and `batch-status` target.

## Steps

- [ ] **Step 1: Write failing unit tests for the indexed intake contract.**
  - Select one of two indexed rows and assert only that row becomes a `DownloadCreate`.
  - Assert selected metadata is preserved: title, uploader, duration, thumbnail, video format, audio format, output template, audio bitrate, and subtitles.
  - Assert unchecked rows are absent from `selected_index` and therefore ignored, empty selection returns `[]`, duplicate/malformed indices do not create extra jobs, and missing indexed URLs are skipped.
  - Keep the existing raw direct-URL regression and legacy unindexed preview-row tests.
  - Add a focused suffix test for `selection_from_form` so the existing stream-field contract remains configurable and no-suffix callers remain unchanged.

- [ ] **Step 2: Run the focused unit tests and confirm the new cases fail.**

  ```bash
  uv run pytest tests/unit/test_enqueue_intake.py tests/unit/test_stream_selection.py -q
  ```

- [ ] **Step 3: Implement indexed parsing at the existing intake boundary.**
  - Add the optional suffix to `selection_from_form` and use it from the indexed branch instead of duplicating the five stream-field names.
  - Parse and validate `selected_index` values once, preserving first-seen order and ignoring malformed, duplicate, negative, or missing rows.
  - Build `DownloadCreate` with all row metadata and all five selection values, including `subtitles`.
  - Keep the raw-source and legacy unindexed branches unchanged unless a shared helper change is required.

- [ ] **Step 4: Add page-local selection controls without nesting forms.**
  - Keep `#batch-enqueue-form` as the page-level form and change its action label to `Enqueue selected`.
  - In `batch_preview_card.html`, give each ready row a checked checkbox with `name="selected_index"` and the page-item zero-based index, associated with `batch-enqueue-form`. Do not render a checkbox for error rows.
  - Move the bulk row fields to indexed names using the same page-item index. Keep the individual `/downloads/form` fields and behavior unchanged.
  - Pass the loop index explicitly from `batch_result.html` into each card so error rows do not cause index collisions.

- [ ] **Step 5: Mirror per-row Alpine state into indexed bulk fields.**
  - Extend `streamPicker` with state for output template, audio bitrate, and subtitles.
  - Bind the existing advanced controls with `x-model` so individual and bulk submissions see the same values.
  - Add external hidden bulk controls for the indexed video/audio/advanced fields, using `form="batch-enqueue-form"` and the row index. Encode an unchecked subtitles value as an empty value and a checked value as `on`.
  - Keep pagination controls source/settings-only; cross-page selection remains out of scope.

- [ ] **Step 6: Update the batch route's empty-selection response.**
  - Keep `POST /downloads/batch/form` and its enqueue loop unchanged for non-empty payloads.
  - Return `No videos selected.` with target `batch-status` when no payloads are produced.

- [ ] **Step 7: Add integration coverage for rendering and queue behavior.**
  - Assert the rendered fragment has checked ready-row selectors, no selector for error rows, indexed metadata/selection field names, `Enqueue selected`, and the existing individual enqueue form.
  - Post two indexed rows with one selected and assert exactly one queued `Download` contains that row's metadata, all five selection values, and no unchecked row.
  - Assert an empty selection creates no rows and returns `No videos selected.`
  - Keep existing direct-source, legacy preview-row, individual enqueue, pagination, active stream-field, and friendly-error coverage green.

- [ ] **Step 8: Run focused and regression checks.**

  ```bash
  uv run pytest tests/unit/test_enqueue_intake.py tests/unit/test_stream_selection.py tests/integration/test_pages.py -q
  uv run pytest -q
  uv run ruff check .
  uv run ty check
  ```

- [ ] **Step 9: Commit the phase implementation.**

  ```bash
  git add app/services/enqueue_intake.py app/services/stream_selection.py app/routes/pages.py app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html app/templates/partials/stream_picker_form.html tests/unit/test_enqueue_intake.py tests/unit/test_stream_selection.py tests/integration/test_pages.py
  git commit -m "feat: enqueue selected playlist videos"
  ```

## Usable result

Users can select a subset of the current preview page, retain each selected video's metadata, format, and advanced choices, and create exactly one existing queue job per selected video. Raw direct-URL batches, legacy preview submissions, and individual video enqueue remain supported.
