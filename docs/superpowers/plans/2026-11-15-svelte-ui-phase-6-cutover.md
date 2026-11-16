# Phase 6: Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The new UI is the only UI, served at `http://localhost:8000/`; the Jinja/HTMX/Alpine code, old CSS, paged batch preview and `playlist_page_size` are gone; the screens have been through impeccable's critique, audit and polish; README and Docker describe the new setup.

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 6: Cutover". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** Phase 5.

**Tasks:** Task 6.1 Serve the SPA at `/` and delete the old UI, Task 6.2 Design review passes, Task 6.3 README, Docker and CI final pass.

## Architecture and stack (from the parent plan)

**Architecture:** The FastAPI backend moves to `apps/server` and gains JSON routes under `/api`. The Svelte app lives in `apps/web` and calls them through `openapi-fetch`, with types generated from FastAPI's OpenAPI schema and checked for drift. In production FastAPI also serves the built SPA, so it is still one process on one port. The work is built feature by feature: each phase adds the API and the screens for one feature, and the old UI keeps working until the last phase deletes it.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, yt-dlp, uv, ruff, ty, pytest. Node 24, pnpm 12.9.1, Svelte 5 (runes), Vite 8, `@sveltejs/vite-plugin-svelte` 7, Tailwind CSS 4 (`@tailwindcss/vite`), TypeScript (`svelte-check --tsgo`), Biome 2.6, Vitest 5, Playwright 1.65, `openapi-typescript` 7, `openapi-fetch` 0.17, `@fontsource`.

## Global Constraints (from the parent plan)

- **Old UI keeps working until Phase 6.** No phase before 6 removes or changes the behaviour of a Jinja page, an HTMX route or `/downloads/{id}/file`. The full old test suite stays green until Phase 6 deletes the old tests together with the old code.
- **Where the SPA is served:** in Phases 2–5 the built SPA is served at `/app` (hash routes such as `/app#/queue`), because the Jinja pages still own `/`, `/queue`, `/library` and `/settings`. Phase 6 serves it at `/`. Vite `base` stays `/`; assets live at `/assets/*` and do not collide with the old `/static/*`.
- **SPA serving rules (spec):** real files in `apps/web/dist` by path; `index.html` for app paths; 404 for a missing path that has a file extension; 404 JSON error for any unknown `/api/...` path. `/health` stays at `/health`.
- **Error body** for every `/api` error: `{"error": {"code": str, "message": str}}`. The web app may show `message`. Old HTML routes keep FastAPI's default errors.
- **Pydantic schemas in `app/schemas.py` are the only response models.** Routes never return ORM rows.
- **Quality caps:** exactly `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio`. Default in the UI: `1080` ("Up to 1080p"). The cap compares against the **short side** (min of width and height). Exact format ids win over the cap.
- **Batch limit:** 500 entries per fetch; extra entries are dropped and counted in `skipped`, which the UI shows as "Skipped N".
- **Playlist checking:** from the browser, at most `CHECK_CONCURRENCY = 2` lookups at a time (the spec allows 2–3; 2 because playlist 403s were just fixed). Only selected entries are looked up. Leaving the page stops checking.
- **Theme:** `dark` (default) | `light` | `system`, in `localStorage` key `theme`, applied by an inline script in `index.html` before first paint. Not `system` by default.
- **Session storage key for completion toasts:** `yt-seen-completed-jobs` (same key as today, ids as strings).
- **No runtime CDN.** Fonts come from `@fontsource` packages; nothing loads from Google Fonts.
- **Red is the only accent.** Amber only for "below your cap"; an error tone for failures. Exact values come from `DESIGN.md` and must pass WCAG AA in both themes.
- **Computer only.** Design at 1280 and 1440 widths. Narrow windows may scroll but must not overlap or clip controls.
- **Not used:** Paraglide, PWA, SvelteKit, WebSocket/SSE, server-side playlist checking, taste-skill (`design-taste-frontend`) for app screens.
- **`.env` stays at the repo root.** `apps/server/app/config.py` reads it by absolute path. Relative `YT_DATA_DIR` / `YT_DOWNLOADS_DIR` / `YT_COOKIES_PATH` resolve against the repo root, so `./tmp/data` keeps meaning `<repo>/tmp/data`.
- **Checks before every commit (from Phase 2 on):** `pnpm check` must pass. In Phase 1 that is `pnpm check` with only server checks.
- **UI work:** before any edit to a `.svelte` file or `app.css`, read impeccable's `reference/craft-floor.md` (`/Users/lanh/.agents/skills/impeccable/`) and follow `PRODUCT.md` and `DESIGN.md` at the repo root.
- **Coverage gate:** `pytest --cov=app --cov-fail-under=50` stays in `pnpm check` and CI.

