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

**Phase 6 overrides of the Global Constraints:** "Old UI keeps working until Phase 6" and "Old HTML routes keep FastAPI's default errors" end here. Every non-`/api` path except `/health` now goes to the SPA catch-all.

**Verified before replanning (2026-11-17, at `c645d31`):** with the Task 6.1 deletions and the `main.py` edit applied, ruff and ty pass and server coverage is 96%. Exactly three existing tests fail, and Step 1 below covers each one. The `playlist_page_size` edits break four more test files, also covered below.

### Task 6.1: Serve the SPA at `/` and delete the old UI

**Files:**

- Delete: `apps/server/app/routes/` (whole package), `apps/server/app/templates/`, `apps/server/app/static/`, `apps/server/app/services/{batch_preview,preview,enqueue_intake,stream_selection}.py`, `apps/server/tests/integration/{test_pages,test_partials}.py`, `apps/server/tests/unit/{test_batch_preview,test_preview,test_enqueue_intake,test_stream_selection}.py`
- Modify:
  - `apps/server/app/main.py`: drop the `pages_router` import and `include_router`, the `/static` mount and the `StaticFiles` import
  - `apps/server/app/services/settings.py`: drop `playlist_page_size` from `RuntimeSettings`, `resolve_runtime_settings` (field, parsing, docstring bullet), `SETTINGS_CATALOG` and `_validate`
  - `apps/server/app/services/downloader.py`: `run_download` always installs the output guard (see Interfaces); fix the `resolve_output_template` docstring
  - `apps/server/app/schemas.py`: reword the old-UI comment on `JobCreate._check_strict_bitrate`
  - `apps/server/tests/api/test_spa.py`, `apps/server/tests/api/test_errors.py`, `apps/server/tests/api/test_settings_api.py`
  - `apps/server/tests/unit/{test_settings,test_settings_runtime_resolution,test_downloader_progress,test_quality}.py`
  - `apps/server/pyproject.toml` + `apps/server/uv.lock` (via `uv remove`)
  - `apps/web/e2e/app.ts` (`APP = "/"`, drop the "Phase 6 changes this" comment)

**Interfaces:**

- `/` returns `index.html`. `/queue`, `/library` and `/settings` return `index.html` too: hash routing opens the app on Library, which is acceptable. `/downloads/{id}/file` is gone (it has no extension, so the catch-all returns `index.html`); the UI already uses `/api/downloads/{id}/file`.
- Stale `playlist_page_size` rows in existing databases are ignored, because `get_all_settings` returns catalog keys only. No migration.
- **Absolute output templates (owner decision, 2026-11-17):** `run_download` always installs `output_dir_guard`, so every download must land inside the downloads folder. The JSON API already rejects absolute templates. An old row with an absolute template that points outside the folder now fails on retry with the guard's "downloads folder" error. That is accepted.
- `jinja2` and `python-multipart` come off the direct dependencies. They stay installed as transitive dependencies of `fastapi[standard]`, which is fine: no app code imports them.
- `DownloadCreate` stays lenient about `audio_bitrate`, and `cap_format_options` stays tolerant. Rows the old UI queued may still hold free-form bitrates, and the worker must not crash on them.

