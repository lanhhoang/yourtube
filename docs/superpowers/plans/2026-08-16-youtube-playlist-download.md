# YouTube Playlist Extraction and Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add paginated YouTube playlist expansion to the existing batch preview and queue independent selected video downloads.

**Architecture:** Extend the current synchronous batch-preview service. Flat-expand playlist sources, combine them with direct URLs, page the expanded candidates, and fully extract metadata only for the requested page. Keep queue storage and worker execution unchanged; use indexed HTML form fields for page-local bulk selection.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy, pytest, yt-dlp.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

## Global Constraints

- Keep the existing batch entry point and independent `Download` queue jobs.
- Default playlist page size is `20`; valid configured values are `1..50`.
- Preserve direct URL behavior, per-video format selection, friendly yt-dlp errors, and page-local selection.
- Add no dependencies, migrations, playlist tables, background workers, or public JSON API.
- Write tests before implementation for each behavior change.

---

### Task 1: Add playlist expansion and paginated preview contracts

**Files:**

- Modify: `app/services/batch_preview.py`
- Modify: `app/services/preview.py`
- Test: `tests/unit/test_batch_preview.py`

**Interfaces:**

- `resolve_batch_preview(raw, *, extract_info, expand_playlist=None, proxy=None, cookies_file=None, page=1, page_size=20) -> BatchPreviewResult`
- `BatchPreviewResult` adds `page`, `page_size`, `total_count`, `total_pages`, `has_previous`, and `has_next`.
- Add an internal expanded-entry record carrying `source_url`, optional title, and optional error details so invalid playlist entries remain visible.

- [ ] **Step 1: Write failing tests** for YouTube ID URL fallback, URL precedence, lazy flat entries, empty/invalid entries, mixed source ordering, deduplication, page slicing, page metadata, page clamping, and current-page-only metadata extraction.
- [ ] **Step 2: Run the focused tests** with `uv run pytest tests/unit/test_batch_preview.py -q`; confirm the new cases fail.
- [ ] **Step 3: Implement the minimal expansion path** using the existing `extract_flat_info` seam. Prefer `webpage_url`, then full `url`, then `https://www.youtube.com/watch?v=<id>` for YouTube entries. Convert unusable entries into error candidates.
- [ ] **Step 4: Implement page slicing and result metadata** while preserving direct URL behavior and existing friendly error mapping.
- [ ] **Step 5: Run the focused tests** again and confirm they pass.
- [ ] **Step 6: Commit** with `git add app/services/batch_preview.py app/services/preview.py tests/unit/test_batch_preview.py && git commit -m "feat: paginate playlist batch previews"`.

### Task 2: Add the persisted playlist page-size setting

**Files:**

- Modify: `app/services/settings.py`
- Modify: `app/routes/pages.py`
- Modify: `app/templates/pages/settings.html`
- Modify: `app/templates/partials/settings_form.html`
- Test: `tests/unit/test_settings_runtime_resolution.py`
- Test: `tests/integration/test_pages.py`

**Interfaces:**

- `RuntimeSettings.playlist_page_size: int`
- Settings key: `playlist_page_size`, default string value `"20"`.

- [ ] **Step 1: Write failing tests** for default resolution, persisted resolution, values `1` and `50`, and rejection of `0`, `51`, and non-integers.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_settings_runtime_resolution.py -q`; confirm failure.
- [ ] **Step 3: Add the catalog key, validator, runtime field, form input, and route form update.** Keep all settings updates atomic through the existing service.
- [ ] **Step 4: Add the settings-page rendering assertion** and run the focused unit/integration tests.
- [ ] **Step 5: Commit** with `git add app/services/settings.py app/routes/pages.py app/templates/pages/settings.html app/templates/partials/settings_form.html tests/unit/test_settings_runtime_resolution.py tests/integration/test_pages.py && git commit -m "feat: configure playlist preview page size"`.

### Task 3: Wire the paginated HTMX preview UI

**Files:**

- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/templates/partials/batch_preview_card.html`
- Modify: `app/templates/partials/stream_picker_form.html`
- Modify: `app/static/css/app.css` only for required checkbox/pagination layout
- Test: `tests/integration/test_pages.py`

**Interfaces:**

- `POST /info/batch/form` reads `sources` and `page`, resolves `RuntimeSettings.playlist_page_size`, and renders the current page.
- Pagination submits the original source text and a page number to `/info/batch/form`, targeting `#batch-result`.

- [ ] **Step 1: Write failing integration tests** for page summaries, previous/next controls, hidden source preservation, checked-by-default ready rows, visible error rows, and configured page size.
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_pages.py -q`; confirm failure.
- [ ] **Step 3: Pass `page` and `page_size` through the route** and render pagination state in the batch fragment.
- [ ] **Step 4: Add page-local checkboxes** while retaining each row’s individual enqueue form.
- [ ] **Step 5: Mirror Alpine format and advanced-option state** into indexed bulk fields so per-video choices survive bulk enqueue.
- [ ] **Step 6: Run the focused integration tests** and confirm they pass.

### Task 4: Parse selected indexed rows for bulk enqueue

**Files:**

- Modify: `app/services/enqueue_intake.py`
- Test: `tests/unit/test_enqueue_intake.py`
- Test: `tests/integration/test_pages.py`

**Interfaces:**

- `build_batch_downloads(form)` accepts repeated `selected_index` values and reads indexed fields for each selected row.
- Empty selection returns an empty payload list; direct raw-source submissions retain existing behavior.

- [ ] **Step 1: Write failing tests** for selecting one of several rows, preserving each row’s title/duration/format/advanced fields, ignoring unchecked rows, empty selection, and direct URL regression.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_enqueue_intake.py -q`; confirm failure.
- [ ] **Step 3: Implement indexed-field parsing** with numeric index validation, existing duration conversion, and the existing `DownloadCreate` contract.
- [ ] **Step 4: Update the batch route response** to report a clear no-selection message and avoid creating jobs when the payload list is empty.
- [ ] **Step 5: Run unit and integration enqueue tests** and confirm selected rows create independent queued downloads.
- [ ] **Step 6: Commit** with `git add app/services/enqueue_intake.py tests/unit/test_enqueue_intake.py tests/integration/test_pages.py && git commit -m "feat: enqueue selected playlist videos"`.

### Task 5: Full verification and handoff

**Files:**

- Test: all affected unit and integration test files
- Modify: `README.md` only if the project’s feature list needs the playlist workflow documented

- [ ] **Step 1: Run** `uv run pytest` and fix only failures caused by this feature.
- [ ] **Step 2: Run** `uv run ruff check .`.
- [ ] **Step 3: Run** `uv run ty check`.
- [ ] **Step 4: Manually smoke-test** the supplied playlist URL: preview page 1, navigate pages, deselect entries, choose per-video formats, enqueue selected rows, and verify independent queue jobs.
- [ ] **Step 5: Self-review the diff** for accidental schema changes, unindexed bulk fields, silent invalid-entry loss, and regressions in direct URL batching.
- [ ] **Step 6: Commit any final documentation/test-only corrections** with `git add README.md tests app && git commit -m "test: verify playlist download workflow"`.

## Plan self-review

- Every spec requirement maps to Tasks 1–5.
- No placeholder steps or undefined interfaces remain.
- The plan preserves the existing worker, queue schema, downloader, and direct-video flow.
- The only deliberate ceiling is re-expanding playlists on each page request; persistent sessions can be added later if this becomes a measured performance or UX problem.
