# Phase 3: Library, Queue and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the new UI at `/app` the owner can browse and search the library as a thumbnail grid, download or delete files, watch the queue with live progress, cancel, retry or dismiss failed jobs, get completion toasts, and edit settings — everything except adding downloads (still done in the old UI at `/`).

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 3: Library, Queue and Settings". The tasks below are copied from it verbatim (re-synced 2026-11-16 after checking against the code on `main`). If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** Phase 2 (including owner approval of PRODUCT.md and DESIGN.md).

**Tasks:** Task 3.1 Queue API: list, cancel, retry, dismiss, Task 3.2 Library and Settings API, Task 3.3 Queue screen, polling, toasts and the rail count, Task 3.4 Library screen, Task 3.5 Settings screen, Task 3.6 e2e for Queue and Library.

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

3. **Retry or dismiss pressed twice, or pressed on a job that is no longer failed.** It must not create duplicate jobs or delete a finished download. Retry and dismiss act only on `error` rows; anything else gets a 409. Tests: `test_retry_twice_conflicts`, `test_dismiss_done_job_conflicts` (Task 3.1).

The numbers are the parent plan's Review Focus numbers. The tests that pin them are in this phase's tasks.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 3: Library, Queue and Settings

**Usable result:** in the new UI at `/app` the owner can browse and search the library as a thumbnail grid, download or delete files, watch the queue with live progress, cancel, retry or dismiss failed jobs, get completion toasts, and edit settings — everything except adding downloads (still done in the old UI at `/`).

**Facts about the code this phase builds on** (checked against `main` after Phase 2):

- `app/api/__init__.py` defines `api_router = APIRouter(prefix="/api")` and then a catch-all `/{path:path}` that answers 404 `not_found`. Feature routers must be included **above** the catch-all (`api_router.include_router(jobs.router)` etc. go where the comment "Feature routers are included here" is), or the catch-all swallows them.
- `ApiError(status, code, message)` from `app.api.errors` produces the error body. Pydantic validation errors on `/api` already become 422 `invalid_request`.
- API tests use `client` (from `tests/api/conftest.py`, runs the lifespan with migrations skipped and workers off) plus `db_session_visible` for rows the app's own sessions must see.
- `ty` rejects passing a `str` where a `Literal` is expected. ORM `Download.status` is `str` and `RuntimeDiagnostics.level` is `str`, so the schema constructors below go through `model_validate(..., from_attributes=True)` (or a dict), not keyword arguments.
- FastAPI with a `lifespan=` ignores `app.router.on_startup` handlers (checked: they never run). Seeding for e2e wraps `app.router.lifespan_context` instead.
- Vitest runs in Node (no `document`, no `sessionStorage`). Pure helpers take what they need as arguments.
- `ThemeSelect.svelte` holds its own `$state` and uses `name="theme"` on its radios. Two instances on one page (rail + Settings) would share one browser radio group and drift apart. Task 3.5 fixes this.

### Task 3.1: Queue API: list, cancel, retry, dismiss

**Files:**
- Modify: `apps/server/app/schemas.py`, `apps/server/app/services/queue.py`, `apps/server/app/api/__init__.py`
- Create: `apps/server/app/api/jobs.py`
- Test: `apps/server/tests/unit/test_queue_retry_dismiss.py`, `apps/server/tests/api/test_queue_api.py`

**Interfaces:**
- Schemas:
  ```python
  type JobStatus = Literal["queued", "active", "done", "error", "cancelled"]
  type MediaKind = Literal["video", "audio"]
  class JobOut(BaseModel):
      id: int; url: str; title: str | None; uploader: str | None; duration: int | None; thumbnail: str | None
      status: JobStatus; progress: float; error_code: str | None; error_message: str | None
      media_kind: MediaKind; file_size: int | None; media_format: str | None; resolution_height: int | None
      created_at: datetime; finished_at: datetime | None
      @classmethod
      def from_row(cls, row: Download) -> "JobOut": ...   # cls.model_validate({...fields from row..., "media_kind": ...})
  class QueueOut(BaseModel):
      active: list[JobOut]      # queued + active, oldest first (get_active_jobs)
      failed: list[JobOut]      # status error, newest first
      completed: list[JobOut]   # get_recent_completed_jobs(limit=20)
  ```
  `media_kind` is `"audio"` when the job has an audio id and no video id, or when it is `done` with `resolution_height is None`; otherwise `"video"`. (Phase 4 adds `quality_cap` to `JobOut` and makes cap `audio` count as audio.) `schemas.py` imports `Download` under `TYPE_CHECKING` only, so it stays free of ORM imports at runtime.
