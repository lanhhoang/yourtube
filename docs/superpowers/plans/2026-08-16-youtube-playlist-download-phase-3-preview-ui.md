# YouTube Playlist Download — Phase 3: Paginated Preview UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the settings-aware preview service into the existing batch form and render paginated playlist results with existing individual enqueue actions.

**Architecture:** Keep one HTMX route, `POST /info/batch/form`. The route reads the source text and page number, resolves the configured page size, and swaps only `#batch-result`; each rendered ready card continues to use the existing individual `/downloads/form` action.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Global Constraints

- Preserve the existing batch form and individual video enqueue behavior.
- Navigation resubmits the original source text and page number.
- Render no more than the configured page size and keep failures visible.
- Do not add client-side playlist state or a new route family.

## Files

- Modify: `app/routes/pages.py`
- Modify: `app/templates/partials/batch_result.html`
- Modify: `app/templates/partials/batch_preview_card.html` only where needed to render paged candidates
- Modify: `app/static/css/app.css` only for required pagination layout
- Test: `tests/integration/test_pages.py`

## Interfaces

- `POST /info/batch/form` reads `sources` and optional `page`, passes `RuntimeSettings.playlist_page_size` to `resolve_batch_preview`, and renders `partials/batch_result.html`.
- Pagination forms submit `sources` and `page`, target `#batch-result`, and use `innerHTML` replacement.

## Steps

- [ ] **Step 1: Write failing integration tests** for page summaries, page position/total, previous/next controls, hidden source preservation, configured page size, ready cards, and visible error cards.
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_pages.py -q`; confirm the new cases fail.
- [ ] **Step 3: Update the route** to accept `page`, resolve runtime page size, call the paginated preview service, and pass the original source text to the template.
- [ ] **Step 4: Render pagination controls** with disabled/omitted previous and next actions at the correct boundaries.
- [ ] **Step 5: Preserve existing individual enqueue forms** and ensure page navigation does not submit or create queue rows.
- [ ] **Step 6: Run** `uv run pytest tests/integration/test_pages.py -q`; confirm focused tests pass.
- [ ] **Step 7: Commit** with `git add app/routes/pages.py app/templates/partials/batch_result.html app/templates/partials/batch_preview_card.html app/static/css/app.css tests/integration/test_pages.py && git commit -m "feat: add paginated playlist preview UI"`.

## Usable result

Users can paste the supplied playlist into the existing batch form, inspect one page at a time, navigate the playlist, and individually add any ready video to the existing queue.
