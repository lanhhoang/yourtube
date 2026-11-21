# Phase 6: Library: sort and filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the All / Downloading / Video / Audio only chips with sort and filter (type, channel, playlist), remembered across visits.

**Usable result:** Library toolbar: search · Sort (Newest, Oldest, Title A–Z, Longest, Largest) · Filter (Type, Channel, Playlist; a bottom sheet on phones) · Select. Active filters show as removable pills; the choice survives a reload.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md` §6

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 13, 14, 15. The tasks below match it; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phases 1–5 merged (`main` @ `fb162a1`). `JobOut` already has `playlist_title`/`playlist_channel` (Phase 3), and Library has Select mode (Phase 5). No server or schema changes in this phase. Work on branch `20261121-library-queue-subtitles-phase-6-sort-filter`.

**Revised 2026-11-21 after a readiness review against `main` @ `fb162a1`.** Fixes:

- **Stale filters vs search.** `done` is the server-side search result while `q` is set. The old rule ("a channel not present in the items is ignored, and the component drops it") would clear a real channel filter as soon as a search hid that channel. Now `filterItems` applies the view strictly, and stale values are dropped by a separate `dropStale(view, facets)` that runs only against the **unsearched** list (`fullFacets`, refreshed on every load with an empty `q`). Facets for the panel also come from `fullFacets`, so options don't vanish while searching or filtering.
- **Flaky e2e assertion.** `Slow video` is seeded `queued`, workers run, and the stub finishes it after about 20 s (or `queue.spec.ts` cancels it). "Slow video is not in the library" was racy. Task 13 now stubs `/api/queue` with an active job that exists only in that response, and asserts it isn't shown.
- **E2E file filters go without `--`.** `pnpm e2e -- library.spec.ts` forwards a literal `--` and runs the whole suite. Use `pnpm e2e library.spec.ts phone.spec.ts`.
- **Motion tokens.** There is no 150 ms token. The popover uses `--duration-fast` (120 ms) and `--ease-out`. `app.css` already removes motion under `prefers-reduced-motion`, so nothing extra is needed.
- **Dead code from Task 13.** `JobCard` is used only by Library. Once Library is done-only, its in-progress branches (progress bar, "Downloading/Queued" line, `inProgress`) are unreachable, so they go. The same goes for Library's `noJobs` and the `status === "done"` filter in `visibleDone`.
- **One Filters dialog at a time.** Library picks the popover or the sheet with `new MediaQuery("(min-width: 768px)")` from `svelte/reactivity` (as `ListView.svelte` does), so only one `dialog` named "Filters" exists.
- **Esc.** Library already listens on `window` for Esc to leave Select mode, and the sheet's Esc keydown still bubbles there. Esc with the popover or sheet open closes only that.
- **Deterministic e2e seeds.** Other spec files add rows in parallel (`E2E Video`, `E2E Playlist` entries, uploader `E2E`). The new tests pick options by value, never "the second channel", and assert on the dedicated rows only. The seeded rows have no file, so the startup library move and the ffprobe backfill skip them.
- **Selection clears on q, type, channel or playlist changes**, as the spec says (search or filter). A sort change keeps the selection, because it doesn't change which items are visible.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. No API schema change in this phase, so `api.gen.ts` stays as it is.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. No new dependencies.
- `DESIGN.md` is the visual contract: red is the only accent, WCAG AA in both themes, 8 px control radius, pill buttons, 120–200 ms ease-out motion, 2 px `fg` focus outline, status never shown by colour alone, no shadows except menus (offset 0 8px, blur 24px, 40% black). Phone is below 768 px: 44 px tap targets, 16 px inputs.
- UI tasks: before editing, read `~/.agents/skills/impeccable/reference/craft-floor.md` and `reference/operate.md` (this is an Operate surface: precision and restraint, known patterns). Use `~/.config/pi/skills/design-taste-frontend/SKILL.md` §6 "Never" as the anti-slop checklist. No new visual language, no decorative extras.
- Bulk delete touches only `done` rows and their own files and sidecars, and always confirms first.
- Follow the existing test layout: Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `apps/server/tests/e2e_server.py`). Spec files run in parallel against one e2e server, and tests within a file run in order.
- E2E file filters go without `--`: `pnpm e2e library.spec.ts`. If Playwright's browser is missing, prefix `PW_CHANNEL=chrome`.

## Review Focus

1. A stored channel/playlist that no longer exists is ignored, not an empty library. A channel that a search merely hides is **not** stale.
2. Facets come from the unsearched, unfiltered list, so options don't vanish while filtering or searching.
3. No regression for search or Select mode: sort/filter apply after the server-side `q` search, and "Select all" covers exactly the visible (filtered) items. E2E tests that delete rows don't break sort/filter tests (dedicated seeded rows).

---

### Task 13: Library shows finished items only; chips removed

**Files:**

- Modify: `apps/web/src/lib/library.ts`, `apps/web/src/routes/Library.svelte`, `apps/web/src/components/JobCard.svelte`, `apps/web/test/library.test.ts`, `apps/web/e2e/library.spec.ts`
- Delete: `apps/web/src/components/Chips.svelte`

**Interfaces:**

- Produces: `lib/library.ts` no longer exports `Chip` or `libraryItems`. `qualityLabel`, `formatSize`, `watchMeta`, `toggle` and `bulkResultText` stay.

`Library.svelte` keeps the `queue` prop and its reload-on-finish effect (that's how new downloads appear), but renders `done` only: `items = done` for now. Remove `chip`, `noJobs`, and the `status === "done"` filter in `visibleDone` (every item is done). Empty states: `searching && done.length === 0` → `Nothing matches “q”.`; `done.length === 0` → `No downloads yet. Paste a URL above.` Drop the `Nothing here yet.` branch. In-progress work is in the Queue tab (badge count), so nothing replaces "Downloading".

`JobCard.svelte`: remove `inProgress`, the progress bar and the "Downloading/Queued" line. The title is a link unless `selecting`, and the checkbox shows whenever `selecting` (`picking` becomes `selecting`).

- [ ] **Step 1: Update tests.**
  - Delete the two `libraryItems` tests and the import.
  - Add e2e `"library lists finished downloads only"` in `library.spec.ts`. Stub `**/api/queue` with `page.route` (as in `queue.spec.ts`) to return one `active` job titled `Stubbed active` (id 9201) and empty `completed`. Go to `#/`. `Seeded video`'s link is visible, `getByRole("article").filter({ hasText: "Stubbed active" })` has count 0, and `getByRole("radiogroup", { name: "Filter" })` has count 0.