- Services (`queue.py`):
  - `get_failed_jobs(session) -> list[Download]` — status `error`, `finished_at desc, id desc`.
  - `retry_job(session, job_id) -> bool` — conditional UPDATE `WHERE id = :id AND status = 'error'` setting `status='queued', progress=0, error_code=None, error_message=None, cancel_requested=False, claimed_at=None, finished_at=None`; commits; returns whether a row changed. Keeps URL, format ids, template, bitrate, subtitles (and the cap from Phase 4) because it is the same row. `created_at` is kept, so a retried job keeps its original place in line (`claim_next` orders by `created_at`) — usually that means it runs next; that is fine.
  - `dismiss_job(session, job_id) -> bool` — `DELETE WHERE id = :id AND status = 'error'`; commits (dismiss deletes the row: failed jobs have no file and nothing else reads them).
- Routes (`api/jobs.py`, `router = APIRouter(tags=["jobs"])`, session via `Depends(get_session)`, included in `api_router` above the catch-all):
  - `GET /api/queue` → `QueueOut`
  - `POST /api/downloads/{job_id}/cancel` → 204; `cancel_job` false → 409 `not_cancellable` "This download can't be cancelled." (missing ids get the same 409; the UI never sends one).
  - `POST /api/downloads/{job_id}/retry` → `JobOut`; when `retry_job` is false: missing → 404 `not_found` "Download not found."; otherwise 409 `not_failed` "Only failed downloads can be retried." On success re-read the row with `session.get(Download, job_id, populate_existing=True)` (the UPDATE bypassed the identity map).
  - `POST /api/downloads/{job_id}/dismiss` → 204; same 404/409 rules with "Only failed downloads can be dismissed."
  - 204 routes declare `status_code=204, response_class=Response` and return `Response(status_code=204)` so the OpenAPI schema has no body.

- [ ] **Step 1: Write the failing tests**

```python
# unit (db_session; make rows with enqueue_download, then set status/fields and commit)
def test_retry_resets_failed_job(db_session):  # error row with progress 40, error_code "timeout", cancel_requested True, video_format_id "137"
    assert retry_job(db_session, row.id) is True
    db_session.refresh(row)
    assert (row.status, row.progress, row.error_code, row.finished_at, row.cancel_requested, row.video_format_id) == ("queued", 0.0, None, None, False, "137")
def test_retry_twice_conflicts(db_session): assert retry_job(s, id) is True and retry_job(s, id) is False
def test_retry_ignores_non_failed(db_session): ...  # queued/active/done/cancelled rows → False, unchanged
def test_dismiss_deletes_only_failed(db_session): ...  # error row gone; done row stays and returns False
def test_get_failed_jobs_newest_first(db_session): ...
# api (client + db_session_visible)
def test_queue_lists_active_failed_completed(client, db_session_visible): ...  # one of each; assert ids in each list; done row with resolution_height None → media_kind "audio"; audio-id-only queued row → "audio"
def test_cancel_queued_returns_204(client, ...): ...
def test_cancel_done_returns_409_error_body(client, ...): assert r.json()["error"]["code"] == "not_cancellable"
def test_retry_endpoint_requeues(client, ...): assert r.json()["status"] == "queued"
def test_retry_done_job_conflicts(client, ...): assert r.status_code == 409 and r.json()["error"]["code"] == "not_failed"
def test_dismiss_failed_job_returns_204(client, ...): ...  # row gone
def test_dismiss_done_job_conflicts(client, ...): assert r.status_code == 409 and row still exists
def test_retry_missing_404(client): assert r.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_queue_retry_dismiss.py tests/api/test_queue_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement** schemas, services, routes.

- [ ] **Step 4: Regenerate types and check**

Run: `pnpm typegen && pnpm check`
Expected: PASS (the old suite included).

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): queue list, cancel, retry and dismiss"`