## Review Focus for this phase

None of the parent plan's Review Focus items is owned by this phase. Still read the parent's list: earlier phases' tests must stay green.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 6: Cutover

**Usable result:** the new UI is the only UI, served at `http://localhost:8000/`; the Jinja/HTMX/Alpine code, old CSS, paged batch preview and `playlist_page_size` are gone; the screens have been through impeccable's critique, audit and polish; README and Docker describe the new setup.

### Task 6.1: Serve the SPA at `/` and delete the old UI

**Files:**
- Delete: `apps/server/app/routes/` (pages router), `apps/server/app/templates/`, `apps/server/app/static/`, `apps/server/app/services/{batch_preview,preview,enqueue_intake,stream_selection}.py`, `apps/server/tests/integration/{test_pages,test_partials}.py`, `apps/server/tests/unit/{test_batch_preview,test_preview,test_enqueue_intake,test_stream_selection}.py`
- Modify: `apps/server/app/main.py` (drop pages router and `/static` mount), `apps/server/app/services/settings.py` (drop `playlist_page_size` from `SETTINGS_CATALOG`, `RuntimeSettings`, `_validate`), `apps/server/tests/unit/{test_settings,test_settings_runtime_resolution}.py`, `apps/server/tests/api/test_spa.py`, `apps/server/pyproject.toml` (drop `jinja2`, `python-multipart` from dependencies), `uv.lock`, `apps/web/e2e/app.ts` (`APP = "/"`)

**Interfaces:**
- `/` now returns `index.html`; `/queue`, `/library`, `/settings` return `index.html` too (hash routing means the app opens on Library; acceptable). `/downloads/{id}/file` is gone; the UI uses `/api/downloads/{id}/file`.
- Stale `playlist_page_size` rows in existing databases are ignored by `get_all_settings` (catalog keys only); no migration.

- [ ] **Step 1: Update tests first**: `test_spa.py` — `test_root_serves_index` (`client.get("/").text == INDEX`), `test_old_page_paths_serve_index` (`/queue`), `test_old_file_route_gone` (`/downloads/1/file` has no extension, so it returns `index.html` as `text/html`, not a file). Settings tests: `playlist_page_size` absent from `get_all_settings` and from `RuntimeSettings`.
- [ ] **Step 2:** `cd apps/server && uv run pytest tests/api/test_spa.py tests/unit/test_settings.py -v` → FAIL.
- [ ] **Step 3: Delete and edit** the files listed. Grep for leftovers: `rg -n "templates|htmx|alpine|playlist_page_size|batch_preview|stream_selection|enqueue_intake" apps/` → nothing outside migrations and docs.
- [ ] **Step 4:** `pnpm typegen && pnpm check && pnpm e2e` → PASS, coverage ≥ 50.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat!: serve the Svelte app at / and remove the Jinja/HTMX UI"`

### Task 6.2: Design review passes

**Files:** Modify: whatever the passes find under `apps/web/src/`

- [ ] **Step 1:** Run impeccable `critique`, then `audit`, then `polish` on every screen (Library, Queue, Settings, single video, playlist with override panel open, toasts, empty and error states) in a real browser at 1280 and 1440 widths, both themes. Fix every finding at or above the craft floor; list any deliberately left with a reason in the commit message.
- [ ] **Step 2:** `pnpm check && pnpm e2e` → PASS.
- [ ] **Step 3: Commit** `git add -A && git commit -m "polish: impeccable critique, audit and polish fixes"`

### Task 6.3: README, Docker and CI final pass

**Files:** Modify: `README.md`, `Dockerfile`, `compose.yaml`, `.dockerignore`, `.github/workflows/quality.yml`

- [ ] **Step 1: README** — setup (`pnpm install`, `cd apps/server && uv sync --dev`), `pnpm dev` (UI on :5173, API on :8000), `pnpm build && pnpm start` (all on :8000), `pnpm check`, `pnpm e2e`, `pnpm typegen`, repo layout, `.env` at the repo root, quality caps and playlist checking in a few lines. Remove HTMX/Alpine/Jinja mentions.
- [ ] **Step 2: Docker** — drop anything left for `app/static` or templates; confirm the image has Node 24 and ffmpeg.
- [ ] **Step 3: Verify**

Run: `docker compose build && docker compose up -d && sleep 5 && curl -fs localhost:8000/health && curl -fs localhost:8000/ | grep -q '<div id="app"' && docker compose down`
Expected: exit 0.
Run: `pnpm check && pnpm e2e`
Expected: PASS.

- [ ] **Step 4: Commit** `git add -A && git commit -m "docs: README and Docker for the Svelte app"`
