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

**State at the start (Phase 4 merged):** `POST /api/sources` returns `SourcesResult` (`kind: "list"` with `entries`, `title`, `skipped`); `POST /api/downloads` takes up to 500 `JobCreate`s with `quality_cap` or exact ids; `services/sources.py` has `video_details(info, url)` and `_is_playlist(info)`; the web app has `QualitySelect`, `FormatPicker`, `lib/{quality,format-picker,fetch-options,latest,errors,api}.ts`; `Fetch.svelte` shows a "Playlists open in the classic UI for now." note for `kind === "list"`; `tests/e2e_server.py` stubs `downloader.extract_info` and `extract_flat_info` with one `_stub_info`.

### Task 5.1: Lookup API

**Files:**

- Modify: `apps/server/app/api/fetch.py`, `apps/server/app/schemas.py`, `apps/server/app/services/sources.py`
- Test: `apps/server/tests/api/test_lookup_api.py`

**Interfaces:**

- `class LookupRequest(BaseModel): url: str = Field(min_length=1); use_proxy: bool = False; use_cookies: bool = False`
- `services/sources.py`: `def lookup_video(url: str, *, extract_full: Callable[..., dict], proxy: str | None, cookies_file: str | None) -> VideoDetails`. Calls `extract_full(url, noplaylist=True, proxy=proxy, cookies_file=cookies_file)`; if `_is_playlist(info)` raises `NotAVideoError` (a new `ValueError` subclass in `sources.py`); else returns `video_details(info, url)`.
- `POST /api/lookup` (`LookupRequest`) → `VideoDetails`. Resolves proxy and cookies exactly like `/sources` (`resolve_runtime_settings`, honouring `use_proxy` / `use_cookies`) and passes `extract_full=lambda *a, **k: downloader.extract_info(*a, **k)` so tests can monkeypatch `downloader.extract_info`. `NotAVideoError` → 422 `not_a_video` "This URL is a playlist, not a single video." (caught **before** the generic handler); any other exception → 502 with `friendly_ytdlp_error`'s code and message.

- [ ] **Step 1: Write the failing tests** (same style as `test_sources_api.py`: monkeypatch `downloader.extract_info`)

```python
def test_lookup_returns_details(client, monkeypatch): ...      # best_short_side 720 for a 1280x720-only stub
def test_lookup_uses_noplaylist(client, monkeypatch): ...      # captured kwargs["noplaylist"] is True
def test_lookup_failure_is_502_with_friendly_message(client, monkeypatch): ...  # stub raises "HTTP Error 403: Forbidden" → code "http_forbidden"
def test_lookup_playlist_url_is_422(client, monkeypatch): ...  # stub returns {"_type": "playlist", "entries": []} → code "not_a_video"
def test_lookup_passes_proxy_only_when_asked(client, monkeypatch): ...  # save proxy_url via PUT /api/settings; use_proxy false → kwargs["proxy"] is None; true → the saved URL
```

- [ ] **Step 2:** `cd apps/server && uv run pytest tests/api/test_lookup_api.py` → FAIL. **Step 3:** implement. **Step 4:** `pnpm typegen && pnpm check` → PASS (`api.gen.ts` now has `/api/lookup` and `LookupRequest`).
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(api): single-video lookup for playlist checking"`

### Task 5.2: Playlist logic: checker, badges, selection and job building

**Files:**

- Create: `apps/web/src/lib/{checker.ts,badges.ts,playlist.ts,duration.ts}`
- Modify: `apps/web/src/routes/VideoView.svelte` (import `formatDuration` from `lib/duration.ts` instead of its local copy; no other change)
- Test: `apps/web/test/{checker,badges,playlist}.test.ts`

**Interfaces:**

