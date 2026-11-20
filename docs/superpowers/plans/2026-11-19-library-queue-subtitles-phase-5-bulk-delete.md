# Phase 5: Library: Select mode and bulk delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select several finished videos in the Library and delete them together, on desktop and phone.

**Usable result:** Library → **Select** → tick videos (or **Select all**) → **Delete** → **Delete N?** → gone, with "Deleted N" (or "Deleted 2, 1 failed"). Works by tap on the phone, where per-card delete didn't exist before.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 11, 12. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phase 4 recommended (bulk delete then removes subtitle sidecars too). The chips stay until Phase 6.

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

1. Partial failure: the rest are deleted, the failing ones stay listed and selected; non-`done` and unknown ids are reported, never deleted.
2. In Select mode a tap toggles and never navigates; in-progress cards are not selectable.
3. Two-step confirm before any deletion; 44 px targets and the action bar above the tab bar on phones.

---

### Task 11: `POST /api/library/delete`

**Files:**
- Modify: `apps/server/app/services/library.py`, `apps/server/app/api/library.py`, `apps/server/app/schemas.py`
- Test: `tests/unit/test_library.py`, `tests/api/test_library_api.py`

**Interfaces:**
- Consumes: `delete_from_library(session, job_id) -> tuple[bool, str]` (with Task 10's sidecar removal)
- Produces:
  - `delete_many(session: Session, ids: list[int]) -> tuple[list[int], list[tuple[int, str]]]`: `(deleted, failed)`. It deduplicates while keeping order, calls `delete_from_library` per id (that function commits per row), and puts `ok` ids, including `file_missing`, in `deleted`.
  - `class BulkDeleteIn(BaseModel): ids: list[int] = Field(min_length=1, max_length=500)`
  - `class BulkDeleteFailure(BaseModel): id: int; reason: str`
  - `class BulkDeleteOut(BaseModel): deleted: list[int]; failed: list[BulkDeleteFailure]`
  - Route `POST /api/library/delete -> BulkDeleteOut` (200, even with failures).

- [ ] **Step 1: Write the failing tests.**
  - unit `test_delete_many_partial`: rows A (done, file exists), B (done, file missing), C (active), D (done, `os.remove` raises `PermissionError` via monkeypatch), 9999 (unknown) → `deleted == [A, B]`, `failed == [(C,"not_done"),(D,"delete_failed"),(9999,"not_found")]`. D's row still exists.
  - unit `test_delete_many_dedupes`: `[A, A]` → `deleted == [A]`.
  - api `test_bulk_delete`: 200 with that shape. `{"ids": []}` → 422 with the standard error body. 501 ids → 422.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `uv run pytest -q`, then `pnpm typegen`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: bulk delete endpoint for the library"`

### Task 12: Select mode, action bar and bulk delete UI

**Files:**
- Modify: `apps/web/src/routes/Library.svelte`, `apps/web/src/components/JobCard.svelte`, `apps/web/src/lib/library.ts`
- Test: `apps/web/test/library.test.ts`, `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Consumes: `POST /api/library/delete` (Task 11)
- Produces:
  - `JobCard` props: `{ job, ondeleted, selecting?: boolean = false, selected?: boolean = false, ontoggle?: (id: number) => void }`
  - `lib/library.ts`: `toggle(selected: Set<number>, id: number): Set<number>`, `bulkResultText(deleted: number, failed: number): string` → `"Deleted 3"`, `"Deleted 2, 1 failed"`, `"Couldn't delete 2"` (when `deleted === 0`)

Behaviour:
- The toolbar gets a `Select` button (pill, same style as other secondary buttons), shown when `done.length > 0`. In Select mode it reads `Done`, and `Esc` also exits. Exiting clears the selection.
- In Select mode, each card renders a visible checkbox at the top-left of the thumbnail (a native `<input type="checkbox">`, `accent-(--color-action)`, inside a ≥44 px label on phone). The whole card toggles: the title link's `after:` overlay is replaced by a `<label>` overlay for the checkbox, so tapping anywhere toggles and nothing navigates. The hover menu is hidden. A selected card gets a 2 px `fg` ring on the thumbnail. Selection is shown by the checkbox and the ring, never colour alone.
- Sticky action bar (`role="region"`, `aria-label="Selection"`): `sticky bottom-0` inside `main`, so on phones it sits above the tab bar. `bg-surface border-t border-line`, padding `p-3`, plus `pb-[calc(0.75rem+env(safe-area-inset-bottom))]` only if it ever ends up at the screen edge (it doesn't, because the tab bar is below). Contents: `{n} selected` (tabular, `aria-live="polite"`) · `Select all` (selects every visible item; reads `Clear` when all visible are selected) · `Delete` (primary danger style used elsewhere: check `Watch.svelte`'s `button`; disabled at 0).
- Delete uses the existing two-step pattern. First click → label `Delete {n}?` for 4 s. Second click → call the API → remove the `deleted` ids from `done` → show `bulkResultText` in the bar for 4 s (`role="status"`). The ids that failed stay selected. Exit Select mode when nothing is left selected.
- Changing the search or the chip clears the selection (Task 15 extends this to sort and filter changes). The chips still exist in this phase, so in-progress cards may be in the list: they get no checkbox, are never selectable, and `Select all` takes only `status === "done"` items.

- [ ] **Step 1: Write the failing tests.**
  - unit: `toggle` adds then removes. `bulkResultText(3,0)` → `"Deleted 3"`, `(2,1)` → `"Deleted 2, 1 failed"`, `(0,2)` → `"Couldn't delete 2"`.
  - e2e desktop `"select and delete several"`: create two done rows via the seeded data. Add a second seeded row `Bulk A`/`Bulk B` in `e2e_server._seed`, with files `bulk-a.mp4`/`bulk-b.mp4` (uploader `E2E`). Click `Select`, check `Bulk A` and `Bulk B` (by `getByRole("checkbox", { name: "Bulk A" })`). Expect `2 selected`. Click `Delete`, then `Delete 2?`. Both articles disappear and the files are gone (poll `existsSync`). `Deleted 2` is visible.
  - e2e desktop `"select mode does not navigate"`: in Select mode, clicking a card's title leaves the URL at `#/`.
  - e2e phone (`phone.spec.ts`) `"select mode on phone"`: tap `Select`. The checkbox target is ≥ 44 px (`expectTarget`). The action bar is visible above the tab bar (its bottom ≤ the tab bar's top). No sideways scroll.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Read `craft-floor.md` and `operate.md` first, and the taste skill's §6 "Never" list. Keep the copy plain. The checkbox's accessible name is the video title.
- [ ] **Step 4: Run `pnpm check` and `pnpm e2e`.** Then screenshot desktop at 1440 and phone at 390 in both themes, with Select mode on and two selected, and check against `DESIGN.md`.
- [ ] **Step 5: Commit.** `git commit -m "feat: select several library items and delete them together"`