- [ ] **Step 1: Update tests first**
  - `tests/api/test_spa.py`:
    - Replace `test_spa_does_not_shadow_old_pages` with `test_root_serves_index` (`client.get("/").text == INDEX`) and `test_old_page_paths_serve_index` (`/queue`, `/library` and `/settings` each `== INDEX`).
    - Add `test_old_file_route_serves_index`: `client.get("/downloads/1/file")` has status 200, `content-type` starts with `text/html`, and `.text == INDEX`.
    - In `test_spa_without_dist_returns_404_hint`, replace `assert "<html" in client_no_dist.get("/queue").text` with `assert client_no_dist.get("/").status_code == 404`.
  - `tests/api/test_errors.py`: delete `test_old_routes_keep_default_errors`. The `mini` app's `/old` assertion already covers default errors for non-API paths.
  - `tests/api/test_settings_api.py`: replace `test_settings_put_keeps_playlist_page_size` with `test_settings_ignores_stale_playlist_page_size`. Store a `playlist_page_size` row (`db_session_visible.add(Setting(key="playlist_page_size", value="30")); db_session_visible.commit()`), then assert that `client.get("/api/settings").json()` has no `playlist_page_size` key and still returns 200.
  - `tests/unit/test_settings.py`:
    - Drop `playlist_page_size` from `DEFAULT_CATALOG`.
    - Delete `test_playlist_page_size_rejects_invalid_values` and `test_playlist_page_size_accepts_boundary_values`.
    - In `test_set_settings_batch_validates_each_value`, use `{"proxy_url": "http://p:1", "max_concurrent": "9"}` and assert `get_setting(db_session, "proxy_url") == ""` afterwards. The old invalid value, `playlist_page_size: "51"`, stops being validated.
    - Add `test_playlist_page_size_not_in_catalog`: `"playlist_page_size" not in get_all_settings(db_session)`.
  - `tests/unit/test_settings_runtime_resolution.py`:
    - Delete `test_resolve_runtime_settings_normalizes_invalid_stored_playlist_page_size` and its parametrize decorator.
    - Remove the `playlist_page_size` seed and assertions at lines 35, 48 and 55.
    - Add `assert not hasattr(resolved, "playlist_page_size")` to the blank-values test.
  - `tests/unit/test_downloader_progress.py`: rename `test_run_download_guards_relative_templates_only` to `test_run_download_always_guards`. The absolute-template case now asserts `"match_filter" in ...`.
  - `tests/unit/test_quality.py`: rename `test_old_ui_payload_accepts_free_form_bitrate` to `test_stored_free_form_bitrate_is_tolerated`. Reword the comment: rows queued before the strict API may hold free-form bitrates, and the worker must not crash on them.
- [ ] **Step 2:** `cd apps/server && uv run pytest tests/api/test_spa.py tests/api/test_settings_api.py tests/unit/test_settings.py tests/unit/test_settings_runtime_resolution.py tests/unit/test_downloader_progress.py -v` → FAIL (root/old-path tests, the settings catalog tests and the always-guard test).
- [ ] **Step 3: Delete and edit** the files listed.
  - `run_download`: replace the `if not (output_template and Path(output_template).is_absolute()):` block with unconditional `guard = output_dir_guard(output_dir)` and `ydl_opts["match_filter"] = guard`. Drop the `| None` on `guard` if it is now always set, and anything that branches on it being `None`.
  - Docstring for `resolve_output_template`: absolute templates are returned untouched, but `run_download`'s guard still refuses any final path outside the downloads folder.
  - Dependencies: `cd apps/server && uv remove jinja2 python-multipart` (this updates `uv.lock`).
- [ ] **Step 4: Leftover grep**

  Run: `rg -n -i "jinja|htmx|alpine|playlist_page_size|batch_preview|stream_selection|enqueue_intake|pages_router|/static|old ui|old html|old-ui" apps/ -g '!apps/server/alembic/**' -g '!apps/server/uv.lock' -g '!apps/server/README.md'`
  Expected: no output. (`apps/server/README.md` is rewritten in Task 6.3. "Output template" matches are legitimate, which is why the pattern does not include `templates`.)

- [ ] **Step 5:** `pnpm check && pnpm e2e` → PASS, coverage ≥ 50. `pnpm check` already runs `typegen:check`. The OpenAPI schema does not change, because the pages router was `include_in_schema=False`.
- [ ] **Step 6: Commit** `git add -A && git commit -m "feat!: serve the Svelte app at / and remove the Jinja/HTMX UI"`

### Task 6.2: Design review passes

**Files:** Modify: whatever the passes find under `apps/web/src/` (and `apps/web/e2e/*.spec.ts` if copy changes break selectors); `.gitignore` (add `.impeccable/`).

**How to get every state in a real browser without YouTube:** use the e2e server, which stubs yt-dlp and seeds data.

```bash
pnpm build && rm -rf tmp/e2e && cd apps/server && \
  YT_DATA_DIR=$PWD/../../tmp/e2e/data YT_DOWNLOADS_DIR=$PWD/../../tmp/e2e/downloads \
  YT_DATABASE_URL=sqlite:///$PWD/../../tmp/e2e/data/yourtube.db \
  YT_PROXY_URL= YT_COOKIES_PATH= YT_WORKERS_ENABLED=1 \
  uv run uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8100
```

- Library with data: `http://127.0.0.1:8100/#/` (seeded "Seeded video").
- Single video: fetch `https://e2e.test/video`.
- Playlist with a below-cap entry and an unavailable entry: fetch `https://e2e.test/playlist`, then open an override panel.
- Queue: the seeded "Slow video", plus anything queued above. Completion toasts appear when a fake download finishes.
- Error state: fetch any other URL (the stub raises "not stubbed").
- Empty states: restart the server with a fresh `tmp/e2e` and delete the seeded rows from Library and Queue in the UI.

