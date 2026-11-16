# Phase 2: Web app shell and design foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pnpm dev` opens the new Svelte shell at `http://localhost:5173` — top bar with the URL field, left rail (Library, Queue, Settings), dark by default with light/system switch — styled from an owner-approved `PRODUCT.md` and `DESIGN.md`. `pnpm build && pnpm start` serves the same shell at `http://localhost:8000/app` while the old UI still runs at `/`. `pnpm check` covers Biome, svelte-check, Vitest, the type-drift check and all server checks; `pnpm e2e` runs a theme-switch test.

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 2: Web app shell and design foundation". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** Phase 1.

**Tasks:** Task 2.1 API foundation on the server: error body, SPA serving, OpenAPI export, Task 2.2 Web package scaffold, tooling, typed client and type-drift check, Task 2.3 Owner checkpoint 1 — `PRODUCT.md`, Task 2.4 Owner checkpoint 2 — visual direction and `DESIGN.md`, Task 2.5 App shell (top bar, left rail, theme) and e2e harness.

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

1. **A clone where the web app hasn't been built.** `pnpm start` or a bare `uvicorn` with no `apps/web/dist` must still start, serve the old UI, the API and `/health`, and answer `/app` with a plain 404 that says to run `pnpm build`. It must not crash at import. Test: `test_spa_without_dist_returns_404_hint` (Task 2.1).
4. **Late replies after the person moved on.** They fetch URL A, then URL B before A answers; or they leave a playlist page while lookups are running. A's answer must not replace B's view, and lookups finishing after leaving must not start new ones or change the page. Tests: `latest` test (Task 2.2), `checker ignores results after stop` (Task 5.2).

The numbers are the parent plan's Review Focus numbers. The tests that pin them are in this phase's tasks.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 2: Web app shell and design foundation

**Usable result:** `pnpm dev` opens the new Svelte shell at `http://localhost:5173` — top bar with the URL field, left rail (Library, Queue, Settings), dark by default with light/system switch — styled from an owner-approved `PRODUCT.md` and `DESIGN.md`. `pnpm build && pnpm start` serves the same shell at `http://localhost:8000/app` while the old UI still runs at `/`. `pnpm check` covers Biome, svelte-check, Vitest, the type-drift check and all server checks; `pnpm e2e` runs a theme-switch test.

### Task 2.1: API foundation on the server: error body, SPA serving, OpenAPI export

**Files:**
- Create: `apps/server/app/api/__init__.py`, `apps/server/app/api/errors.py`, `apps/server/app/api/spa.py`, `apps/server/app/openapi_export.py`
- Modify: `apps/server/app/main.py`, `apps/server/app/routes/pages.py` (`APIRouter(include_in_schema=False)` only)
- Test: `apps/server/tests/api/__init__.py`, `apps/server/tests/api/test_errors.py`, `apps/server/tests/api/test_spa.py`

**Interfaces:**
- `class ApiError(Exception): __init__(self, status_code: int, code: str, message: str)`.
- `def install_error_handlers(app: FastAPI) -> None` — for requests whose path starts with `/api/`: `ApiError` → its status + error body; `HTTPException` → its status, code `http_<status>`, message = `detail` if it is a string else `"Request failed."`; `RequestValidationError` → 422, code `invalid_request`, message = first error's `msg` prefixed with its field path (`"jobs.0.url: Field required"`). Other paths keep FastAPI defaults.
- `api_router = APIRouter(prefix="/api")`; its last route is `@api_router.api_route("/{path:path}", methods=[all], include_in_schema=False)` → `ApiError(404, "not_found", "No such API endpoint.")`. Later phases include their routers **before** this catch-all (keep the catch-all at the bottom of `api/__init__.py`).
- `spa_router` (in `api/spa.py`): `GET /{path:path}`, `include_in_schema=False`, registered **last** in `main.py` (after the pages router). Rules, with `dist = settings.web_dist_dir`: no `dist/index.html` → 404 `text/plain` "Web app not built. Run `pnpm build`."; path resolves to an existing file inside `dist` (reject anything that resolves outside) → `FileResponse`; last segment contains a `.` → 404; otherwise `dist/index.html`. In Phases 2–5 this makes `/app` (and `/app/anything`) return `index.html` because the Jinja routes still own `/`, `/queue`, `/library`, `/settings`.
- `python -m app.openapi_export` prints `json.dumps(app.openapi(), indent=2, sort_keys=True)` to stdout. Importing `app.main` must not start the lifespan.