- `lib/duration.ts`: `export function formatDuration(total: number): string` — moved unchanged from `VideoView.svelte` (`m:ss`, or `h:mm:ss` from one hour).
- `lib/checker.ts`:
  ```ts
  export const CHECK_CONCURRENCY = 2;
  export type CheckResult =
    | { ok: true; details: VideoDetails }
    | { ok: false; message: string };
  export function createChecker(opts: {
    lookup: (url: string) => Promise<VideoDetails>;
    onResult: (index: number, result: CheckResult) => void;
    concurrency?: number;
  }): {
    want(index: number, url: string): void;
    drop(index: number): void;
    stop(): void;
  };
  ```
  `want` queues an index (ignored if already queued, running or done); `drop` removes a queued index, so a later `want` queues it again (a running one finishes and still reports); at most `concurrency` lookups run, started in the order they were wanted; after `stop()` nothing new starts and late results are not reported. A rejected lookup becomes `{ ok: false, message: messageFor(err) }`. `VideoDetails` is `components["schemas"]["VideoDetails"]`.
- `lib/playlist.ts`:
  ```ts
  export type Override = {
    selection: Selection;
    subtitles: boolean;
    outputTemplate: string;
    audioBitrate: string;
  };
  export type Check = "idle" | "checking" | CheckResult;
  export type EntryState = {
    entry: SourceEntry;
    selected: boolean;
    check: Check;
    override: Override | null;
  };
  export type Header = {
    cap: QualityCap;
    subtitles: boolean;
    outputTemplate: string;
    audioBitrate: string;
  };
  export function initialEntries(result: SourcesResult): EntryState[];
  export function isUnavailable(e: EntryState): boolean; // check is { ok: false }
  export function setSelected(
    entries: EntryState[],
    index: number,
    selected: boolean,
  ): EntryState[];
  export function selectAll(
    entries: EntryState[],
    selected: boolean,
  ): EntryState[];
  export function applyResult(
    entries: EntryState[],
    index: number,
    r: CheckResult,
  ): EntryState[];
  export function setOverride(
    entries: EntryState[],
    index: number,
    o: Override | null,
  ): EntryState[];
  export type AddState =
    | { kind: "empty" }
    | { kind: "checking"; done: number; total: number }
    | { kind: "ready"; count: number };
  export function addState(entries: EntryState[]): AddState;
  export function buildJobs(entries: EntryState[], header: Header): JobCreate[];
  ```
  The `check` field is the single source of truth for what the screen asks the checker to do:
  - `initialEntries`: an entry with `error_code` → `{ selected: false, check: { ok: false, message: error_message ?? "Unavailable" } }`; an entry with `details` → `{ selected: true, check: { ok: true, details } }`; any other entry → `{ selected: true, check: "checking" }`. `override: null` for all.
  - `setSelected` / `selectAll`: never select an unavailable entry. Selecting an `"idle"` entry sets `check: "checking"`; deselecting a `"checking"` entry sets `check: "idle"`; an entry with a result keeps it.
  - `applyResult`: ok → stores it (whether or not the entry is still selected); failure → stores it and deselects.
  - `addState`: `total` = selected entries, `done` = selected entries with an ok check. `total === 0` → `empty`; `done < total` → `checking`; else `ready` with `count = total`.
  - `buildJobs`: selected entries with an ok check only, in index order. Each job: `url`, `title`, `uploader`, `duration`, `thumbnail` from `details` (falling back to the entry's field when the details' field is null), `quality_cap: header.cap`. Without an override: `subtitles`, `output_template`, `audio_bitrate` from the header and both format ids `null`. With an override: `video_format_id` / `audio_format_id` from its selection, and its `subtitles`, template and bitrate. Blank or whitespace-only strings → `null`.
- `lib/badges.ts`:

  ```ts
  export type Badge =
    | { kind: "below"; label: string }
    | { kind: "custom"; label: string }
    | { kind: "unavailable"; label: "Unavailable"; message: string };
  export function badgeFor(e: EntryState, cap: QualityCap): Badge | null;
  ```

  Order: unavailable first (`message` from the failed check); then a custom override → `"{h}p · custom"` where h is `min(width, height)` of the chosen video stream row in `details.picker.video_streams` (or its `height` when width is null); `"audio · custom"` when only an audio id is chosen; `"{cap label} · custom"` (label from `CAP_OPTIONS`) when the override has no exact ids; then, for an ok check, `isBelowCap(cap, details.best_short_side)` → `"{best}p max"`; else `null` (also `null` while `"idle"` or `"checking"`).