- [ ] **Step 1: Setup.** Run `/Users/lanh/.agents/skills/impeccable/scripts/impeccable context` once from the repo root, then read `reference/critique.md`, `reference/audit.md` and `reference/polish.md`. Read `reference/craft-floor.md` right before the first `.svelte` or `app.css` edit.
- [ ] **Step 2: Critique, then audit.** Cover Library, Queue, Settings, single video, playlist with the override panel open, toasts, empty states and error states, at 1280 and 1440 widths in both themes. Record findings with impeccable's P0–P3 tags. Critique reports go to `.impeccable/critique/`. Add `.impeccable/` to `.gitignore`: they are working notes, not repo content.
- [ ] **Step 3: Fix.** Fix every P0 and P1 finding and every craft-floor violation. P2/P3 findings are fixed when the change is small and stays inside `PRODUCT.md` / `DESIGN.md`; otherwise list them. Do not change product behaviour, the Global Constraints (red-only accent, amber only for below-cap, dark default theme) or copy that states facts, unless the owner approves.
- [ ] **Step 4: Polish**, then re-check the touched screens once at both widths and in both themes. Batch the fixes before re-checking; don't screenshot after every tweak.
- [ ] **Step 5:** `pnpm check && pnpm e2e` → PASS. If a copy change broke an e2e selector, update the spec to the new copy, not the copy to the old spec.
- [ ] **Step 6: Commit** `git add -A && git commit -m "polish: impeccable critique, audit and polish fixes"`. The commit body lists any P0–P2 finding deliberately left, with a reason.

### Task 6.3: README, Docker and CI final pass

**Files:** Modify: `README.md`, `apps/server/README.md`, `Dockerfile`, `compose.yaml` (comments only, if anything is stale), `.github/workflows/quality.yml`. `.dockerignore` only if the check in Step 3 finds something.

- [ ] **Step 1: Root README.**
  - Cover: setup (`cp .env.example .env`, `pnpm install`, `cd apps/server && uv sync --dev`); `pnpm dev` (UI on http://localhost:5173 with `/api` proxied, API on :8000); `pnpm build && pnpm start` (everything on :8000); `pnpm check`, `pnpm e2e` and `pnpm typegen`; the repo layout (`apps/server`, `apps/web`); `.env` at the repo root; quality caps (`best` / 2160 / 1440 / 1080 / 720 / 480 / audio, short side, default 1080) and playlist checking (selected entries only, 2 at a time, 500-entry limit) in a few lines.
  - Remove: the HTMX bullet, "Paginated YouTube playlist preview", the "(Phase 5)" labels, and `pnpm dev # http://127.0.0.1:8000`.
- [ ] **Step 2: `apps/server/README.md`.**
  - Intro: "JSON API under `/api`; serves the built web app from `apps/web/dist`", not "the current Jinja/HTMX UI".
  - Layout: drop `routes/`, `templates/` and `static/`; add `api/` (JSON routes, SPA serving, error bodies).
  - `YT_WEB_DIST_DIR`: drop "(unused until Phase 2)".
  - Tests: mention `tests/api/`.
- [ ] **Step 3: Docker.**
  - Fix the Dockerfile header: it says "Single-stage build", but the build is multi-stage (`web-build` then `runtime`).
  - Confirm nothing references `app/static` or templates (expected: nothing does).
  - Confirm the runtime image has Node 24 (`COPY --from=node-runtime`) and ffmpeg.
  - Confirm `.dockerignore`'s `dist/` does not matter: `apps/web/dist` is built inside the image.
- [ ] **Step 4: CI.** In `quality.yml`, remove the stale comment "Server coverage threshold is low for now; increase to 80 after Phase 4". The gate stays at 50 per the Global Constraints. Nothing else changes.
- [ ] **Step 5: Verify.** Docker Desktop must be running (it was not on 2026-11-17), and port 8000 must be free (stop `pnpm start` / `pnpm dev`).

  Run: `docker compose build && docker compose up -d && for i in $(seq 1 30); do curl -fs localhost:8000/health && break; sleep 2; done && curl -fs localhost:8000/ | grep -q '<div id="app"' && curl -fs localhost:8000/queue | grep -q '<div id="app"'; rc=$?; docker compose down; exit $rc`
  Expected: exit 0.
  Run: `pnpm check && pnpm e2e`
  Expected: PASS.

- [ ] **Step 6: Commit** `git add -A && git commit -m "docs: README and Docker for the Svelte app"`
