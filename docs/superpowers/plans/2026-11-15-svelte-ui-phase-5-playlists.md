# Phase 5: Playlists and multiple URLs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paste a playlist (or several URLs) in the new UI, see every video at once, choose one quality for all, watch each selected video get checked (badges for below-cap, custom and unavailable), override single videos in a side panel, and add them all in one go once checking is done. The new UI now covers everything the old one does.

**Parent plan:** `docs/superpowers/plans/2026-11-15-svelte-ui.md`, section "Phase 5: Playlists and multiple URLs". The tasks below are copied from it verbatim. If they ever differ, the parent plan wins.

**Phase index:** `docs/superpowers/plans/2026-11-15-svelte-ui-phases.md`

**Spec:** `docs/superpowers/specs/2026-11-15-svelte-ui-design.md`

**Prerequisites:** Phase 4.

**Tasks:** Task 5.1 Lookup API, Task 5.2 Playlist logic: checker, badges, selection and job building, Task 5.3 Playlist screen.

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

4. **Late replies after the person moved on.** They fetch URL A, then URL B before A answers; or they leave a playlist page while lookups are running. A's answer must not replace B's view, and lookups finishing after leaving must not start new ones or change the page. Tests: `latest` test (Task 2.2), `checker ignores results after stop` (Task 5.2).

The numbers are the parent plan's Review Focus numbers. The tests that pin them are in this phase's tasks.

## File Structure

See the parent plan's "File Structure" for the final layout. This phase touches only the files named in its tasks' **Files** blocks.

---

## Phase 5: Playlists and multiple URLs

**Usable result:** paste a playlist (or several URLs) in the new UI, see every video at once, choose one quality for all, watch each selected video get checked (badges for below-cap, custom and unavailable), override single videos in a side panel, and add them all in one go once checking is done. The new UI now covers everything the old one does.

### Task 5.1: Lookup API

**Files:**
- Modify: `apps/server/app/api/fetch.py`, `apps/server/app/schemas.py`
- Test: `apps/server/tests/api/test_lookup_api.py`

**Interfaces:**
- `class LookupRequest(BaseModel): url: str = Field(min_length=1); use_proxy: bool = False; use_cookies: bool = False`
- `POST /api/lookup` (`LookupRequest`) → `VideoDetails` via `downloader.extract_info(url, noplaylist=True, ...)` and `video_details`. yt-dlp failure → 502 with `friendly_ytdlp_error`'s code and message. A result that has `entries` (the URL is a playlist) → 422 `not_a_video` "This URL is a playlist, not a single video."

- [ ] **Step 1: Write the failing tests**

```python
def test_lookup_returns_details(client, monkeypatch): ...      # best_short_side 720 for a 1280x720-only stub
def test_lookup_uses_noplaylist(client, monkeypatch): ...      # captured kwargs["noplaylist"] is True
def test_lookup_failure_is_502_with_friendly_message(client, monkeypatch): ...  # stub raises "HTTP Error 403: Forbidden" → code "http_forbidden"
def test_lookup_playlist_url_is_422(client, monkeypatch): ...
```

- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** `pnpm typegen && pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): single-video lookup for playlist checking"`

### Task 5.2: Playlist logic: checker, badges, selection and job building

**Files:**
- Create: `apps/web/src/lib/{checker.ts,badges.ts,playlist.ts}`
- Test: `apps/web/test/{checker,badges,playlist}.test.ts`

**Interfaces:**
- `lib/checker.ts`:
  ```ts
  export const CHECK_CONCURRENCY = 2;
  export type CheckResult = { ok: true; details: VideoDetails } | { ok: false; message: string };
  export function createChecker(opts: {
    lookup: (url: string) => Promise<VideoDetails>;
    onResult: (index: number, result: CheckResult) => void;
    concurrency?: number;
  }): { want(index: number, url: string): void; drop(index: number): void; stop(): void };
  ```
  `want` queues an index once (ignored if queued, running or done); `drop` removes a queued index (a running one finishes and still reports); at most `concurrency` lookups run; after `stop()` nothing new starts and late results are not reported. Errors become `{ ok: false, message: messageFor(err) }`.
- `lib/badges.ts`:
  ```ts
  export type Badge = { kind: "below"; label: string } | { kind: "custom"; label: string } | { kind: "unavailable"; label: "Unavailable"; message: string };
  export function badgeFor(entry: EntryState, cap: QualityCap): Badge | null;
  ```
  Order: unavailable first; then custom override → label `"{h}p · custom"` (h = short side of the chosen video stream, or `"audio · custom"` when only audio is chosen, or `"{cap label} · custom"` when the override has no exact ids); then `isBelowCap(cap, best)` → `"{best}p max"`; else null.
- `lib/playlist.ts`:
  ```ts
  export type Override = { selection: Selection; subtitles: boolean; outputTemplate: string; audioBitrate: string };
  export type EntryState = { entry: SourceEntry; selected: boolean; check: "idle" | "checking" | CheckResult; override: Override | null };
  export type Header = { cap: QualityCap; subtitles: boolean; outputTemplate: string; audioBitrate: string };
  export function initialEntries(result: SourcesResult): EntryState[];   // all selected except error entries; entries with `details` start as checked ok
  export function setSelected(entries: EntryState[], index: number, selected: boolean): EntryState[];  // unavailable can't be selected
  export function selectAll(entries: EntryState[], selected: boolean): EntryState[];  // skips unavailable
  export function applyResult(entries: EntryState[], index: number, r: CheckResult): EntryState[];  // failure → unavailable and deselected
  export type AddState = { kind: "empty" } | { kind: "checking"; done: number; total: number } | { kind: "ready"; count: number };
  export function addState(entries: EntryState[]): AddState;
  export function buildJobs(entries: EntryState[], header: Header): JobCreate[];
  ```
  `buildJobs`: selected entries with an ok check only, in index order; each job carries url/title/uploader/duration/thumbnail from the details (falling back to the entry), `quality_cap: header.cap`, and either the header's subtitles/template/bitrate (no ids) or the override's selection ids, subtitles, template and bitrate; blank strings → null.

