# YouTube Playlist Download — Phase 2: Expansion Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the batch service expand mixed direct and playlist sources into ordered, deduplicated, paginated preview candidates.

**Architecture:** Reuse the existing `extract_flat_info` seam and injectable preview callbacks. Keep full metadata extraction limited to the selected page, represent invalid entries as error candidates, and return navigation metadata without changing queue storage.

**Tech Stack:** Python 3.12, yt-dlp, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Global Constraints

- Preserve direct URL behavior and existing friendly yt-dlp errors.
- Resolve entry URLs by preferring `webpage_url`, then full `url`, then a YouTube watch URL from `id`.
- Preserve order, deduplicate exact URLs, keep invalid entries visible, and do not add a total playlist cap.
- Use default `page=1` and `page_size=20`; clamp requested pages to the available range.

## Files

- Modify: `app/services/batch_preview.py`
- Modify: `app/services/preview.py`
- Test: `tests/unit/test_batch_preview.py`

## Interfaces

- `resolve_batch_preview(raw, *, extract_info, expand_playlist=None, proxy=None, cookies_file=None, page=1, page_size=20) -> BatchPreviewResult`
- `BatchPreviewResult` adds `page`, `page_size`, `total_count`, `total_pages`, `has_previous`, and `has_next`.
- Add an internal expanded-entry record carrying `source_url`, optional title, and optional error details.

## Steps

- [ ] **Step 1: Write failing unit tests** for URL precedence, YouTube ID fallback, lazy flat entry iterables, empty/invalid entries, mixed source order, exact deduplication, page slicing, navigation metadata, page clamping, and current-page-only metadata extraction.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_batch_preview.py -q`; confirm the new cases fail.
- [ ] **Step 3: Implement expanded-entry resolution** using the existing `extract_flat_info` path. Convert entries without usable URLs into error candidates labeled by playlist position.
- [ ] **Step 4: Implement page slicing and result metadata** while retaining the existing preview error mapper and direct-source fallback.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_batch_preview.py -q`; confirm all focused tests pass.
- [ ] **Step 6: Commit** with `git add app/services/batch_preview.py app/services/preview.py tests/unit/test_batch_preview.py && git commit -m "feat: paginate playlist batch previews"`.

## Usable result

The service can be called by a route or test with a mixed source string and returns a page of ready/error candidates plus enough metadata to render navigation.