- [ ] **Step 1: Write the failing tests** (build `EntryState`s with small local helpers; `checker.test.ts` uses deferred promises and `await Promise.resolve()` / `vi.waitFor` to flush)

```ts
// checker.test.ts
it("never runs more than 2 lookups at once", ...);       // want 0..4 → 2 started; resolve one → third starts
it("does not look up the same index twice", ...);         // want(0) twice, and again after it reported
it("drop removes a queued index", ...);                   // want 0,1,2 then drop(2) → resolving 0 and 1 never starts 2
it("a rejected lookup reports ok: false with the message", ...);
it("checker ignores results after stop", ...);            // resolve a running lookup after stop → onResult not called, nothing new started
// badges.test.ts
expect(badgeFor(okEntry(720), "1080")).toEqual({ kind: "below", label: "720p max" });
expect(badgeFor(okEntry(1080), "1080")).toBeNull();
expect(badgeFor(okEntry(720), "best")).toBeNull();
expect(badgeFor(checkingEntry(), "1080")).toBeNull();
expect(badgeFor(customEntry({ videoShortSide: 1440 }), "1080")).toEqual({ kind: "custom", label: "1440p · custom" });
expect(badgeFor(customEntry({ audioOnly: true }), "1080")).toEqual({ kind: "custom", label: "audio · custom" });
expect(badgeFor(failedEntry("Video unavailable"), "1080")).toEqual({ kind: "unavailable", label: "Unavailable", message: "Video unavailable" });
// playlist.test.ts
expect(initialEntries(resultWithErrorEntry)[1]).toMatchObject({ selected: false, check: { ok: false } });
expect(initialEntries(resultWithPlainEntry)[0]).toMatchObject({ selected: true, check: "checking" });
expect(setSelected(withUnavailable, 0, true)[0].selected).toBe(false);
expect(setSelected([checking()], 0, false)[0].check).toBe("idle");
expect(setSelected([idle()], 0, true)[0].check).toBe("checking");
expect(applyResult([checking()], 0, { ok: false, message: "x" })[0].selected).toBe(false);
expect(addState([checking(), ok()])).toEqual({ kind: "checking", done: 1, total: 2 });
expect(addState([ok(), ok(), failed()])).toEqual({ kind: "ready", count: 2 });
expect(addState(allDeselected)).toEqual({ kind: "empty" });
expect(buildJobs([okWithOverride, okPlain, deselected], header)).toEqual([
  expect.objectContaining({ video_format_id: "137", audio_format_id: "140", quality_cap: "1080" }),
  expect.objectContaining({ video_format_id: null, subtitles: true, output_template: null, quality_cap: "1080" }),
]);
```

- [ ] **Step 2:** `pnpm test` → FAIL. **Step 3:** implement. **Step 4:** `pnpm check` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): playlist checker, badges and job building"`

### Task 5.3: Playlist screen

**Files:**

- Create: `apps/web/src/routes/ListView.svelte`, `apps/web/src/components/{EntryCard,OverridePanel}.svelte`, `apps/web/e2e/playlist.spec.ts`
- Modify: `apps/web/src/routes/Fetch.svelte` (replace the "classic UI" note with `{#key result}<ListView {result} />{/key}`), `apps/server/tests/e2e_server.py`

**Interfaces:**