- [ ] **Step 1: Write the failing tests**

```ts
// checker.test.ts (deferred promises)
it("never runs more than 2 lookups at once", ...);
it("does not look up the same index twice", ...);
it("drop removes a queued index", ...);
it("checker ignores results after stop", ...);   // resolve a running lookup after stop → onResult not called, nothing new started
// badges.test.ts
expect(badgeFor(okEntry(720), "1080")).toEqual({ kind: "below", label: "720p max" });
expect(badgeFor(okEntry(1080), "1080")).toBeNull();
expect(badgeFor(okEntry(720), "best")).toBeNull();
expect(badgeFor(customEntry({ videoShortSide: 1440 }), "1080")).toEqual({ kind: "custom", label: "1440p · custom" });
expect(badgeFor(failedEntry("Video unavailable"), "1080")?.kind).toBe("unavailable");
// playlist.test.ts
expect(addState([checking(), ok()])).toEqual({ kind: "checking", done: 1, total: 2 });
expect(addState(allDeselected)).toEqual({ kind: "empty" });
expect(setSelected(withUnavailable, 0, true)[0].selected).toBe(false);
expect(buildJobs([okWithOverride, okPlain, deselected], header)).toEqual([
  expect.objectContaining({ video_format_id: "137", audio_format_id: "140", quality_cap: "1080" }),
  expect.objectContaining({ video_format_id: null, subtitles: true, quality_cap: "1080" }),
]);
```

- [ ] **Step 2:** `pnpm test` → FAIL. **Step 3:** implement. **Step 4:** `pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): playlist checker, badges and job building"`

### Task 5.3: Playlist screen

**Files:**
- Create: `apps/web/src/routes/ListView.svelte`, `apps/web/src/components/{EntryCard,OverridePanel}.svelte`, `apps/web/e2e/playlist.spec.ts`
- Modify: `apps/web/src/routes/Fetch.svelte` (replace the Phase 4 note with `ListView`), `apps/server/tests/e2e_server.py`

**Interfaces:**
- `ListView.svelte`: header — title (or "{N} sources" when `title` is null), `N videos · M selected`, Select all / Select none, `QualitySelect` (default `DEFAULT_CAP`), Subtitles toggle, Advanced menu (output template, audio bitrate), and the Add button whose label follows `addState`: `Checking k / M…` (disabled), `Add M to queue`, or disabled `Add to queue` when empty. "Skipped N" note under the header when `skipped > 0`. One scrolling grid of `EntryCard`, no pagination. On mount: a checker; `want` every selected entry without a result; selecting an entry calls `want`, deselecting calls `drop`; `onDestroy` and route changes call `stop()`. Changing the cap only re-renders badges. Add → `POST /api/downloads` with `buildJobs`; success "Added M to queue." with a link to the Queue.
- `EntryCard.svelte`: checkbox, thumbnail (placeholder until details arrive), title, duration, badge from `badgeFor` (amber below, red custom, error tone unavailable with its message on hover and on click), a small spinner while checking. Clicking the card (not the checkbox) opens `OverridePanel`.
- `OverridePanel.svelte`: right-side panel with a Playlist setting / Custom switch; Custom shows `FormatPicker` for that entry's `details.picker`, Subtitles, output template, audio bitrate; Close button and Escape close it. Disabled for entries that aren't checked yet ("Still checking…").
- e2e stub data: `https://e2e.test/playlist` flat result with title "E2E Playlist" and 3 entries: `https://e2e.test/v/a` (1080p), `https://e2e.test/v/b` (720p only), `https://e2e.test/v/gone`. `extract_info` (lookup) for `/v/gone` raises "Video unavailable"; others return details after a 0.3 s sleep.

- [ ] **Step 1: Write the e2e spec**

```ts
test("fetch playlist, wait for checks, add", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("textbox", { name: /paste/i }).fill("https://e2e.test/playlist");
  await page.getByRole("button", { name: "Fetch" }).click();
  await expect(page.getByText("E2E Playlist")).toBeVisible();
  await expect(page.getByRole("button", { name: /Checking \d+ \/ 3/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Add 2 to queue" })).toBeEnabled();
  await expect(page.getByText("720p max")).toBeVisible();
  await expect(page.getByText("Unavailable")).toBeVisible();
  await page.getByRole("button", { name: "Add 2 to queue" }).click();
  await expect(page.getByText("Added 2 to queue.")).toBeVisible();
});
```

- [ ] **Step 2:** `pnpm e2e` → FAIL.
- [ ] **Step 3: Implement** (craft floor first; follow `DESIGN.md`).
- [ ] **Step 4:** `pnpm check && pnpm e2e` → PASS. With `pnpm dev` and a real 20–50 video playlist: Add stays disabled until every selected video is checked; at most 2 lookups run at once (server log); leaving the page mid-check stops further lookups (server log goes quiet); an override shows the red custom badge and the queued job uses its format.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): playlist screen with checking, badges and overrides"`
