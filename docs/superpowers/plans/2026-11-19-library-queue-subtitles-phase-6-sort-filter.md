# Phase 6: Library: sort and filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the All / Downloading / Video / Audio only chips with sort and filter (type, channel, playlist), remembered across visits.

**Usable result:** Library toolbar: search · Sort (Newest, Oldest, Title A–Z, Longest, Largest) · Filter (Type, Channel, Playlist; a bottom sheet on phones) · Select. Active filters show as removable pills; the choice survives a reload.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 13, 14, 15. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phase 3 (Task 6 adds `playlist_title`/`playlist_channel` to `JobOut`) and Phase 5 (selection clears on view change).

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. No new dependencies.
- `DESIGN.md` is the visual contract: red is the only accent, WCAG AA in both themes, 8 px control radius, pill buttons, 120–200 ms ease-out motion, 2 px `fg` focus outline, status never shown by colour alone. Phone is below 768 px: 44 px tap targets, 16 px inputs.
- UI tasks: before editing, read `~/.agents/skills/impeccable/reference/craft-floor.md` and `reference/operate.md` (this is an Operate surface: precision and restraint, known patterns). Use `~/.config/pi/skills/design-taste-frontend/SKILL.md` §6 "Never" as the anti-slop checklist. No new visual language, no decorative extras.
- yt-dlp never gets global `ignoreerrors`. Media failures must still fail the job.
- Never request an auto-translated subtitle track (any `automatic_captions` key except `<lang>-orig`).
- Bulk delete touches only `done` rows and their own files and sidecars, and always confirms first.
- Database changes go through one new Alembic revision, `20261119120000`, whose `down_revision` is `20261118130000`. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/test_db.py`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `apps/server/tests/e2e_server.py`).

## Review Focus

1. A stored channel/playlist that no longer exists is ignored, not an empty library.
2. Facets come from the unfiltered list, so options don't vanish while filtering.
3. No regression for search: sort/filter apply after the server-side `q` search; e2e tests that delete rows don't break sort/filter tests (dedicated seeded rows).

---

### Task 13: Library shows finished items only; chips removed

**Files:**
- Modify: `apps/web/src/lib/library.ts`, `apps/web/src/routes/Library.svelte`, `apps/web/test/library.test.ts`
- Delete: `apps/web/src/components/Chips.svelte`

**Interfaces:**
- Produces: `lib/library.ts` no longer exports `Chip` or `libraryItems`. `qualityLabel`, `formatSize` and `watchMeta` stay.

`Library.svelte` keeps the `queue` prop and its reload-on-finish effect (that's how new downloads appear), but renders `done` only. Empty states: `searching && done.length === 0` → `Nothing matches “q”.` `done.length === 0` → `No downloads yet. Paste a URL above.` In-progress work is in the Queue tab (badge count), so nothing replaces "Downloading".

- [ ] **Step 1: Update tests.** Delete the `libraryItems` tests. Add an e2e assertion in `library.spec.ts`: on `#/`, `page.getByRole("radiogroup", { name: "Filter" })` has count 0, and `Slow video` (seeded `queued`) is not shown in the library.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Remove `Chips` and `libraryItems`.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e -- library.spec.ts phone.spec.ts`.**
- [ ] **Step 5: Commit.** `git commit -m "refactor: library lists finished downloads only; drop the chips"`

### Task 14: Sort and filter logic

**Files:**
- Modify: `apps/web/src/lib/library.ts`; `apps/web/test/library.test.ts`

**Interfaces:**
- Consumes: `JobOut.playlist_title`, `playlist_channel`, `uploader`, `media_kind`, `finished_at`, `created_at`, `title`, `duration`, `file_size`
- Produces:

```ts
export type SortKey = "added-desc" | "added-asc" | "title" | "duration" | "size";
export type KindFilter = "any" | "video" | "audio";
export type LibraryView = { sort: SortKey; kind: KindFilter; channel: string | null; playlist: string | null };
export const DEFAULT_VIEW: LibraryView;               // { sort: "added-desc", kind: "any", channel: null, playlist: null }
export const SORT_OPTIONS: { value: SortKey; label: string }[];
// labels: "Newest first", "Oldest first", "Title A–Z", "Longest first", "Largest first"
export function sortItems(items: JobOut[], sort: SortKey): JobOut[];   // new array, stable
export function filterItems(items: JobOut[], view: LibraryView): JobOut[];
export type Facet = { value: string; count: number };
export function facets(items: JobOut[]): { channels: Facet[]; playlists: Facet[] };
export function activeFilterCount(view: LibraryView): number;
export const VIEW_KEY = "yt.library.view";
export function readView(raw: string | null): LibraryView;   // tolerant: bad JSON or unknown values → defaults per field
```

