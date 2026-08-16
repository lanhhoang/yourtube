# YouTube Playlist Download — Phase 4: Selected Enqueue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add page-local row selection and bulk enqueue while preserving each video’s chosen formats and advanced options.

**Architecture:** Keep individual row forms for single-item actions, and add a separate page-level bulk form using `selected_index` plus indexed metadata and format fields. Alpine state mirrors each row’s format choices into that bulk form; the existing queue service remains unchanged.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, Alpine.js, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Global Constraints

- Selection is page-local and ready rows are checked by default.
- Bulk fields use names such as `url_0`, `title_0`, `video_format_id_0`, and `subtitles_0`.
- Empty selection creates no jobs and returns a clear status message.
- Preserve raw direct-URL batch submissions and individual enqueue behavior.

## Files

- Modify: `app/services/enqueue_intake.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/stream_picker_form.html`
- Modify: `app/static/css/app.css` only for required selection layout
- Test: `tests/unit/test_enqueue_intake.py`
- Test: `tests/integration/test_pages.py`

## Interfaces

- `build_batch_downloads(form)` accepts repeated `selected_index` values and reads indexed fields for selected rows.
- `POST /downloads/batch/form` enqueues the returned `DownloadCreate` payloads and reports the created count; an empty list reports no selection.

## Steps

- [ ] **Step 1: Write failing unit tests** for selecting one of several rows, preserving title/duration/thumbnail/format/advanced fields, ignoring unchecked rows, empty selection, and direct URL regression.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_enqueue_intake.py -q`; confirm the new cases fail.
- [ ] **Step 3: Implement indexed-field parsing** with numeric index validation, existing duration conversion, and the existing `DownloadCreate` contract.
- [ ] **Step 4: Add checked-by-default row checkboxes** and indexed hidden fields to the bulk form while retaining per-row individual forms.
- [ ] **Step 5: Mirror Alpine stream and advanced-option state** into the indexed bulk fields so each selected row preserves its own choices.
- [ ] **Step 6: Update the batch route response** for successful selected enqueue and the no-selection case.
- [ ] **Step 7: Run** `uv run pytest tests/unit/test_enqueue_intake.py tests/integration/test_pages.py -q`; confirm selected rows create independent queued downloads and direct batches still pass.
- [ ] **Step 8: Commit** with `git add app/services/enqueue_intake.py app/routes/pages.py app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html app/templates/partials/stream_picker_form.html app/static/css/app.css tests/unit/test_enqueue_intake.py tests/integration/test_pages.py && git commit -m "feat: enqueue selected playlist videos"`.

## Usable result

Users can select a subset of the current preview page, retain per-video format choices, and create exactly one existing queue job per selected video.