- `ListView.svelte` (`{ result: SourcesResult }`):
  - Header: title (or "{N} sources" when `title` is null), `N videos · M selected`, Select all / Select none, `QualitySelect` (default `DEFAULT_CAP`), Subtitles checkbox, an Advanced disclosure (output template, audio bitrate; same inputs and placeholders as `VideoView`), and the Add button whose label follows `addState`: `Checking k / M…` (disabled), `Add M to queue`, or disabled `Add to queue` when empty. "Skipped N" note under the header when `skipped > 0`.
  - One scrolling grid of `EntryCard`, no pagination.
  - Checking: `entries = $state(initialEntries(result))`. One checker per mount, created with `lookup = (url) => call(api.POST("/api/lookup", { body: { url, use_proxy, use_cookies } }))` where the options come from `readFetchOptions(localStorage.getItem(FETCH_OPTIONS_KEY))`, and `onResult = (i, r) => entries = applyResult(entries, i, r)`. An effect keeps the checker in step with `entries`: `want` every entry whose check is `"checking"`, `drop` every entry whose check is `"idle"` (the checker ignores repeats). The effect's teardown on unmount calls `stop()`; leaving the route unmounts `Fetch`, and a new fetch remounts `ListView` via `{#key}`.
  - Changing the cap only re-renders badges (no new lookups).
  - Add: guarded against double clicks (`adding`, as in `VideoView`) → `POST /api/downloads` with `{ jobs: buildJobs(entries, header) }`; success → "Added M to queue." with a link to `#/queue` (`role="status"`); failure → `messageFor(err)` in `role="alert"`.
- `EntryCard.svelte` (`{ state: EntryState; cap: QualityCap; onToggle(selected: boolean); onOpen() }`): `<article>` with a checkbox labelled "Select {title}", thumbnail (`loading="lazy"`; neutral placeholder until there is one), title (entry title, else details title, else URL), duration via `formatDuration`, the badge from `badgeFor` (below → `warn`, custom → `accent`, unavailable → `danger`), and a small spinner with an accessible "Checking" label while `check === "checking"`. Clicking the card body (not the checkbox) calls `onOpen`. For an unavailable entry the checkbox is disabled and the error message shows in a `title` on hover and in a small popover on click instead of opening the panel.
- `OverridePanel.svelte` (`{ state: EntryState; header: Header; onChange(o: Override | null); onClose() }`): right-side panel with a "Playlist setting / Custom" switch. Choosing Custom creates an override from the header values with no exact ids; choosing Playlist setting sets it back to `null`. Custom shows `FormatPicker` (Video and Audio) for `details.picker`, Subtitles, output template and audio bitrate. A Close button and Escape close it. While the entry is still `"checking"` (or `"idle"`) it shows "Still checking…" and no controls.
- e2e stubs (`tests/e2e_server.py`): split `_stub_info` into `_stub_flat` (bound to `extract_flat_info`) and `_stub_full` (bound to `extract_info`); both keep handling `_VIDEO_URLS` as today.
  - `_stub_flat("https://e2e.test/playlist")` → `{"_type": "playlist", "title": "E2E Playlist", "entries": [{"url": "https://e2e.test/v/a", "title": "Video A"}, {"url": "https://e2e.test/v/b", "title": "Video B"}, {"url": "https://e2e.test/v/gone", "title": "Video Gone"}]}`.
  - `_stub_full` for `/v/a` (1080p video + audio formats) and `/v/b` (720p video + audio only) returns details after `time.sleep(1.0)`, long enough for the test to see the Checking state; `/v/gone` raises `RuntimeError("Video unavailable")`.

- [ ] **Step 1: Write the e2e spec**

```ts
test("fetch playlist, wait for checks, add", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/playlist");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "E2E Playlist" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Checking \d+ \/ 3/ }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Add 2 to queue" }),
  ).toBeEnabled();
  await expect(page.getByText("720p max", { exact: true })).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Add 2 to queue" }).click();
  await expect(page.getByText("Added 2 to queue.")).toBeVisible();
});
```

- [ ] **Step 2:** `pnpm e2e` → FAIL.
- [ ] **Step 3: Implement** (read impeccable's `reference/craft-floor.md` first; follow `PRODUCT.md` and `DESIGN.md`).
- [ ] **Step 4:** `pnpm check && pnpm e2e` → PASS (all specs, including `video.spec.ts` after the stub split). With `pnpm dev` and a real 20–50 video playlist: Add stays disabled until every selected video is checked; at most 2 lookups run at once (server log); leaving the page mid-check stops further lookups (server log goes quiet); an override shows the red custom badge and the queued job uses its format; at 1280 and 1440 widths in both themes nothing overlaps or clips, and the override panel doesn't cover the Add button.
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(web): playlist screen with checking, badges and overrides"`
