# Phase 3: Library, Queue and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the new UI at `/app` the owner can browse and search the library as a thumbnail grid, download or delete files, watch the queue with live progress, cancel, retry or dismiss failed jobs, get completion toasts, and edit settings — everything except adding downloads (still done in the old UI at `/`).

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 3: Library, Queue and Settings". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

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
      def from_row(cls, row: Download) -> "JobOut": ...
  class QueueOut(BaseModel):
      active: list[JobOut]      # queued + active, oldest first (get_active_jobs)
      failed: list[JobOut]      # status error, newest first
      completed: list[JobOut]   # get_recent_completed_jobs(limit=20)
  ```
  `media_kind` is `"audio"` when the job has an audio id and no video id, or when it is `done` with `resolution_height is None`; otherwise `"video"`. (Phase 4 adds `quality_cap` to `JobOut` and makes cap `audio` count as audio.)
- Services (`queue.py`):
  - `get_failed_jobs(session) -> list[Download]` — status `error`, `finished_at desc, id desc`.
  - `retry_job(session, job_id) -> bool` — conditional UPDATE `WHERE id = :id AND status = 'error'` setting `status='queued', progress=0, error_code=None, error_message=None, cancel_requested=False, claimed_at=None, finished_at=None`; returns whether a row changed. Keeps URL, format ids, template, bitrate, subtitles (and the cap from Phase 4) because it is the same row.
  - `dismiss_job(session, job_id) -> bool` — `DELETE WHERE id = :id AND status = 'error'` (dismiss deletes the row: failed jobs have no file and nothing else reads them).
- Routes (`api/jobs.py`, `router = APIRouter(tags=["jobs"])`, included in `api_router`):
  - `GET /api/queue` → `QueueOut`
  - `POST /api/downloads/{job_id}/cancel` → 204; `cancel_job` false → 409 `not_cancellable` "This download can't be cancelled."
  - `POST /api/downloads/{job_id}/retry` → `JobOut`; missing → 404 `not_found` "Download not found."; not `error` → 409 `not_failed` "Only failed downloads can be retried."
  - `POST /api/downloads/{job_id}/dismiss` → 204; same 404/409 rules with "Only failed downloads can be dismissed."

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_retry_resets_failed_job(db_session):  # error row with progress 40, error_code "timeout", video_format_id "137"
    assert retry_job(db_session, row.id) is True
    db_session.refresh(row)
    assert (row.status, row.progress, row.error_code, row.finished_at, row.video_format_id) == ("queued", 0.0, None, None, "137")
def test_retry_twice_conflicts(db_session): assert retry_job(s, id) is True and retry_job(s, id) is False
def test_dismiss_deletes_only_failed(db_session): ...  # error row gone; done row stays and returns False
# api
def test_queue_lists_active_failed_completed(client, db_session_visible): ...  # one of each; assert ids in each list and media_kind
def test_cancel_queued_returns_204(client, ...): ...
def test_cancel_done_returns_409_error_body(client, ...): assert r.json()["error"]["code"] == "not_cancellable"
def test_retry_endpoint_requeues(client, ...): assert r.json()["status"] == "queued"
def test_dismiss_done_job_conflicts(client, ...): assert r.status_code == 409 and row still exists
def test_retry_missing_404(client): assert r.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd apps/server && uv run pytest tests/unit/test_queue_retry_dismiss.py tests/api/test_queue_api.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement** schemas, services, routes.

- [ ] **Step 4: Regenerate types and check**

Run: `pnpm typegen && pnpm check`
Expected: PASS.

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): queue list, cancel, retry and dismiss"`

### Task 3.2: Library and Settings API

**Files:**
- Modify: `apps/server/app/schemas.py`, `apps/server/app/api/jobs.py`, `apps/server/app/api/__init__.py`
- Create: `apps/server/app/api/library.py`, `apps/server/app/api/settings.py`
- Test: `apps/server/tests/api/test_library_api.py`, `apps/server/tests/api/test_settings_api.py`

**Interfaces:**
- `GET /api/library?q=` → `list[JobOut]` (`search_library` when `q` is non-blank, else `get_library`).
- `DELETE /api/library/{job_id}` → 204. `delete_from_library` reasons map to: `not_found` 404 "Download not found.", `not_done` 409 "Only finished downloads can be deleted.", `delete_failed` 500 "The file couldn't be deleted." `file_missing` is still 204.
- `GET /api/downloads/{job_id}/file` (in `jobs.py`) → same behaviour as the old `/downloads/{id}/file` but with error bodies: 404 `not_found`, 409 `not_ready` "Download is not ready.", 404 `file_missing` "File is missing." The old route stays until Phase 6.
- Schemas:
  ```python
  class SettingsOut(BaseModel): max_concurrent: int; proxy_url: str; cookies_path: str; downloads_dir: str
  class SettingsIn(BaseModel):
      max_concurrent: int = Field(ge=1, le=5); proxy_url: str = ""; cookies_path: str = ""; downloads_dir: str = ""
  class DiagnosticsOut(BaseModel): level: Literal["ok", "warning"]; messages: list[str]; js_runtime_ready: bool; workers_enabled: bool
  ```
  `playlist_page_size` is not exposed (the old UI still owns it until Phase 6).