- [ ] **Step 1: Write the failing tests**

`test_errors.py`:
```python
def test_unknown_api_path_returns_error_body(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "No such API endpoint."}}

def test_old_routes_keep_default_errors(client):
    r = client.get("/downloads/999999/file")
    assert r.status_code == 404 and "error" not in r.json()
```
Add a fixture router in the test that raises `ApiError(409, "busy", "Busy.")` and a validation failure; assert both bodies.

`test_spa.py` (point `settings.web_dist_dir` at a `tmp_path` with `index.html`, `assets/a.js`):
```python
def test_spa_serves_index_for_app_paths(client): assert client.get("/app").text == INDEX
def test_spa_serves_real_files(client): assert client.get("/assets/a.js").text == JS
def test_spa_missing_file_with_extension_404(client): assert client.get("/assets/b.js").status_code == 404
def test_spa_does_not_shadow_old_pages(client): assert "<html" in client.get("/queue").text and client.get("/queue").text != INDEX
def test_spa_blocks_traversal(client): assert client.get("/..%2f..%2fpyproject.toml").status_code == 404
def test_spa_without_dist_returns_404_hint(client_no_dist):
    r = client_no_dist.get("/app"); assert r.status_code == 404 and "pnpm build" in r.text
def test_openapi_export_prints_schema(capsys): ...  # run module main(); json.loads(out)["openapi"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd apps/server && uv run pytest tests/api -v`
Expected: FAIL (module `app.api` not found).

- [ ] **Step 3: Implement** `api/errors.py`, `api/__init__.py`, `api/spa.py`, `openapi_export.py`; in `main.py` call `install_error_handlers(app)`, include `api_router`, then the pages router, then `spa_router`.

- [ ] **Step 4: Run the server checks**

Run: `pnpm check`
Expected: PASS, including every old test.

- [ ] **Step 5: Commit**

```bash
git add -A apps/server && git commit -m "feat(server): /api error body, SPA serving and OpenAPI export"
```

### Task 2.2: Web package scaffold, tooling, typed client and type-drift check

**Files:**
- Create: `apps/web/{package.json,index.html,vite.config.ts,svelte.config.js,tsconfig.json,tsconfig.node.json}`, `apps/web/scripts/typegen.ts`, `apps/web/src/{main.ts,App.svelte,app.css}`, `apps/web/src/lib/{api.ts,api.gen.ts,errors.ts,latest.ts,router.ts,router.svelte.ts,theme.ts}`, `apps/web/public/favicon.svg` (copy of `apps/server/app/static/assets/favicon.svg`), `biome.json`, `vitest.config.ts`
- Modify: root `package.json` (final scripts and devDeps), `.gitignore` (`node_modules/`, `apps/web/dist/`, `test-results/`, `playwright-report/`, `.svelte-check/`), `.github/workflows/quality.yml`, `Dockerfile`
- Test: `apps/web/test/{router,theme,errors,latest}.test.ts`

