# Svelte UI — design

Date: 2026-11-15
Status: draft, owner answered builder-check questions; pending owner review
Reference project: `/Users/lanh/Developer/apprendre-le-francais` (Svelte 5 SPA + API server, pnpm workspace)

## Intent

The owner can't get the UI they want with HTMX + Alpine. They want yourtube to look like YouTube, but more aesthetic and minimal: YouTube's layout (top bar, left rail, chips, thumbnail grid) in a dark, near-black, monochrome style where thumbnails carry the colour. FastAPI stays as the backend. The repo is restructured to match apprendre-le-francais so both projects share one shape and toolchain.

The redesign also fixes the playlist flow: today a playlist is previewed page by page, every video needs its own format choice, and selection is page-local. The owner wants one quality for the whole playlist, sees every video's real availability before queueing, and queues the whole playlist in one go.

## Goals

- A Svelte 5 single-page app replaces every Jinja/HTMX/Alpine page: Library, Queue, Settings, single-video fetch, playlist/batch fetch.
- YouTube-like layout, dark by default, with a light theme and a "system" option.
- Pasting a URL works from anywhere (top bar).
- Playlists: one quality cap for all selected videos, per-video override, every selected video checked (badges) before "Add to queue" is enabled, selection spans the whole playlist.
- Repo laid out like apprendre: `apps/server` (FastAPI), `apps/web` (Svelte), pnpm workspace root.
- Still one container, one process, one port in production.
- Typed API calls from the web app, with a check that fails when the types drift from the server.

## Non-goals

- Phone layout. Computer only for now; narrow windows must not break, but nothing is designed for them.
- In-browser video playback.
- Interface translation (Paraglide) and PWA/offline. apprendre has both; yourtube doesn't need them.
- Live push (WebSocket/SSE). Polling stays.
- Server-side background jobs for playlist checking. Checking runs from the browser tab.
- Changes to download behaviour beyond the quality cap (worker pool, recovery, error mapping stay as they are).

## Anti-goals