- `GET /api/settings` → `SettingsOut` (from `get_all_settings`); `PUT /api/settings` (`SettingsIn`) → `SettingsOut`, writes only those four keys via `set_settings_batch`, `ValueError` → 422 `invalid_settings` with its message; `POST /api/settings/reset` → `SettingsOut`; `GET /api/diagnostics` → `DiagnosticsOut` from `collect_runtime_diagnostics(workers_enabled=settings.workers_enabled)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_library_lists_done_only_newest_first(client, db_session_visible): ...
def test_library_search_matches_title_or_uploader(client, ...): ...  # q="Ana" finds uploader "Anath"
def test_library_delete_removes_row_and_file(client, tmp_path, ...): ...
def test_library_delete_active_conflicts(client, ...): assert r.json()["error"]["code"] == "not_done"
def test_file_route_streams_done_file(client, tmp_path, ...): assert r.content == b"data"
def test_file_route_missing_file_404(client, ...): assert r.json()["error"]["code"] == "file_missing"
def test_settings_roundtrip(client, ...): put {"max_concurrent": 3, ...}; get → 3
def test_settings_rejects_out_of_range(client): r = put max_concurrent 9 → 422, code "invalid_request"
def test_settings_put_keeps_playlist_page_size(client, db_session_visible): ...  # stored 30 stays 30
def test_settings_reset_restores_defaults(client, ...): ...
def test_diagnostics_shape(client): assert set(r.json()) == {"level", "messages", "js_runtime_ready", "workers_enabled"}
```

- [ ] **Step 2: Run them to see them fail**, `cd apps/server && uv run pytest tests/api -v`. Expected: FAIL for the new tests.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** `pnpm typegen && pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): library, file download and settings endpoints"`

### Task 3.3: Queue screen, polling, toasts and the rail count

**Files:**
- Create: `apps/web/src/lib/{poll.ts,toasts.ts}`, `apps/web/src/routes/Queue.svelte`, `apps/web/src/components/Toasts.svelte`
- Modify: `apps/web/src/App.svelte`, `apps/web/src/components/LeftRail.svelte`
- Test: `apps/web/test/{poll,toasts}.test.ts`