### Task 3.2: Library and Settings API

**Files:**
- Modify: `apps/server/app/schemas.py`, `apps/server/app/api/jobs.py`, `apps/server/app/api/__init__.py`
- Create: `apps/server/app/api/library.py`, `apps/server/app/api/settings.py`
- Test: `apps/server/tests/api/test_library_api.py`, `apps/server/tests/api/test_settings_api.py`

**Interfaces:**
- `GET /api/library?q=` → `list[JobOut]` (`search_library(q.strip())` when `q` is non-blank, else `get_library`).
- `DELETE /api/library/{job_id}` → 204. `delete_from_library` reasons map to: `not_found` 404 "Download not found.", `not_done` 409 "Only finished downloads can be deleted.", `delete_failed` 500 "The file couldn't be deleted." `file_missing` is still 204.
- `GET /api/downloads/{job_id}/file` (in `jobs.py`) → same behaviour as the old `/downloads/{id}/file` (`resolve_repo_path(row.file_path)`), returned as `FileResponse(path, filename=path.name)`, but with error bodies: 404 `not_found` "Download not found.", 409 `not_ready` "Download is not ready.", 404 `file_missing` "File is missing." The old route stays until Phase 6.
- Schemas:
  ```python
  class SettingsOut(BaseModel): max_concurrent: int; proxy_url: str; cookies_path: str; downloads_dir: str
  class SettingsIn(BaseModel):
      max_concurrent: int = Field(ge=1, le=5); proxy_url: str = ""; cookies_path: str = ""; downloads_dir: str = ""
  class DiagnosticsOut(BaseModel): level: Literal["ok", "warning"]; messages: list[str]; js_runtime_ready: bool; workers_enabled: bool
  ```
  `playlist_page_size` is not exposed (the old UI still owns it until Phase 6). `SettingsOut` is built from `get_all_settings` with `int(values["max_concurrent"])`; `DiagnosticsOut` via `DiagnosticsOut.model_validate(diag, from_attributes=True)`. String fields are saved with `.strip()`.