- [ ] **Step 2: Run them and see them fail.** `pnpm e2e library.spec.ts`
- [ ] **Step 3: Implement.** Remove `Chips.svelte`, `Chip`, `libraryItems` and the JobCard in-progress branches.
- [ ] **Step 4: Verify.** `pnpm check` and `pnpm e2e library.spec.ts phone.spec.ts`.
- [ ] **Step 5: Commit.** `git commit -m "refactor: library lists finished downloads only; drop the chips"`

### Task 14: Sort and filter logic

**Files:**

- Modify: `apps/web/src/lib/library.ts`, `apps/web/test/library.test.ts`

**Interfaces:**

- Consumes: `JobOut.playlist_title`, `uploader`, `media_kind`, `finished_at`, `created_at`, `title`, `duration`, `file_size`
- Produces:

```ts
export type SortKey =
  | "added-desc"
  | "added-asc"
  | "title"
  | "duration"
  | "size";
export type KindFilter = "any" | "video" | "audio";
export type LibraryView = {
  sort: SortKey;
  kind: KindFilter;
  channel: string | null;
  playlist: string | null;
};
export const DEFAULT_VIEW: LibraryView; // { sort: "added-desc", kind: "any", channel: null, playlist: null }
export const SORT_OPTIONS: { value: SortKey; label: string }[];
// labels: "Newest first", "Oldest first", "Title A–Z", "Longest first", "Largest first"
export function sortItems(items: JobOut[], sort: SortKey): JobOut[]; // new array, stable
export function filterItems(items: JobOut[], view: LibraryView): JobOut[]; // strict AND
export type Facet = { value: string; count: number };
export type Facets = { channels: Facet[]; playlists: Facet[] };
export function facets(items: JobOut[]): Facets;
export function dropStale(view: LibraryView, f: Facets): LibraryView; // same object when nothing is stale
export function activeFilterCount(view: LibraryView): number; // kind ≠ "any", channel, playlist
export function sameFilters(a: LibraryView, b: LibraryView): boolean; // kind, channel, playlist (not sort)
export const VIEW_KEY = "yt.library.view";
export function readView(raw: string | null): LibraryView; // tolerant: bad JSON or unknown values → defaults per field
export function saveView(view: LibraryView): void; // localStorage.setItem(VIEW_KEY, JSON.stringify(view))
```

Rules:

