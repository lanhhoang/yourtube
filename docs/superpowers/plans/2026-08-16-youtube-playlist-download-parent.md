# YouTube Playlist Download Parent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. The original plan remains unchanged; phase plans are the execution units.

**Goal:** Deliver paginated YouTube playlist extraction and selected independent downloads through five small, usable implementation phases.

**Architecture:** Reuse the existing batch-preview, settings, HTMX, Alpine.js, enqueue, and queue services. Build from configuration and pure service contracts toward rendered pagination and finally indexed bulk selection, leaving the worker and database schema unchanged.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy, pytest, yt-dlp.

**Spec:** `docs/superpowers/specs/2026-08-16-youtube-playlist-download-design.md`

**Source plan:** `docs/superpowers/plans/2026-08-16-youtube-playlist-download.md` (preserved unchanged)

## Global Constraints

- Keep the existing batch entry point and independent `Download` queue jobs.
- Default playlist page size is `20`; valid configured values are `1..50`.
- Preserve direct URL behavior, per-video format selection, friendly yt-dlp errors, and page-local selection.
- Add no dependencies, migrations, playlist tables, background workers, or public JSON API.
- Write tests before implementation for each behavior change.
- Keep the original source plan unchanged; add and edit only the parent and phase plan files during planning.

## Phase order

| Phase | Plan file                                                          | Atomic usable result                                                                               | Depends on               |
| ----- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------ |
| 1     | `2026-08-16-youtube-playlist-download-phase-1-page-size.md`        | A persisted, validated playlist page-size setting appears in Settings.                             | None                     |
| 2     | `2026-08-16-youtube-playlist-download-phase-2-expansion.md`        | The batch service can expand, deduplicate, page, and report playlist candidates.                   | Phase 1 contract/default |
| 3     | `2026-08-16-youtube-playlist-download-phase-3-preview-ui.md`       | The existing batch form renders paginated playlist previews; individual video enqueue still works. | Phases 1–2               |
| 4     | `2026-08-16-youtube-playlist-download-phase-4-selected-enqueue.md` | Users can select page-local rows, preserve per-video choices, and enqueue only selected videos.    | Phase 3                  |
| 5     | `2026-08-16-youtube-playlist-download-phase-5-verification.md`     | The complete workflow is verified, documented, and ready for handoff.                              | Phase 4                  |

Each phase ends with its focused tests passing and one commit. A phase is usable on its own even if later phases have not started: configuration is independently usable in Phase 1, the service contract is independently testable in Phase 2, preview is usable with individual actions in Phase 3, and bulk selection is added in Phase 4.

## Cross-phase acceptance criteria

- The supplied playlist URL can be submitted through the existing batch form.
- Playlist entries are expanded in order, deduplicated, and paginated with a default page size of 20.
- Only the current page performs full metadata/format extraction.
- Invalid entries remain visible while valid entries continue through the flow.
- Ready rows retain the existing per-video format picker and can be enqueued independently.
- Bulk enqueue creates one existing queue job per selected video and does not queue unchecked rows.
- Direct URL batches and individual video downloads remain unchanged.
- `uv run pytest`, `uv run ruff check .`, and `uv run ty check` pass before handoff.

## Execution rule

Read the relevant phase plan before implementation, complete its checklist in order, run its focused verification, and commit before moving to the next phase. Do not edit the original plan to track progress; use the phase plan’s checkboxes or the execution session’s task tracker.