- `GET /api/settings` → `SettingsOut`; `PUT /api/settings` (`SettingsIn`) → `SettingsOut`, writes only those four keys via `set_settings_batch` (as strings), `ValueError` → 422 `invalid_settings` with its message; `POST /api/settings/reset` → `SettingsOut` (`reset_settings` also resets `playlist_page_size`, same as the old UI's reset); `GET /api/diagnostics` → `DiagnosticsOut` from `collect_runtime_diagnostics(workers_enabled=settings.workers_enabled)` (`app.config.settings`).
- Router files: `api/library.py` (`tags=["library"]`), `api/settings.py` (`tags=["settings"]`; import the service module as `from app.services import settings as settings_service` and the config as `from app.config import settings as app_settings` to avoid the name clash).

- [ ] **Step 1: Write the failing tests**

```python
def test_library_lists_done_only_newest_first(client, db_session_visible): ...
def test_library_search_matches_title_or_uploader(client, ...): ...  # q="Ana" finds uploader "Anath"; q="  " returns everything
def test_library_delete_removes_row_and_file(client, tmp_path, ...): ...
def test_library_delete_active_conflicts(client, ...): assert r.json()["error"]["code"] == "not_done"
def test_library_delete_missing_404(client): assert r.json()["error"]["code"] == "not_found"
def test_file_route_streams_done_file(client, tmp_path, ...): assert r.content == b"data"
def test_file_route_not_ready_409(client, ...): assert r.json()["error"]["code"] == "not_ready"
def test_file_route_missing_file_404(client, ...): assert r.json()["error"]["code"] == "file_missing"
def test_settings_roundtrip(client, db_session_visible): put {"max_concurrent": 3, ...}; get → 3
def test_settings_rejects_out_of_range(client): r = put max_concurrent 9 → 422, code "invalid_request"
def test_settings_put_keeps_playlist_page_size(client, db_session_visible): ...  # stored 30 stays 30
def test_settings_reset_restores_defaults(client, db_session_visible): ...
def test_diagnostics_shape(client): assert set(r.json()) == {"level", "messages", "js_runtime_ready", "workers_enabled"}
```

- [ ] **Step 2: Run them to see them fail**, `cd apps/server && uv run pytest tests/api -v`. Expected: FAIL for the new tests.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** `pnpm typegen && pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): library, file download and settings endpoints"`

### Task 3.3: Queue screen, polling, toasts and the rail count

**Files:**
- Create: `apps/web/src/lib/{poll.ts,toasts.ts,queue.ts}`, `apps/web/src/routes/Queue.svelte`, `apps/web/src/components/Toasts.svelte`
- Modify: `apps/web/src/App.svelte`
- Test: `apps/web/test/{poll,toasts,queue}.test.ts`

(`LeftRail.svelte` already takes `queueCount` from Phase 2; only `App.svelte` changes to feed it.)

**Interfaces:**
- `lib/poll.ts`: `function createPoller(task: () => Promise<void>, intervalMs: number, isHidden: () => boolean = () => document.hidden): { start(): void; stop(): void }` — `start()` runs `task` now, then `intervalMs` after each run **finishes** (never overlapping; a rejected task is caught and polling continues); while `isHidden()` is true a tick skips the task and just schedules the next tick; after `stop()` nothing more runs (a run in flight when `stop()` is called doesn't schedule another). `isHidden` is a parameter so the test runs in Node.
- `lib/toasts.ts`: `SEEN_KEY = "yt-seen-completed-jobs"`; `readSeen(stored: string | null): Set<string>` (bad JSON or a non-array → empty set; entries kept as strings); `function newCompletions(seen: Set<string>, completed: JobOut[], silent: boolean): { toasts: JobOut[]; seen: Set<string> }` — returns a new set with every completed id (as a string) added; returns as toasts the jobs not already in `seen`, unless `silent`. `silent` is true for the first successful poll after the app loads (same as the old queue page: completions that happened while the page was closed are marked seen without toasts).
- `lib/queue.ts`: `type JobOut = components["schemas"]["JobOut"]`, `type QueueOut = components["schemas"]["QueueOut"]` (re-exported for screens and tests); `function leftActive(prev: JobOut[], next: JobOut[]): boolean` — true when some id in `prev` is not in `next` (a job finished, failed or was cancelled).
- `App.svelte` owns one app-wide poller: `refreshQueue()` calls `GET /api/queue` (guarded by `latest()`), stores the `QueueOut` in `$state`, feeds `LeftRail` `queueCount = active.length`, runs `newCompletions` against `readSeen(sessionStorage.getItem(SEEN_KEY))`, writes the new set back, and pushes toasts. The poller (2000 ms) starts in an `$effect` and is stopped by its cleanup. `Queue.svelte` and (Task 3.4) `Library.svelte` receive `queue: QueueOut | null` and `refresh: () => Promise<void>` as props (one poller, not one per screen). A failed poll keeps the last good data.
- `Toasts.svelte`: fixed region with `aria-live="polite"`; each toast shows "Downloaded" and the title, disappears after 5 s, and has a Close button (`aria-label="Close"`).
- `Queue.svelte`: heading "Queue". Active jobs as a `<ul>` of `<li>` (thumbnail, title, uploader, status "Queued"/"Downloading", red progress bar with % for active, **Cancel**). Then a "Failed" section (title, `error_message`, **Retry**, **Dismiss**). Empty state when both lists are empty: "Nothing in the queue." Before the first poll answers: no empty state, just the heading. After an action, `await refresh()` at once. Action errors show `messageFor(err)` inline next to the job; buttons are disabled while their request runs (no double posts).

- [ ] **Step 1: Write the failing tests** (Vitest with fake timers)

```ts
// poll.test.ts
it("runs at once, then intervalMs after each run finishes", ...);   // task resolves after 5 s, interval 2 s → second call at 7 s
it("does not run again after stop, even if a run was in flight", ...);
it("skips runs while hidden and resumes when visible", ...);
it("keeps polling after a rejected run", ...);
// toasts.test.ts
const r1 = newCompletions(new Set(), [job(1), job(2)], true); expect(r1.toasts).toEqual([]); expect([...r1.seen]).toEqual(["1", "2"]);
const r2 = newCompletions(r1.seen, [job(2), job(3)], false); expect(r2.toasts.map((j) => j.id)).toEqual([3]);
expect(readSeen("nope")).toEqual(new Set()); expect(readSeen('{"a":1}')).toEqual(new Set()); expect(readSeen('["4"]')).toEqual(new Set(["4"]));
// queue.test.ts
expect(leftActive([job(1), job(2)], [job(2)])).toBe(true); expect(leftActive([job(1)], [job(1), job(2)])).toBe(false);
```

- [ ] **Step 2:** `pnpm test` → FAIL.
- [ ] **Step 3: Implement** (craft floor first; follow `DESIGN.md`).
- [ ] **Step 4:** `pnpm check` → PASS. In `pnpm dev`, queue a video in the old UI at `:8000/` and watch it in `:5173/#/queue`: progress moves, the rail count shows 1, a toast appears on completion, a forced failure (bad URL) shows Retry/Dismiss and both work.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): queue screen with polling, toasts and rail count"`

### Task 3.4: Library screen

**Files:**
- Create: `apps/web/src/routes/Library.svelte`, `apps/web/src/components/{JobCard,Chips}.svelte`, `apps/web/src/lib/library.ts`
- Modify: `apps/web/src/App.svelte`
- Test: `apps/web/test/library.test.ts`

**Interfaces:**
- `lib/library.ts`: `type Chip = "all" | "downloading" | "video" | "audio"`; `function libraryItems(done: JobOut[], active: JobOut[], chip: Chip): JobOut[]` — `all` = active first, then done; `downloading` = active only; `video` / `audio` = done and active filtered by `media_kind`. `function qualityLabel(job: JobOut): string` — `Audio` when `media_kind === "audio"`, `{resolution_height}p` when known, else `""`. `function formatSize(bytes: number | null): string` — `""` for null, else `B`/`KB`/`MB`/`GB` with one decimal from KB up (1024-based).
- `Library.svelte` (home, `#/`): heading "Library", search field at the top of the grid (`aria-label="Search library"`, debounced 250 ms, `GET /api/library?q=`, guarded by `latest()`), chips All / Downloading / Video / Audio only (a radio-style group: `role="radiogroup"` with buttons using `aria-checked`, or real radios — the builder's call), thumbnail grid of `JobCard`. Active jobs come from the `queue` prop (`queue.active`); while the search box is non-blank, active jobs are hidden (search covers the library only). Reloads the library list when `leftActive(prev, queue.active)` is true for successive polls (so finished jobs move from in-progress to done without a manual reload).
- `JobCard.svelte`: an `<article>`; 16:9 thumbnail (neutral placeholder when none; `loading="lazy"`, `alt=""`), title (2 lines max), uploader · `qualityLabel` · `formatSize` (empty parts left out). In progress: red progress bar along the thumbnail bottom and status text instead of actions. Done: a menu shown on hover **and** on focus-within (so keyboard users reach it) with **Download file** (`<a href="/api/downloads/{id}/file" download>`) and **Delete** (two-step: "Delete" then "Confirm delete", the second step returns to "Delete" after 4 s or on blur; errors inline). After a delete succeeds the parent removes the card at once.
- Empty states: no jobs at all → "No downloads yet. Paste a URL above."; search with no results → "Nothing matches “{q}”."; a chip with no results → "Nothing here yet." Library load error → `messageFor(err)` with a "Try again" button.

- [ ] **Step 1: Write the failing test**

```ts
expect(libraryItems([d1], [a1], "all").map((j) => j.id)).toEqual([a1.id, d1.id]);
expect(libraryItems([d1], [a1], "downloading")).toEqual([a1]);
expect(libraryItems([video, audio], [], "audio")).toEqual([audio]);
expect(qualityLabel(video1080)).toBe("1080p"); expect(qualityLabel(audio)).toBe("Audio");
expect(formatSize(null)).toBe(""); expect(formatSize(1536)).toBe("1.5 KB"); expect(formatSize(5 * 1024 ** 3)).toBe("5.0 GB");
```

- [ ] **Step 2:** `pnpm test` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** `pnpm check` → PASS; in the browser at 1280 and 1440, both themes: grid, chips, search, delete and download work with real downloads.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): library grid with chips, search, download and delete"`

### Task 3.5: Settings screen

**Files:**
- Create: `apps/web/src/routes/Settings.svelte`
- Modify: `apps/web/src/App.svelte`, `apps/web/src/components/ThemeSelect.svelte`

**Interfaces:**
- `ThemeSelect.svelte` fix (needed because the rail and Settings both show it): keep the chosen theme in one module-level `$state` (`<script module>`) so both copies agree, and give each copy its own radio group name via `$props.id()` (e.g. `name="theme-{id}"`). Takes an optional `label` prop for the group's `aria-label` (default "Theme"); the existing shell e2e (`getByRole("radio", { name: "Light" })`) must keep passing — on the Settings screen there are two "Light" radios, so the shell test stays on `#/`.
- Form: Max concurrent downloads (number input 1–5, note "Applies after restart."), Proxy URL, Cookies file path, Downloads folder (placeholder "Default from server config"), Theme (`ThemeSelect`, applies at once, not part of Save), **Save** ("Settings saved." on success, `messageFor(err)` on error), **Reset to defaults** (two-step confirm; reloads the form from the response). Loads `GET /api/settings` and `GET /api/diagnostics` on mount; load error → `messageFor(err)` with "Try again". A diagnostics panel shows only when `level === "warning"`, listing `messages`. Every field has a visible `<label>`.

- [ ] **Step 1: Implement** (craft floor first).
- [ ] **Step 2: Verify** `pnpm check` and `pnpm e2e` → PASS; in the browser: save, reload shows saved values, max 9 shows the validation message, reset restores defaults, the old UI's settings page shows the same values, switching theme in Settings updates the rail's selector too.
- [ ] **Step 3: Commit** `git add -A && git commit -m "feat(web): settings screen"`

### Task 3.6: e2e for Queue and Library

**Files:**
- Modify: `apps/server/tests/e2e_server.py`
- Create: `apps/web/e2e/{queue,library}.spec.ts`

**Interfaces:**
- `e2e_server.py` seeds after migrations by wrapping the lifespan (an `on_startup` hook would never run, because the app uses `lifespan=`):
  ```python
  _original = app.router.lifespan_context
  @asynccontextmanager
  async def _lifespan(a: FastAPI) -> AsyncIterator[None]:
      async with _original(a):
          _seed()
          yield
  app.router.lifespan_context = _lifespan
  ```
  `_seed()` (with `SessionLocal`) inserts one `done` row "Seeded video" (uploader "E2E", `resolution_height` 1080, `media_format` "mp4", `file_size` 4, `finished_at` now) whose `file_path` is a real 4-byte file written to `settings.downloads_dir / "seeded.mp4"`, and one `queued` row "Slow video" with URL `https://e2e.test/slow`. Playwright's `webServer` deletes `tmp/e2e` before each run, so the database starts empty. Workers are on, so a worker claims "Slow video" within about a second.
- Stub `run_download(url, *, output_dir, progress_hook, **_)` (keyword names match the real call in `job_runner`): for URLs containing `slow`, call `progress_hook({"status": "downloading", "_percent_str": f"{p}%"})` for p = 1..100 with 0.2 s sleeps (the real hook raises `DownloadCancelled` when cancel is requested); otherwise write `<output_dir>/<last path segment>.mp4` with 4 bytes, call the hook with `status="finished", filename=...`, and return `DownloadResult(path, 4, "mp4", 1080)`.
- Each spec only touches its own seeded row, so the two spec files can run in either order or in parallel.

- [ ] **Step 1: Write the specs**

```ts
test("cancel in queue", async ({ page }) => {
  await page.goto(`${APP}#/queue`);
  const row = page.getByRole("listitem").filter({ hasText: "Slow video" });
  await row.getByRole("button", { name: "Cancel" }).click();
  await expect(row).toHaveCount(0);
});
test("delete in library", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const card = page.getByRole("article").filter({ hasText: "Seeded video" });
  await card.hover();
  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Confirm delete" }).click();
  await expect(card).toHaveCount(0);
});
```

- [ ] **Step 2:** `pnpm e2e` → PASS (fix stubs/markup until it does; keep the accessible names). Then `pnpm check` → PASS (`ty` checks `e2e_server.py`).
- [ ] **Step 3: Commit** `git add -A && git commit -m "test(e2e): queue cancel and library delete"`