Rules:
- "added" = `finished_at ?? created_at`. Title sort uses `localeCompare(…, undefined, { sensitivity: "base", numeric: true })`, with a null title sorting last. Duration and size sort descending, with nulls last. Ties keep the input order.
- Channel = `uploader`. Playlist = `playlist_title`. Facets are distinct, non-empty values with counts, sorted by `localeCompare`, and built from the **unfiltered** list so options never vanish while picking.
- `filterItems` applies kind, channel and playlist (AND). A channel or playlist value not present in the items is ignored (stale stored value), so `filterItems` returns the kind-filtered list as if that field were null. The component also drops it from the view.

- [ ] **Step 1: Write the failing tests:** one per sort key (including nulls last and stable ties); a kind/channel/playlist AND combination; a stale channel ignored; facet counts and order; `activeFilterCount`; `readView` with `null`, `"{bad"`, `{"sort":"nope","kind":"audio"}` → `{...DEFAULT_VIEW, kind:"audio"}`.
- [ ] **Step 2: Run them and see them fail.** `pnpm test`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit.** `git commit -m "feat: library sort and filter helpers"`

### Task 15: Toolbar, filter panel, pills and persistence

**Files:**
- Create: `apps/web/src/components/LibraryFilters.svelte`
- Modify: `apps/web/src/routes/Library.svelte`, `apps/server/tests/e2e_server.py` (seed one audio row and one playlist row with a different uploader), `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`, `README.md`

**Interfaces:**
- Consumes: Task 14's exports; `BottomSheet` (`{ open, title, onclose, children }`)
- Produces: `LibraryFilters` props `{ view: LibraryView (bindable), channels: Facet[], playlists: Facet[] }`. It renders the form fields only. The container (popover or sheet) belongs to `Library.svelte`.

Layout:
- Desktop toolbar row: `Library` heading · (right side) search · `Sort` select (labelled visually-hidden "Sort", native `<select>` styled like `QualitySelect`) · `Filter` button (pill; shows `Filter · 2` when filters are active) · `Select`. The Filter button opens a popover anchored under it (`<div role="dialog" aria-label="Filters">`, `bg-surface border border-line-strong rounded-control p-4`, closes on Esc or an outside click, focus moves into it and back).
- Phone: the search fills the first row. The second row is `Sort` select · `Filter` · `Select`, each ≥ 44 px. `Filter` opens `BottomSheet` titled "Filters".
- `LibraryFilters` fields: Type as a radiogroup (Any / Video / Audio). Channel as a `<select>` ("Any channel" plus `name (count)`). Playlist as a `<select>` ("Any playlist" plus `name (count)`), hidden when there are no playlists. Changes apply immediately (no Apply button), and `Clear filters` resets kind, channel and playlist.
- Under the toolbar, when filters are active: removable pills `Video`, `Channel: X`, `Playlist: Y`, each with a ✕ button (`aria-label="Remove filter Channel: X"`), plus a `Clear filters` text button.
- Results: `items = sortItems(filterItems(done, view), view.sort)`. When filters hide everything: `No videos match these filters.` plus `Clear filters`.
- Persistence: `readView(localStorage.getItem(VIEW_KEY))` on mount. An `$effect` writes it on change. A stale channel or playlist gets reset to `null` after the first load.
- Selection (Task 12) clears whenever `view` or `q` changes.
- README: a short "Library" paragraph covering Sort/Filter/Select, plus the subtitle languages rule and the player tracks, and codecs/HDR on the Watch page.

- [ ] **Step 1: Write the failing e2e tests.** Tests in one spec file share the e2e server, and `"delete in library"` and `"select and delete several"` remove rows. Seed dedicated rows for these tests (`Sort A`, `Sort B`, an audio row, a playlist row under uploader `Other`) and assert only on those.
  - desktop `"sort by title"`: pick `Title A–Z`. The first article title is alphabetically first among the seeded rows.
  - desktop `"filter by channel and clear"`: open Filter, pick the second channel → only its rows. A pill `Channel: <name>` is visible. Click its ✕ → all rows are back.
  - desktop `"filter by type audio"`: Type = Audio → only the seeded audio row.
  - desktop `"view persists"`: set sort `Oldest first`, reload, and the select still shows `Oldest first`.
  - phone `"filters open in a sheet"`: tap `Filter`, `getByRole("dialog", { name: "Filters" })` is visible, controls ≥ 44 px, no sideways scroll.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Read `craft-floor.md`, `operate.md` and the taste skill's §6 first. Use only existing tokens. Popover motion is opacity/translate at 150 ms ease-out, removed under `prefers-reduced-motion`.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e`.** Screenshot desktop 1440 and phone 390 in both themes: default, filters active (pills), the sheet open, and the empty filtered state. Fix anything that breaks `DESIGN.md`.
- [ ] **Step 5: Commit.** `git commit -m "feat: sort and filter the library"`
