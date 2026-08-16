# YouTube Playlist Download — Phase 2: Expansion Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the batch service expand mixed direct and playlist sources into ordered, deduplicated, paginated preview candidates.

**Architecture:** Keep playlist discovery on the existing `extract_flat_info` seam and keep full metadata extraction on `extract_info`. Expand every source before slicing the requested page, represent malformed playlist entries as visible error candidates, and extract full metadata only for usable URLs on the current page.

**Tech Stack:** Python 3.12, yt-dlp, pytest.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Parent plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download-parent.md`

## Current-repo constraints

- Phase 1 is already merged on this branch: `RuntimeSettings.playlist_page_size` and the persisted `1..50` setting contract exist. Do not touch settings, routes, or templates in this phase.
- `app/services/batch_preview.py` currently caps expanded candidates at 50 and exposes `truncated_count`; remove the service cap, but retain that field with its default for compatibility with the current result template and existing manually-built test results. The new service always returns `truncated_count == 0`.
- `app/services/preview.py` is the route-facing facade. It must accept and forward pagination arguments while preserving its injectable flat-expansion seam and the current direct-source fallback.

## Global constraints

- Preserve direct URL behavior, existing friendly yt-dlp errors, and the existing `extract_info`/proxy/cookies call shape.
- Resolve a flat entry URL in this order: valid `webpage_url`, valid full `url`, then `https://www.youtube.com/watch?v=<id>` for a non-empty entry ID. A valid full URL is an `http` or `https` URL with a network location; relative extractor URLs are not usable.
- Preserve source/entry order and deduplicate only usable exact URLs in first-seen order. Invalid entries are never deduplicated away.
- Do not impose a playlist-wide or batch-wide candidate cap. Page size is the only slice, and the settings service supplies values from `1..50`.
- Keep all expansion and metadata work synchronous; add no dependencies, migrations, storage, or public API.

## Interfaces

- `resolve_batch_preview(raw, *, extract_info, expand_playlist=None, proxy=None, cookies_file=None, page=1, page_size=20) -> BatchPreviewResult` in both the core service and the route-facing `app.services.preview` facade. The facade supplies the existing `extract_flat_info`-backed expansion callback when none is injected.
- `expand_playlist_entries(url, *, extract_info, proxy=None, cookies_file=None)` returns internal expanded-entry records. Keep the `extract_info` keyword name so the existing preview test seam remains usable.
- Add an internal expanded-entry record with `source_url`, optional flat `title`, and optional `error_code`/`error_message`. Invalid entries use the playlist source URL as their origin, a title such as `Playlist entry 3`, and an `invalid_playlist_entry` error whose message includes the 1-based position.
- Extend `BatchPreviewResult` with `page`, `page_size`, `total_count`, `total_pages`, `has_previous`, and `has_next`. Give them compatibility defaults of `1`, `20`, `0`, `1`, `False`, and `False` respectively so existing route tests that construct a result manually remain valid; service-produced results always contain calculated values.
- `valid_count` and `invalid_count` count only the returned page. `total_count` counts all expanded candidates, including errors. An empty candidate set reports page `1`, one total page, and no navigation.

## Expansion and pagination rules

- A flat result without an `entries` value represents a direct source and yields one usable source candidate. An empty iterable of entries yields no candidates. A malformed non-iterable/string `entries` value yields one visible expansion error candidate with code `invalid_playlist_entries` and message `Playlist entries could not be read.`.
- Iterate entries once so generators and other lazy iterables work. Non-dict entries and dicts without a usable URL become error candidates labeled with their 1-based playlist position.
- Normalize callback-returned URL strings into expanded-entry records so existing unit seams remain simple; callback-returned error records pass through unchanged.
- If expansion raises, retain the current direct-source fallback: send the original source through normal metadata extraction, map that extraction failure with `friendly_ytdlp_error`, and continue with later sources. A failed fallback produces one error item for that source.
- Expand and deduplicate the complete candidate sequence before computing `total_count` and slicing. Clamp `page_size` to at least 1, clamp requested page values below 1 to page 1, and clamp values beyond the last page to the last page. For an empty sequence, keep page 1.
- Run `extract_info` and build picker payloads only for usable candidates in the clamped current page. Pass through prebuilt error candidates without metadata extraction. Preserve the existing unsupported-playlist guard for direct-only calls.

## Files

- Modify: `app/services/batch_preview.py`
- Modify: `app/services/preview.py`
- Test: `tests/unit/test_batch_preview.py`
- Test: `tests/unit/test_preview.py`

## Steps

- [ ] **Step 1: Write/update failing unit tests** for URL precedence and YouTube ID fallback, lazy flat entry iterables, empty and malformed entries, position-labeled invalid candidates, mixed source order, exact deduplication, no total cap, page slicing, total/page navigation metadata, page clamping including empty results, expansion-error continuation, and current-page-only metadata extraction. Update the existing hard-cap assertion rather than preserving the obsolete 50-item behavior. Add a facade test that forwards `page` and `page_size`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_batch_preview.py tests/unit/test_preview.py -q`; confirm the new and changed cases fail for the current implementation.
- [ ] **Step 3: Implement expanded-entry resolution** in `batch_preview.py`: add URL validation/precedence, ID fallback, lazy iteration, visible invalid-entry records, and callback-result normalization while preserving proxy/cookie forwarding and the direct-source fallback.
- [ ] **Step 4: Implement uncapped expansion, page clamping, result metadata, and page-local full extraction**. Keep friendly error mapping, current picker payload construction, and compatibility defaults for `BatchPreviewResult`.
- [ ] **Step 5: Update the `preview.py` facade** to accept `expand_playlist`, `page`, and `page_size`, use the existing `extract_flat_info` closure by default, and forward the complete contract to the core service.
- [ ] **Step 6: Run focused and regression checks** with `uv run pytest tests/unit/test_batch_preview.py tests/unit/test_preview.py tests/integration/test_pages.py -q`; confirm the new service behavior passes and existing result/template/direct-source tests remain green.
- [ ] **Step 7: Commit** with `git add app/services/batch_preview.py app/services/preview.py tests/unit/test_batch_preview.py tests/unit/test_preview.py && git commit -m "feat: paginate playlist batch previews"`.

## Usable result

The route-facing batch preview service can accept mixed direct and playlist sources, return a clamped page of ready/error candidates with navigation metadata, avoid full extraction outside the current page, and preserve existing direct URL behavior for Phase 3 to render.