- "added" = `finished_at ?? created_at` (ISO strings; compare with `Date.parse`). Title sort uses `localeCompare(…, undefined, { sensitivity: "base", numeric: true })`, with a null title sorting last. Duration and size sort descending, with nulls last. Ties keep the input order.
- Channel = `uploader`. Playlist = `playlist_title`. Facets are distinct, non-empty values with counts, sorted by `localeCompare` on the value.
- `filterItems` applies kind, channel and playlist with AND, strictly: a channel with no matching items gives an empty result. Staleness is `dropStale`'s job, not `filterItems`'s.
- `dropStale` sets `channel`/`playlist` to `null` when the value isn't in `f.channels`/`f.playlists`. It returns the same object when nothing changes, so an `$effect` that assigns it doesn't loop.
- `readView` keeps `channel`/`playlist` only when they are non-empty strings.

- [ ] **Step 1: Write the failing tests:**
  - one per sort key, including nulls last and stable ties; "added" falls back to `created_at`
  - a kind + channel + playlist AND combination; a channel with no matches gives `[]`
  - `facets` counts and order, skipping null and empty values
  - `dropStale`: a stale channel and playlist become `null`; a valid view comes back as the same object (`toBe`)
  - `activeFilterCount` and `sameFilters` (a sort-only change is the same filters)
  - `readView` with `null`, `"{bad"`, `'{"sort":"nope","kind":"audio"}'` → `{ ...DEFAULT_VIEW, kind: "audio" }`, and `'{"channel":""}'` → `DEFAULT_VIEW`
- [ ] **Step 2: Run them and see them fail.** `pnpm test`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them and see them pass.** `pnpm check`
- [ ] **Step 5: Commit.** `git commit -m "feat: library sort and filter helpers"`

### Task 15: Toolbar, filter panel, pills and persistence

**Files:**

- Create: `apps/web/src/components/LibraryFilters.svelte`
- Modify: `apps/web/src/routes/Library.svelte`, `apps/server/tests/e2e_server.py`, `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`, `README.md`

**Interfaces:**

- Consumes: Task 14's exports; `BottomSheet` (`{ open, title, onclose, children }`); `MediaQuery` from `svelte/reactivity`
- Produces: `LibraryFilters` props `{ view: LibraryView (bindable), channels: Facet[], playlists: Facet[] }`. It renders the form fields and its own `Clear filters` button only. The container (popover or sheet) belongs to `Library.svelte`.

State in `Library.svelte`:

- `view = $state(readView(localStorage.getItem(VIEW_KEY)))`. An `$effect` calls `saveView(view)` on change.
- `fullFacets = $state<Facets | null>(null)`. `load()` sets it to `facets(rows)` whenever the query was empty, and `removed()`/bulk delete refresh it the same way when `q` is empty. The first load always has an empty `q`.
- An `$effect`: when `fullFacets` is set, `view = dropStale(view, fullFacets)`.
- `items = sortItems(filterItems(done, view), view.sort)`. `visibleDone = items.map((j) => j.id)`, so "Select all" covers what's visible.
- The selection clears when `q` changes or when `sameFilters` says the filters changed (track `view.kind`, `view.channel`, `view.playlist`, not `view.sort`).

Layout:

- Desktop toolbar row: `Library` heading · (right side) search · `Sort` select (visually hidden label "Sort", native `<select>` styled like `QualitySelect`) · `Filter` button (outlined pill like `Select`; reads `Filter · 2` when filters are active, with `aria-expanded`) · `Select`. Sort and Filter are hidden in the "No downloads yet" state.
- Filter opens a popover anchored under the button: `<div role="dialog" aria-label="Filters">`, `bg-surface border border-line-strong rounded-control p-4` with the menu shadow from `DESIGN.md`. It fades and moves in with opacity and translate at `--duration-fast`/`--ease-out`. It closes on Esc, on an outside pointerdown, or on the Filter button again. Focus moves to its first control on open and back to the Filter button on close. The window Esc handler closes the popover first, ignores Esc while the sheet is open (the sheet closes itself), and only leaves Select mode when neither is open.
- Phone (`!wide.current`): the search fills the first row. The second row is `Sort` select · `Filter` · `Select`, each ≥ 44 px and 16 px text. `Filter` opens `BottomSheet` titled "Filters" with the same `LibraryFilters` inside. Only one of popover/sheet is ever rendered.
- `LibraryFilters` fields: Type as a radiogroup named "Type" (Any / Video / Audio, styled like the old chips: `rounded-control bg-raised`, checked `bg-action text-on-action`). Channel as a `<select>` labelled "Channel" ("Any channel", then `name (count)`, value = name). Playlist as a `<select>` labelled "Playlist" ("Any playlist", then `name (count)`), hidden when there are no playlists. Changes apply immediately (no Apply button). `Clear filters` resets kind, channel and playlist and is disabled when none are active.
- Under the toolbar, when filters are active: removable pills `Video` or `Audio`, `Channel: X`, `Playlist: Y`, each with a ✕ button (`aria-label="Remove filter Channel: X"`; for type, `Remove filter Audio`), plus a `Clear filters` text button. Pills use `rounded-pill border border-line-strong`, with no accent colour.
- Empty states, in order: `searching && done.length === 0` → `Nothing matches “q”.`; `done.length === 0` → `No downloads yet. Paste a URL above.`; `items.length === 0` → `No videos match these filters.` plus a `Clear filters` button.
- README: a short "Library" subsection under Features covering Sort/Filter/Select (bulk delete), plus the subtitle languages rule (original language and real English, no auto-translated tracks) and the player tracks (off by default), and codecs/HDR on the Watch page.