- A generic dark dashboard: cards in cards, gradient accents, decorative glow. Minimal means fewer elements, not grey boxes.
- A YouTube clone with its clutter (recommendations, avatars, view counts, notification bells). Only the layout grammar is borrowed.
- Colour other than red as an accent. Red marks: logo mark, progress bars, the selected format, counts on the rail, custom-override badges. Amber is reserved for "below your cap" warnings; a red-ish tone for errors.
- A video silently downloaded below the chosen quality without the owner having seen it.
- Hammering YouTube with parallel lookups (the project just fixed playlist 403s).
- Fonts or assets fetched from a CDN at runtime (today's UI loads Google Fonts; the new one bundles fonts, as apprendre does).

## Constraints

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, yt-dlp, uv, ruff, ty, pytest. Migrations run in the FastAPI lifespan; keep that.
- Frontend toolchain mirrors apprendre: Node 24, pnpm, Svelte 5 (runes), Vite 8, TypeScript via `svelte-check --tsgo`, Tailwind CSS 4 via `@tailwindcss/vite`, Biome, Vitest, Playwright.
- The Docker image must keep bundling Node 22+ for yt-dlp's EJS solver (Node 24 satisfies it) and ffmpeg.
- CI (`.github/workflows/quality.yml`) runs on ubuntu and macOS; it gains the web checks.

## Approaches

|       | Approach                                                                                                                                                                                                                                     | Trade-off                                                                                                                                                  | Verdict                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| **A** | **apprendre's setup: `apps/server` FastAPI with JSON under `/api`, `apps/web` Svelte 5 + Vite + Tailwind + hash router, types generated from FastAPI's OpenAPI spec (`openapi-typescript` + `openapi-fetch`), FastAPI serves the built SPA** | Python and TypeScript are linked only by generated types, so a route change needs a regenerate (enforced by a check). Otherwise matches apprendre exactly. | **Chosen by the owner** |
| B     | SvelteKit in static-adapter mode                                                                                                                                                                                                             | File routing and its conventions; server features unused since FastAPI is the server. apprendre rejected SvelteKit, so the two projects would diverge.     | Rejected                |
| C     | Gradual: mount Svelte components inside the Jinja pages                                                                                                                                                                                      | Always shippable mid-way, but HTMX, Alpine and Svelte coexist for a while, and it doesn't deliver the apprendre layout.                                    | Rejected                |

Rollout (owner agreed): one branch, phased — (1) move files into the new layout, (2) add the JSON API and tests alongside the HTML routes, (3) build the Svelte screens, (4) delete Jinja, HTMX, Alpine and the old CSS. The old UI keeps working until phase 4.

## Decisions

### Repo layout

```
yourtube/
├── apps/
│   ├── server/          app/, alembic/, alembic.ini, tests/, pyproject.toml, uv.lock
│   └── web/             Svelte app (src/, index.html, vite.config.ts, e2e/, test/)
├── docs/superpowers/    specs and plans
├── package.json         workspace root: dev, build, check, typegen scripts
├── pnpm-workspace.yaml
├── biome.json
├── Dockerfile           stage 1 builds apps/web with Node; stage 2 is the Python runtime
└── compose.yaml         (renamed from docker-compose.yml, as in apprendre)
```

- `pnpm dev` runs uvicorn (`uv run --directory apps/server …`) and Vite together; Vite proxies `/api` and file downloads to FastAPI, as apprendre's Vite proxies to Hono.
- `pnpm check` runs Biome, `svelte-check`, Vitest, ruff, ty, pytest, and the type-drift check.
- `.superpowers/` is added to `.gitignore`.
- `.env` stays at the repo root (my call). `apps/server/app/config.py` loads it by absolute path from the repo root, and the dev `data_dir`/`downloads_dir` defaults keep resolving to the repo-root `tmp/` so the existing local database and settings survive the move.

### Server

- JSON routes under `/api/...`, built on the existing services. Pydantic schemas in `app/schemas.py` are the response models (so they appear in OpenAPI). ORM objects are never returned (existing rule).
- Error body: `{ "error": { "code", "message" } }`, as in apprendre. Since there is no translation, the web app may show `message` (the existing `friendly_ytdlp_error` text is already user-facing).
- In production FastAPI serves `apps/web/dist`: real files by path, `index.html` for app routes, 404 for missing files with an extension and for unknown `/api` paths (same rules as apprendre's `app.ts`). `/health` stays where it is for Docker.
- The file download route (`/downloads/{id}/file`) keeps its behaviour (moved under `/api` is the builder's call, as long as the Vite proxy and the SPA fallback agree).
- Endpoints the UI needs (names are the builder's):
  - Library list with search, delete.
  - Queue: active/queued jobs, failed jobs, plus recently completed (for toasts); cancel; **retry** (requeues a failed job with the same URL, cap/format ids, subtitles, template, bitrate); **dismiss** (removes a failed job from the Queue; whether it deletes the row or sets a flag is the builder's call).
  - Enqueue one job; enqueue many jobs in one request (JSON body, not the indexed `url_3` form fields).
  - Lookup one URL: title, uploader, duration, thumbnail, full stream-picker payload, and the video's best available height.
  - List sources: takes one or more URLs, expands playlists with the flat extractor, returns every entry (url, title, thumbnail, duration where the flat data has them, or an entry error). No paging.
  - Settings get/save/reset, and runtime diagnostics.
- The paged batch preview (`resolve_batch_preview` paging) and the `playlist_page_size` setting are removed in phase 4.
- Batch size limit: the current 50-item truncation is raised so real playlists fit (500 is my call; builder may adjust and must show the "skipped N" note when it applies).

### Quality cap (backend change)

- The cap compares against the video's **short side** (min of width and height), so a vertical 1080×1920 video counts as 1080p (my call; it avoids silently downgrading vertical videos). The server's format selector and the browser's badge logic use the same rule and share test cases. If yt-dlp's selector language can't express it cleanly, the builder falls back to height and records why.
- New nullable column on `downloads`: the quality cap, one of `best`, `2160`, `1440`, `1080`, `720`, `480`, `audio`. Alembic migration.
- When a job has exact format ids, they win (today's behaviour). Otherwise the job runner turns the cap into a yt-dlp format selector that never fails for lack of a quality: best video at or below the cap plus best audio, falling back to the best the video has. `audio` means best audio only. Exact selector strings are the builder's, with unit tests per cap.
- Enqueue endpoints accept either a cap or exact format ids per job.

### Web app

- Svelte 5 runes, hash router, `latest()` stale-reply guard, error-code-to-message helper, and theme handling copied in spirit from apprendre (`apps/web/src/lib/`).
- Theme: `dark` (default) | `light` | `system`, stored in `localStorage`, applied by an inline script before first paint. Default is dark, not system.
- Data access through `openapi-fetch` with types generated from FastAPI's OpenAPI schema into a committed file; the drift check regenerates and fails on a diff.

### Layout and screens

Approved mockups: `.superpowers/brainstorm/11221-1794783582/content/direction-v2.html` and `playlist-quality.html` (local, gitignored). The playlist mockup's "page 1 of 2" is stale: there is no pagination.

```
┌───────────────────────────────────────────────────────────────────┐
│ ▬ yourtube        [ Paste a video or playlist URL…    ] [Fetch]   │
├──────┬────────────────────────────────────────────────────────────┤
│ Lib  │ [All] [Downloading] [Video] [Audio only]                   │
│ Queue│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                        │
│  ②   │ │thumb │ │thumb │ │thumb │ │thumb │  title / uploader · q  │
│ Sett │ └▬▬▬───┘ └──────┘ └──────┘ └──────┘  red bar = in progress │
└──────┴────────────────────────────────────────────────────────────┘
```

- **Which view Fetch opens:** one URL that resolves to a single video opens the single-video view. A URL naming both a video and a playlist (`watch?v=X&list=Y`) opens **the video**, with a "Part of a playlist · Open playlist" link that switches to the playlist view (owner's choice). A playlist URL, or several URLs, opens the playlist view. The lookup endpoints need a way to ask for the single video (yt-dlp `noplaylist`).
- **Top bar:** wordmark, URL field, Fetch. "Use saved proxy" / "Use saved cookies" toggles live in a small menu next to Fetch (my call). Pasting several URLs (whitespace/newline separated) behaves like a playlist (my call: the old "Queue many sources" textarea folds into the same field).
- **Left rail:** Library (home), Queue with a red count of queued + active jobs, Settings.
- **Library (home):** thumbnail grid. Chips: All, Downloading, Video, Audio only. In-progress jobs appear in the grid with a red progress bar along the thumbnail bottom; the page polls while any job is active. Each card offers download file and delete (exact affordance, e.g. hover menu, is the builder's). Search box filters by title or uploader (placement is the builder's; top of the grid is the default).
- **Queue:** list of queued/active jobs with progress, status and cancel, and failed jobs with their error message plus **Retry** and **Dismiss** (owner's choice). Failed jobs stay until retried or dismissed. Polls every 2 s. Completion toasts as today (seen ids kept in `sessionStorage`).
- **Single video (after Fetch):** watch-page layout. Left: large thumbnail, title, uploader, duration, Subtitles toggle, "Add to queue". Right, where YouTube shows "Up next": a quality dropdown (same caps as playlists, default `Up to 1080p`, my call) and a Video / Audio / Advanced segmented control for exact format choice, with the expected container shown. Advanced holds output template and audio bitrate. Choosing an exact format overrides the cap.
- **Playlist / multiple URLs (after Fetch):**
  - The whole list appears at once from the flat extraction, as one scrolling grid (no pagination, no infinite scroll). Header: playlist title, `N videos · M selected`, Select all / none, quality dropdown, Add button.
  - Every selected entry is then looked up in the background, 2–3 at a time, from the browser. The Add button reads `Checking k / M…` and is disabled until all selected entries are checked, then reads `Add M to queue`.
  - Badges: `720p max` (amber, best available is below the cap; it downloads at that best), `1440p · custom` (red, per-video override), `Unavailable` (lookup failed; auto-unchecked, can't be re-selected, shows the error on hover/click). Unchecked entries are not looked up; checking one triggers its lookup. Changing the cap re-evaluates badges without new lookups.
  - Header also holds a **Subtitles** toggle and an **Advanced** menu (output template, audio bitrate) that apply to every selected video (owner's choice).
  - Clicking a card opens a right-side panel with that video's exact format picker and a "Playlist setting / Custom" switch. Custom overrides format, subtitles, template and bitrate for that video only.
  - The bulk-enqueue request therefore carries per-job values (the client resolves header defaults and overrides into each job).
  - Leaving the page stops checking; fetching again starts over.
- **Settings:** max concurrent, proxy URL, cookies path, downloads directory, theme, reset; runtime diagnostics panel when degraded.

### Design process

- **Owner checkpoints (owner's choice):** the build stops twice in phase 3, once to approve `PRODUCT.md` and once to pick the visual direction in the browser, before any screen is coded. Phases 1–2 don't depend on them.
- Use **impeccable** for the visual work: run `impeccable init` to write `PRODUCT.md` (this is Operate-mode app UI), then new-work to set the visual world and write `DESIGN.md` with tokens (dark and light palettes, type scale, spacing, radii, motion). Read its craft floor before UI edits; finish with `critique`, `audit`, and `polish` passes in a real browser at 1280 and 1440 widths, both themes.
- **taste-skill (`design-taste-frontend`) is not used for the app screens.** Its house rules target marketing sites (hero sections, one section per screen, photography, page "moments") and would push the app away from the brief. It's a fit only if a public landing page is ever added.
- Fonts bundled via `@fontsource`; the typeface is chosen during the impeccable world step (old Playfair/Work Sans pairing is retired).

### Tests

- Server: the HTML-string integration tests (`tests/integration/test_pages.py`, `test_partials.py`) are replaced by JSON API tests covering the same behaviours. Service and unit tests stay. New tests for the cap-to-selector mapping, the migration, list-sources (no paging), bulk enqueue with mixed cap/exact jobs, retry and dismiss of failed jobs, single-video lookup of `watch?v=X&list=Y`, and SPA serving rules.
- Web: Vitest for pure logic (router, badge evaluation from cap + best height, checking scheduler concurrency, theme).
- Playwright e2e (desktop viewport, Chromium) for: fetch single video → add to queue; fetch playlist → wait for checks → add; cancel in queue; delete in library; theme switch. yt-dlp is stubbed at the server boundary for e2e (the existing tests already monkeypatch `extract_info`); how the stub is wired is the builder's.
- Coverage gate in CI stays (`--cov-fail-under=50` or higher).

## Left to the builder

- Endpoint paths and schema names.
- Exact yt-dlp selector strings per cap.
- Visual details inside the agreed direction: exact shades (WCAG AA in both themes), typeface, iconography, spacing, motion — settled through impeccable's `DESIGN.md`.
- Card affordances for library actions, search placement.
- Phase boundaries and PR split within the four-phase rollout.
- How e2e stubs yt-dlp.

## Risks

- Checking a long playlist is slow (≈3 s per video at 2–3 in parallel; a 200-video playlist takes minutes) and stops if the tab is left. Accepted for now; a server-side job is the upgrade path.
- Flat playlist extraction may lack thumbnails or durations for some extractors; cards then show a neutral placeholder until the per-video lookup fills them.
- Two toolchains (uv + pnpm) in one repo raise CI time and Docker build complexity.