**Interfaces:**
- `lib/poll.ts`: `function createPoller(task: () => Promise<void>, intervalMs: number): { start(): void; stop(): void }` — runs `task` now, then `intervalMs` after each run **finishes** (never overlapping), skips runs while `document.hidden`, stops for good after `stop()` (a run in flight when `stop()` is called doesn't schedule another).
- `lib/toasts.ts`: `SEEN_KEY = "yt-seen-completed-jobs"`; `readSeen(stored: string | null): Set<string>`; `function newCompletions(seen: Set<string>, completed: JobOut[], silent: boolean): { toasts: JobOut[]; seen: Set<string> }` — every completed id goes into `seen`; when `silent` (first load of the session's first poll) no toasts are returned.
- An app-wide poller in `App.svelte` calls `GET /api/queue` every 2 s, feeds `LeftRail` `queueCount = active.length` and `Toasts` via `newCompletions`, and hands the latest `QueueOut` to `Queue.svelte` (one poller, not one per screen). Toasts disappear after 5 s and can be closed.
- `Queue.svelte`: active jobs (thumbnail, title, uploader, status, red progress bar with %, Cancel), then failed jobs (title, `error_message`, **Retry**, **Dismiss**). Empty state: "Nothing in the queue." After an action, refresh at once. Action errors show `messageFor(err)` inline next to the job.

- [ ] **Step 1: Write the failing tests** (Vitest with fake timers)

```ts
// poll.test.ts
it("waits for a run to finish before scheduling the next", ...);   // task resolves after 5 s, interval 2 s → second call at 7 s
it("does not run again after stop, even if a run was in flight", ...);
// toasts.test.ts
const r1 = newCompletions(new Set(), [job(1), job(2)], true); expect(r1.toasts).toEqual([]); expect([...r1.seen]).toEqual(["1", "2"]);
const r2 = newCompletions(r1.seen, [job(2), job(3)], false); expect(r2.toasts.map((j) => j.id)).toEqual([3]);
expect(readSeen("nope")).toEqual(new Set());
```

- [ ] **Step 2:** `pnpm test` → FAIL.
- [ ] **Step 3: Implement** (craft floor first; follow `DESIGN.md`).
- [ ] **Step 4:** `pnpm check` → PASS. In `pnpm dev`, queue a video in the old UI at `:8000/` and watch it in `:5173/#/queue`: progress moves, the rail count shows 1, a toast appears on completion, a forced failure (bad URL) shows Retry/Dismiss and both work.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): queue screen with polling, toasts and rail count"`

### Task 3.4: Library screen

**Files:**
- Create: `apps/web/src/routes/Library.svelte`, `apps/web/src/components/{JobCard,Chips}.svelte`, `apps/web/src/lib/library.ts`
- Test: `apps/web/test/library.test.ts`

**Interfaces:**
- `lib/library.ts`: `type Chip = "all" | "downloading" | "video" | "audio"`; `function libraryItems(done: JobOut[], active: JobOut[], chip: Chip): JobOut[]` — `all` = active first, then done; `downloading` = active only; `video` / `audio` = done and active filtered by `media_kind`.
- `Library.svelte` (home, `#/`): search field at the top of the grid (debounced 250 ms, `GET /api/library?q=`, guarded by `latest()`), chips All / Downloading / Video / Audio only, thumbnail grid of `JobCard`. Reloads the library list when the app-wide queue poll shows a job left `active` (so finished jobs move from in-progress to done without a manual reload).
- `JobCard.svelte`: 16:9 thumbnail (neutral placeholder when none), title (2 lines max), uploader · quality label (`{resolution_height}p` or `Audio`) · size. In progress: red progress bar along the thumbnail bottom and status text instead of actions. Done: a hover/focus menu with **Download file** (`<a href="/api/downloads/{id}/file" download>`) and **Delete** (two-step: "Delete" then "Confirm delete"; errors inline).
- Empty states: "No downloads yet. Paste a URL above." / "Nothing matches “{q}”."

- [ ] **Step 1: Write the failing test**

```ts
expect(libraryItems([d1], [a1], "all").map((j) => j.id)).toEqual([a1.id, d1.id]);
expect(libraryItems([d1], [a1], "downloading")).toEqual([a1]);
expect(libraryItems([video, audio], [], "audio")).toEqual([audio]);
```

- [ ] **Step 2:** `pnpm test` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** `pnpm check` → PASS; in the browser at 1280 and 1440, both themes: grid, chips, search, delete and download work with real downloads.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): library grid with chips, search, download and delete"`

### Task 3.5: Settings screen

**Files:** Create: `apps/web/src/routes/Settings.svelte`

**Interfaces:**
- Form: Max concurrent downloads (1–5, note "Applies after restart."), Proxy URL, Cookies file path, Downloads folder (placeholder shows "Default from server config"), Theme (`ThemeSelect`), **Save** ("Settings saved." on success, `messageFor(err)` on error), **Reset to defaults** (two-step confirm). A diagnostics panel shows only when `level === "warning"`, listing `messages`.

- [ ] **Step 1: Implement** (craft floor first).
- [ ] **Step 2: Verify** `pnpm check` → PASS; in the browser: save, reload shows saved values, max 9 shows the validation message, reset restores defaults, the old UI's settings page shows the same values.
- [ ] **Step 3: Commit** `git add -A && git commit -m "feat(web): settings screen"`

### Task 3.6: e2e for Queue and Library

**Files:**
- Modify: `apps/server/tests/e2e_server.py`
- Create: `apps/web/e2e/{queue,library}.spec.ts`

**Interfaces:**
- `e2e_server.py` seeds at import (after migrations run in the lifespan, so seed inside a startup hook registered on `app.router.on_startup`, or via an extra lifespan wrapper): one `done` row "Seeded video" with a real 4-byte file in `YT_DOWNLOADS_DIR`, and one `queued` row "Slow video" with URL `https://e2e.test/slow`.
- Stub `run_download(url, …, progress_hook)`: for URLs containing `slow`, call `progress_hook({"status": "downloading", "_percent_str": f"{p}%"})` for p = 1..100 with 0.2 s sleeps (the real hook raises `DownloadCancelled` when cancel is requested); otherwise write `<output_dir>/<last path segment>.mp4` with 4 bytes, call the hook with `status="finished", filename=...`, and return `DownloadResult(path, 4, "mp4", 1080)`.

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
  await card.hover(); await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Confirm delete" }).click();
  await expect(card).toHaveCount(0);
});
```

- [ ] **Step 2:** `pnpm e2e` → PASS (fix stubs/markup until it does; keep the accessible names).
- [ ] **Step 3: Commit** `git add -A && git commit -m "test(e2e): queue cancel and library delete"`