Seeds in `e2e_server.py` (no files, so the library move and the backfill skip them; comment that only the Task 15 tests use them):

| title         | uploader | finished_at    | other                                                  |
| ------------- | -------- | -------------- | ------------------------------------------------------ |
| `Sort B`      | `Sorter` | `now - 1 day`  | `resolution_height=1080`, `duration=60`                |
| `Sort A`      | `Sorter` | `now - 2 days` | `resolution_height=1080`, `duration=600`               |
| `Sort audio`  | `Sorter` | `now - 3 days` | `resolution_height=None` (→ `media_kind: audio`)       |
| `Sort listed` | `Other`  | `now - 4 days` | `resolution_height=1080`, `playlist_title="Sort list"` |

All four rows are `status="done"`, `progress=100.0`, `media_format="mp4"`. Add `timedelta` to the `datetime` import.

- [ ] **Step 1: Write the failing e2e tests.** Assert only on the `Sort …` rows. Helper: `order = (page) => page.getByRole("article").filter({ hasText: /^Sort / }).allTextContents()`, or compare the index of each title in `getByRole("heading", { level: 3 }).allTextContents()`.
  - desktop `"sort by title"`: by default `Sort B` comes before `Sort A` (newest first). Pick `Title A–Z` in `getByLabel("Sort")`. Now `Sort A` comes before `Sort B`.
  - desktop `"filter by channel and clear"`: click `Filter`. In `getByRole("dialog", { name: "Filters" })`, `getByLabel("Channel").selectOption("Other")`. `Sort listed` is visible, `Sort A` has count 0, the button reads `Filter · 1`, and a `Channel: Other` pill is visible. Press Esc: the dialog closes. Click `Remove filter Channel: Other`: `Sort A` is back.
  - desktop `"filter by type audio"`: open Filter, check the `Audio` radio in the `Type` group. `Sort audio` is visible, and `Sort A` and `Sort listed` have count 0. Click `Clear filters` (outside the dialog): `Sort A` is back.
  - desktop `"a search keeps the channel filter"`: set channel `Other`, close the popover, type `Sort A` in the search. `No videos match these filters.` shows, and the `Channel: Other` pill is still there. Clear the search: `Sort listed` is visible again.
  - desktop `"view persists; a stale channel is dropped"`: set sort `Oldest first`, reload, and `getByLabel("Sort")` still has value `added-asc`. Then use `page.evaluate` to set `localStorage["yt.library.view"]` to `{"sort":"added-desc","kind":"any","channel":"Gone","playlist":null}` and reload. `Sort A` is visible and no `Channel: Gone` pill shows.
  - phone `"filters open in a sheet"` in `phone.spec.ts`: tap `Filter`. `getByRole("dialog", { name: "Filters" })` is visible. `expectTarget` passes on the sheet's `Close` button, each `Type` radio's label, and the Channel select. Fonts in `main select` and the sheet's selects are ≥ 16 px. No sideways scroll. `expectTarget` passes on the toolbar's `Sort`, `Filter` and `Select`.
- [ ] **Step 2: Run them and see them fail.** `pnpm e2e library.spec.ts phone.spec.ts`
- [ ] **Step 3: Implement.** Read `craft-floor.md`, `operate.md` and the taste skill's §6 first. Use only existing tokens.
- [ ] **Step 4: Verify.** Run `pnpm check` and `pnpm e2e` (the full suite, so parallel spec files are covered). Screenshot desktop 1440 and phone 390 in both themes: default, filters active (pills), the popover open, the sheet open, and the empty filtered state. Fix anything that breaks `DESIGN.md`.
- [ ] **Step 5: Commit.** `git commit -m "feat: sort and filter the library"`
