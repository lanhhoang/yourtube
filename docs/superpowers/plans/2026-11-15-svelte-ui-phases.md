# Svelte UI: Phase Index

The parent plan `2026-11-15-svelte-ui.md` is split into six phases, from simplest to most complex. Each phase ends with something the owner can use, and each is executed and reviewed on its own. The parent plan stays the reference: every phase file copies its phase's tasks verbatim, plus the parent's Global Constraints and the Review Focus items that phase owns.

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

| # | Phase | Plan | Parent tasks | Usable result |
| - | ----- | ---- | ------------ | ------------- |
| 1 | Repo layout | `…-phase-1-repo-layout.md` | 1.1–1.3 | Old app runs from `apps/server` via `pnpm dev` / `pnpm start` / `pnpm check` on the latest Python dependencies, same `.env` and data; CI and Docker green |
| 2 | Web app shell and design foundation | `…-phase-2-web-shell.md` | 2.1–2.5 | Svelte shell (top bar, rail, dark/light/system) in the approved design, at `:5173` in dev and `/app` in prod; typed client, drift check, e2e harness |
| 3 | Library, Queue and Settings | `…-phase-3-library-queue-settings.md` | 3.1–3.6 | Browse/search/download/delete library, live queue with cancel/retry/dismiss and toasts, settings — in the new UI |
| 4 | Single video with quality cap | `…-phase-4-single-video.md` | 4.1–4.4 | Fetch one video, pick a cap or exact format, add to queue; downloads at the right quality |
| 5 | Playlists and multiple URLs | `…-phase-5-playlists.md` | 5.1–5.3 | Whole playlist at once, one cap, every selected video checked with badges, per-video overrides, add all; new UI does everything the old one does |
| 6 | Cutover | `…-phase-6-cutover.md` | 6.1–6.3 | New UI at `/`, old UI and paged preview removed, design polished, README and Docker updated |

## Order and dependencies

```
Phase 1 ──► Phase 2 (owner approves PRODUCT.md, then picks visual direction) ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
```

- Strictly sequential: each phase builds on the files and API of the previous one.
- **Owner checkpoints** are in Phase 2 (Tasks 2.3 and 2.4). Phase 1 and Task 2.1–2.2 don't depend on them; no screen is styled before both approvals.
- **Old UI stays usable through Phase 5.** The new UI runs beside it at `/app` (prod) or `:5173` (dev). Phase 3 can't add downloads yet; Phase 4 can't do playlists yet; in those gaps the old UI covers it.
- Phases 2–6 each extend the same `apps/server/tests/e2e_server.py` stubs and add one e2e spec. The `APP` constant in `apps/web/e2e/app.ts` switches from `/app` to `/` in Phase 6.

## Why this order

- **1 Repo layout** is a pure move plus a dependency bump: no behaviour change, smallest risk, and every later phase needs the new paths. The bump (Task 1.3) comes after the move so each commit has one cause, and before Phase 2 so the old test suite guards it and the generated API types are built on the shipped versions.
- **2 Shell** sets up the whole toolchain and the visual direction once, so later phases only add screens.
- **3 Library/Queue/Settings** are read-mostly screens over existing services; only retry/dismiss are new backend behaviour.
- **4 Single video** adds the quality cap (migration + yt-dlp format logic) and the first write flow.
- **5 Playlists** is the most complex: browser-side checking with concurrency, badges, overrides and bulk enqueue, all on top of Phase 4's cap and enqueue API.
- **6 Cutover** deletes code and polishes; it's last because it's the only phase that removes the fallback.

## Spec coverage by phase

| Spec item | Phase |
| --------- | ----- |
| `apps/server` + `apps/web` layout, pnpm root, `compose.yaml`, `.env` at root, `tmp/` data | 1, 2 |
| `pnpm dev` / `pnpm check` (Biome, svelte-check, Vitest, ruff, ty, pytest, drift check) | 1, 2 |
| Typed client from OpenAPI with drift check | 2 |
| FastAPI serves built SPA, one process/port, Docker web build stage, Node 24 | 2, 6 |
| `/api` error body, SPA serving rules | 2 |
| Dark default + light + system theme, pre-paint | 2 |
| impeccable PRODUCT.md / DESIGN.md checkpoints, bundled fonts | 2 |
| Top bar (URL field, Fetch, proxy/cookies menu, multi-URL), left rail with queue count | 2, 3 |
| Library grid, chips, search, in-progress cards, download/delete | 3 |
| Queue, cancel, retry, dismiss, 2 s poll, completion toasts | 3 |
| Settings and diagnostics | 3 |
| Quality cap column, short-side rule, cap → selector, exact ids win | 4 |
| Enqueue one / many (JSON, per-job values) | 4 |
| Single-video watch layout, quality dropdown, exact picker, Advanced | 4 |
| `watch?v=X&list=Y` opens the video with "Open playlist" | 4 |
| List sources: whole list, no paging, 500 limit with "Skipped N" | 4 |
| Playlist view: checking 2 at a time, Add disabled until done, badges, header subtitles/Advanced, side-panel override, stop on leave | 5 |
| Remove Jinja/HTMX/Alpine, old CSS, paged preview, `playlist_page_size` | 6 |
| critique / audit / polish at 1280 and 1440, both themes | 6 |
| Python dependencies at latest (owner request, not in spec) | 1 |
| Tests: JSON API tests replace HTML tests, Vitest logic, Playwright e2e (5 flows), coverage ≥ 50 | 2–6 |