**Interfaces:**
- Root scripts (final; later phases don't edit them):
  ```json
  {
    "dev": "pnpm -r --parallel --filter @app/server --filter @app/web dev",
    "build": "pnpm --filter @app/web build",
    "start": "pnpm --filter @app/server start",
    "typegen": "pnpm --filter @app/web typegen",
    "e2e": "pnpm --filter @app/web e2e",
    "format": "biome format --write .",
    "format:check": "biome format .",
    "lint": "biome lint .",
    "typecheck": "pnpm --filter @app/web typecheck",
    "test": "vitest run",
    "check": "pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm --filter @app/web typegen:check && pnpm --filter @app/server check"
  }
  ```
  Root devDeps: `@biomejs/biome@^2.6.7`, `vitest@^5.1.0`, `@types/node@^24`, `tsx@^4.23`.
- `@app/web` scripts: `dev: vite`, `build: vite build`, `typecheck: svelte-check --tsgo --fail-on-warnings && tsc -p tsconfig.node.json`, `typegen: tsx scripts/typegen.ts`, `typegen:check: tsx scripts/typegen.ts --check`, `e2e: playwright test`. devDeps as apprendre minus Paraglide/PWA/Hono: `svelte@^5.57.3`, `vite@^8.3.8`, `@sveltejs/vite-plugin-svelte@^7.3.1`, `tailwindcss@^4.3.5`, `@tailwindcss/vite@^4.3.5`, `svelte-check@^4.7.8`, `typescript@~6.0.3`, `@typescript/native@npm:typescript@^7.0.2`, `openapi-typescript@^7.13.0`, `@playwright/test@^1.65.1`. dependency: `openapi-fetch@^0.17.0`. If pnpm refuses a fresh release (minimum release age), add `minimumReleaseAgeExclude` entries as apprendre does.
- `vite.config.ts`: plugins `tailwindcss()`, `svelte()`; `test: { include: ["test/**/*.test.ts"] }`; dev proxy `/api` and `/health` → `http://127.0.0.1:8000`.
- `biome.json`: apprendre's file, with `files.includes` = `["**", "!**/*.md", "!pnpm-lock.yaml", "!apps/server", "!apps/web/src/lib/api.gen.ts"]` and the `apps/web/src/**` override banning Node modules.
- `scripts/typegen.ts`: runs `pnpm --filter @app/server openapi` (or `uv run --directory ../server python -m app.openapi_export`), feeds the JSON to `openapiTS()` + `astToString()`, prepends `// Generated by scripts/typegen.ts. Do not edit.`; writes `src/lib/api.gen.ts`, or with `--check` compares and exits 1 with "api.gen.ts is out of date. Run pnpm typegen." on any difference.
- `lib/api.ts`: `export const api = createClient<paths>({ baseUrl: "" })` and
  `export async function call<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T>` — returns `data` (or `undefined as T` for 204), throws `ApiError` from the error body, or `ApiError("network", "Can't reach the server.")` on fetch failure.
- `lib/errors.ts`: `class ApiError extends Error { constructor(public code: string, message: string) }`; `function messageFor(err: unknown): string` → `ApiError.message` when non-empty, else `"Something went wrong."`.
- `lib/latest.ts`: apprendre's `latest()` verbatim.
- `lib/router.ts`:
  ```ts
  export type Route = { name: "library" } | { name: "queue" } | { name: "settings" } | { name: "fetch"; urls: string };
  export function parseHash(hash: string): Route;   // "#/" "#/queue" "#/settings" "#/fetch/<encodeURIComponent(urls)>"; anything else → library
  export function href(r: Route): string;
  export type Section = "library" | "queue" | "settings" | null;  // fetch → null
  export function section(r: Route): Section;
  ```
  `router.svelte.ts`: apprendre's reactive `router.route` + `navigate(r: Route)`. The `Route` type is complete here; later phases only add screens.
- `lib/theme.ts`: apprendre's API with `ThemeChoice = "dark" | "light" | "system"`, `THEME_KEY = "theme"`, and `readTheme(stored)` returning `"dark"` for anything that isn't `"light"`/`"system"`. `index.html` inline script applies `.dark` on `<html>` before first paint with the same rule.
- `App.svelte`: switches on `router.route.name` and renders a placeholder heading per screen. No styling decisions yet.

- [ ] **Step 1: Write the failing unit tests**

```ts
// router.test.ts
expect(parseHash("")).toEqual({ name: "library" });
expect(parseHash("#/queue")).toEqual({ name: "queue" });
const urls = "https://youtu.be/a https://www.youtube.com/watch?v=b&list=c";
expect(parseHash(href({ name: "fetch", urls }))).toEqual({ name: "fetch", urls });
expect(parseHash("#/fetch/%E0%A4%A")).toEqual({ name: "library" });   // bad encoding
expect(section({ name: "fetch", urls })).toBeNull();
// theme.test.ts
expect(readTheme(null)).toBe("dark"); expect(readTheme("light")).toBe("light"); expect(readTheme("system")).toBe("system"); expect(readTheme("x")).toBe("dark");
expect(isDark("system", true)).toBe(true); expect(isDark("light", true)).toBe(false);
// errors.test.ts
expect(messageFor(new ApiError("disk_full", "Disk is full."))).toBe("Disk is full.");
expect(messageFor(new Error("x"))).toBe("Something went wrong.");
// latest.test.ts
const next = latest(); const a = next(); const b = next(); expect(a()).toBe(false); expect(b()).toBe(true);
```

- [ ] **Step 2: Run them to see them fail**

Run: `pnpm install && pnpm test`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement the scaffold and `lib/` modules**, run `pnpm typegen` to create `api.gen.ts`.

- [ ] **Step 4: Verify**

Run: `pnpm check`
Expected: PASS.
Run: `pnpm --filter @app/server openapi > /dev/null && echo "// x" >> apps/web/src/lib/api.gen.ts && pnpm --filter @app/web typegen:check; git checkout apps/web/src/lib/api.gen.ts`
Expected: exits 1 with "api.gen.ts is out of date. Run pnpm typegen."
Run: `pnpm dev`, open `http://localhost:5173/#/queue`
Expected: the Queue placeholder, dark background before any script beyond the inline one runs (no white flash on reload).

- [ ] **Step 5: CI and Docker.**
  - CI: in each matrix job add `pnpm/action-setup@v6`, `actions/setup-node@v6` (`node-version-file: .nvmrc`, `cache: pnpm`), `pnpm install --frozen-lockfile`, keep uv setup, and replace the separate uv steps with `pnpm check`.
  - Dockerfile: add stage `web-build` `FROM node:24-trixie-slim`: `corepack enable`, copy `package.json pnpm-lock.yaml pnpm-workspace.yaml apps/web/package.json apps/server/package.json`, `pnpm install --frozen-lockfile --filter @app/web`, copy `apps/web`, `pnpm --filter @app/web build`. Runtime: `COPY --from=web-build /app/apps/web/dist /app/apps/web/dist`; copy Node from `node:24-trixie-slim` instead of 22.
  - Run: `docker compose build && docker compose up -d && sleep 5 && curl -fs localhost:8000/app | grep -q '<div id="app"' && docker compose down`
  - Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(web): Svelte app scaffold, typed API client and drift check"
```

### Task 2.3: Owner checkpoint 1 — `PRODUCT.md`

**Files:** Create: `PRODUCT.md` (repo root, written by impeccable)

- [ ] **Step 1:** Load the impeccable skill (`/Users/lanh/.agents/skills/impeccable/SKILL.md`), run its `context` setup, then `init` (`reference/init.md`). Feed it the spec's Intent, Goals, Non-goals, Anti-goals and "Layout and screens"; register is Operate-mode app UI; platform web, desktop only.
- [ ] **Step 2: STOP.** Show the owner `PRODUCT.md` and wait for approval. Apply their edits. Do not start Task 2.4 before approval.
- [ ] **Step 3: Commit** `git add PRODUCT.md && git commit -m "docs: product context for the Svelte UI"`

### Task 2.4: Owner checkpoint 2 — visual direction and `DESIGN.md`

**Files:** Create: `DESIGN.md` (repo root, plus any sidecar impeccable writes); Modify: `apps/web/src/app.css`, `apps/web/package.json` (the chosen `@fontsource` package)

- [ ] **Step 1:** Run impeccable new-work for the visual world. Constraints to give it: YouTube layout grammar (top bar, left rail, chips, thumbnail grid) without YouTube's clutter; near-black monochrome dark theme plus a light theme; red the only accent (logo mark, progress bars, selected format, rail counts, custom badges); amber only for below-cap warnings; an error tone; WCAG AA in both themes; one bundled typeface (`@fontsource`, chosen here). The approved mockups (`.superpowers/brainstorm/11221-1794783582/content/direction-v2.html`, `playlist-quality.html`) are the starting point.
- [ ] **Step 2: STOP.** Show the owner the direction options in the browser and wait for their pick. Do not code any screen before it.
- [ ] **Step 3:** Write `DESIGN.md` with tokens for both themes (colours, type scale, spacing, radii, motion) and put the same tokens in `app.css` as Tailwind 4 `@theme` variables, with the dark set on `.dark` (`@custom-variant dark (&:where(.dark, .dark *))`). Import the font in `main.ts`.
- [ ] **Step 4: Verify:** `pnpm check` passes; `pnpm dev` shows the placeholder screens in the new tokens in both themes.
- [ ] **Step 5: Commit** `git add -A && git commit -m "design: visual direction and design tokens"`

### Task 2.5: App shell (top bar, left rail, theme) and e2e harness

**Files:**
- Create: `apps/web/src/components/{TopBar,LeftRail,ThemeSelect}.svelte`, `apps/web/src/lib/fetch-options.ts`, `apps/web/playwright.config.ts`, `apps/web/e2e/{app.ts,shell.spec.ts}`, `apps/server/tests/e2e_server.py`
- Modify: `apps/web/src/App.svelte`
- Test: `apps/web/test/fetch-options.test.ts`, `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- `lib/fetch-options.ts`: `type FetchOptions = { useProxy: boolean; useCookies: boolean }`; `FETCH_OPTIONS_KEY = "yt-fetch-options"`; `readFetchOptions(stored: string | null): FetchOptions` (bad JSON → both false); `saveFetchOptions(o: FetchOptions): void`.
- `TopBar.svelte`: wordmark (links to `#/`), URL `<textarea>`-like field that accepts one or more URLs (single line by default, grows on paste of several lines), **Fetch** button, and a small options menu next to Fetch with "Use saved proxy" / "Use saved cookies" toggles bound to `FetchOptions`. Fetch with an empty field does nothing; otherwise `navigate({ name: "fetch", urls: field.trim() })`. Enter submits; Shift+Enter inserts a newline.
- `LeftRail.svelte`: links Library (`#/`), Queue (`#/queue`), Settings (`#/settings`) with `aria-current` from `section()`. Accepts `queueCount: number` (hidden when 0; Phase 3 feeds it).
- `ThemeSelect.svelte`: Dark / Light / System, calls `applyTheme`; mounted in the rail footer (Settings screen reuses it in Phase 3).
- `e2e/app.ts`: `export const APP = "/app";` (Phase 6 changes it to `"/"`). Every spec navigates with `page.goto(\`${APP}#/...\`)`.
- `playwright.config.ts`: Desktop Chrome (`devices["Desktop Chrome"]`, viewport 1440×900), `channel: process.env.PW_CHANNEL`, `baseURL: "http://127.0.0.1:8100"`, `webServer.command: "pnpm build && rm -rf ../../tmp/e2e && cd ../server && uv run uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8100"`, `url: "http://127.0.0.1:8100/health"`, env `YT_DATA_DIR=<repo>/tmp/e2e/data`, `YT_DOWNLOADS_DIR=<repo>/tmp/e2e/downloads`, `YT_WORKERS_ENABLED=1`, `YT_SKIP_MIGRATIONS=0`.
- `tests/e2e_server.py`: sets nothing in the environment itself; monkeypatches `app.services.downloader.extract_info`, `app.services.downloader.extract_flat_info` and `app.services.job_runner.run_download` with stubs (in this phase they raise `RuntimeError("not stubbed")`), then `from app.main import app`. Later phases fill in the stubs and seed data. Every API module must call yt-dlp through `from app.services import downloader` → `downloader.extract_info(...)` so this single patch point works.

- [ ] **Step 1: Write the failing tests**

```ts
// fetch-options.test.ts
expect(readFetchOptions(null)).toEqual({ useProxy: false, useCookies: false });
expect(readFetchOptions("{bad")).toEqual({ useProxy: false, useCookies: false });
expect(readFetchOptions('{"useProxy":true,"useCookies":false}')).toEqual({ useProxy: true, useCookies: false });
```
```ts
// e2e/shell.spec.ts
test("dark by default, theme switch persists", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("radio", { name: "Light" }).check();   // or the control DESIGN.md picks; keep the accessible name
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});
test("rail navigates", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Queue" }).click();
  await expect(page).toHaveURL(/#\/queue$/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `pnpm test && pnpm exec playwright install chromium && pnpm e2e`
Expected: FAIL.

- [ ] **Step 3: Implement** the components and harness. Read impeccable's craft floor first; follow `DESIGN.md`.

- [ ] **Step 4: Verify**

Run: `pnpm check && pnpm e2e`
Expected: PASS. Look at the shell in both themes at 1280 and 1440 in the browser.

- [ ] **Step 5: CI e2e.** Add to `quality.yml` (ubuntu only): `pnpm --filter @app/web exec playwright install --with-deps chromium` and `pnpm e2e`.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(web): app shell with top bar, rail, theme and e2e harness"
```
