# YourTube Phase 7-10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the next YourTube milestone: fix subtitle/output-path failures, export subtitle sidecars as `.srt` plus `.txt` transcripts, expose richer stream metadata, replace the select-based picker with an Alpine-enhanced table UI, and add in-app completion notifications.

**Architecture:** Keep the current FastAPI + Jinja2 + HTMX application intact and layer the new work on top of existing route contracts. Backend correctness lands first in the downloader layer, then stream metadata grows additively, then the home-page fragment is refactored into an Alpine-managed table picker, and finally queue polling powers lightweight in-app completion toasts.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2, HTMX, Alpine.js, yt-dlp, ffmpeg, pytest, uv

---

## Why This Plan Exists

- Phase 6 delivered the editorial UI shell, but the downloader still has a real filesystem bug when subtitles are enabled with a relative output template.
- Users also want subtitle downloads to produce cleaner derived artifacts by default: English-first `.srt` subtitles plus plain-text transcripts without timestamps.
- The current home page renders the same raw format list twice and hides useful differences between video-only and audio-only streams.
- Users need clearer output-container expectations when mixing MP4, WebM, M4A, and Opus-based formats.
- The app currently has almost no browser-side state management; Alpine.js should be introduced narrowly where local UI state is a better fit than more HTMX round-trips.

## File Structure

```
yourtube/
├── app/
│   ├── main.py
│   ├── schemas.py
│   ├── routes/
│   │   ├── api.py
│   │   └── pages.py
│   ├── services/
│   │   ├── downloader.py
│   │   ├── error_mapper.py
│   │   └── queue.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── pages/
│   │   │   ├── home.html
│   │   │   └── queue.html
│   │   └── partials/
│   │       ├── info_result.html
│   │       ├── queue_rows.html
│   │       └── status_message.html
│   └── static/
│       ├── css/app.css
│       └── vendor/
│           ├── htmx.min.js
│           └── alpine.min.js         # new
├── tests/
│   ├── unit/
│   │   ├── test_downloader_format.py
│   │   ├── test_downloader_runtime_resolution.py
│   │   └── test_friendly_errors.py
│   └── integration/
│       ├── test_api_info.py
│       ├── test_pages.py
│       └── test_worker_pool.py
└── plans/
    ├── 2026-06-12-yourtube-design-phase-7-10.md
    ├── 2026-06-12-yourtube-design-phase-7.md
    ├── 2026-06-12-yourtube-design-phase-8.md
    ├── 2026-06-12-yourtube-design-phase-9.md
    └── 2026-06-12-yourtube-design-phase-10.md
```

Responsibilities:

- `app/services/downloader.py` owns output-template resolution, subtitle/transcript artifact generation, stream normalization, and expected-container inference.
- `app/main.py` remains a thin worker orchestrator; it should not grow path-resolution logic that belongs in the downloader service.
- `app/schemas.py` defines additive format metadata needed by the redesigned picker.
- `app/routes/api.py` and `app/routes/pages.py` expose richer stream metadata without breaking existing endpoints.
- `app/templates/partials/info_result.html` becomes the main stream-picker surface and Alpine state root.
- `app/templates/index.html`, `app/templates/pages/queue.html`, and `app/templates/partials/queue_rows.html` expose the toast region and completed-job markers needed for notifications.

## Phase Overview

### Phase 7

- Fix relative `output_template` handling so downloads and subtitle sidecars always land under the resolved downloads directory.
- When subtitles are enabled, use yt-dlp's default single-language English-first caption selection with auto-caption fallback, emit `.srt` sidecars, and derive sibling plain-text `.txt` transcripts.
- Add expected-container inference for selected stream pairs.
- Differentiate path/template failures from generic yt-dlp extraction failures.
- Keep all three changes in the downloader/error-mapper seam rather than testing them through `WorkerPool`.

See: `plans/2026-06-12-yourtube-design-phase-7.md`

### Phase 8

- Expand format metadata with stream typing and audio channel counts.
- Keep API changes additive and compatible with the current route set.
- Limit implementation to the `FormatInfo` contract, downloader normalization, and API regression coverage.
- Do not spend a task on route edits unless the repo has diverged from the current `normalize_formats(raw)` pass-through.
- Use yt-dlp metadata as the primary source of truth and the MartinEesmaa gist only as a labeling/reference aid.

See: `plans/2026-06-12-yourtube-design-phase-8.md`

### Phase 9

- Replace the select-based picker in the home-page lookup result with `Video Streams` and `Audio Streams` tables.
- Introduce Alpine.js for local UI state only: row selection, advanced-toggle state, and expected-container hint updates.
- Preserve HTMX submission and existing browser-facing route IDs.

See: `plans/2026-06-12-yourtube-design-phase-9.md`

### Phase 10

- Add in-app completion toasts driven by queue polling.
- Show each completed job notification once per page session.
- Keep notifications in-app only; do not add the browser Notification API.

See: `plans/2026-06-12-yourtube-design-phase-10.md`

## Core Design Rules

- Do not broaden Alpine.js into a full client-side rewrite.
- Do not break `POST /api/info`, `POST /downloads/form`, or the Phase 6 route set.
- Do not add server-side stream grouping before phase 9; phase 8 only enriches per-format metadata.
- Do not promise MP4 output for incompatible stream combinations; MKV fallback is valid and should be surfaced honestly.
- Do not hardcode container compatibility from the gist; use actual normalized yt-dlp metadata and small compatibility helpers in code.
- Keep tests narrow and phase-specific so each phase can be implemented and reviewed independently.

## Acceptance Criteria

- Enabling subtitles with a relative output template no longer produces permission-denied writes in the process working directory.
- Enabling subtitles yields best-effort English-first `.srt` subtitle export plus sibling plain-text `.txt` transcripts when captions exist, without failing the media download when captions are absent.
- The downloader can explain when a selected stream pair is expected to merge as MP4 versus fallback to MKV.
- `/api/info` and `/info/form` expose enough metadata to render distinct video/audio stream tables.
- The home page shows table-based stream picking, a collapsed advanced section, and an expected-container hint without replacing HTMX.
- The browser shows exactly one in-app toast per completed job per page session while queue polling continues to drive updates.

## Implementation Order

1. Implement Phase 7 and land all backend/path tests first.
2. Implement Phase 8 and verify the enriched format metadata via unit and API tests.
3. Implement Phase 9 and verify the fragment markup plus Alpine asset loading.
4. Implement Phase 10 and verify notification behavior against queue polling.

## Testing Strategy

- Phase 7: `uv run pytest tests/unit/test_downloader_runtime_resolution.py tests/unit/test_downloader_format.py tests/unit/test_friendly_errors.py -v`
- Phase 8: `uv run pytest tests/unit/test_downloader_format.py tests/integration/test_api_info.py -v`
- Phase 9: `uv run pytest tests/integration/test_pages.py -v`
- Phase 10: `uv run pytest tests/integration/test_pages.py tests/integration/test_worker_pool.py -v`

## Commit Strategy

- One commit per task in each phase plan.
- Keep commit messages scoped to the user-visible change:
  - `fix: resolve relative output templates under downloads dir`
  - `feat: enrich stream metadata for table picker`
  - `feat: add alpine-powered stream tables`
  - `feat: add in-app completion notifications`
