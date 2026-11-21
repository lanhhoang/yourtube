# Phase 5: Library: Select mode and bulk delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select several finished videos in the Library and delete them together, on desktop and phone.

**Usable result:** Library → **Select** → tick videos (or **Select all**) → **Delete** → **Delete N?** → gone, a toast says "Deleted N" (or "Deleted 2, 1 failed"), and Select mode ends. Works by tap on the phone, where per-card delete didn't exist before.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md` §5

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 11, 12. The tasks below match it; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** Phases 1–4 merged (`main` @ `07963ac`). `delete_from_library` already removes subtitle sidecars. Work on branch `20261120-library-queue-subtitles-phase-5-bulk-delete`. The chips stay until Phase 6.

**Revised 2026-11-20 after a readiness review against `main` @ `07963ac`.** Fixes:

- Test paths are `apps/server/tests/...`. Run the server tests from `apps/server`.
- No database changes in this phase. The old Alembic line referred to Phase 3's revision, which is already merged.
- There is no "danger" button style. Watch's Delete is the outlined pill (`button` in `Watch.svelte`), and red is reserved for the accent. Bulk Delete uses the same outlined pill.
- The result is an app toast, and Select mode ends when nothing is left selected (owner's call). That needs a new toast kind and a way for `Library` to raise a toast, so `toasts.ts`, `Toasts.svelte`, `App.svelte` and `DESIGN.md` change too.
- Seeded files are moved at startup into channel folders, so `Bulk A` lives at `e2e/bulk-a.mp4`, not `bulk-a.mp4`.
- Spec files run in parallel against one e2e server. The tests never press Delete after `Select all`, and the phone test deletes nothing.
- `sticky bottom-0` inside `main` floats mid-page when the list is short, and stops 16/24 px above the tab bar because of `main`'s padding. The recipe below was checked in Chrome at 390 px: the bar sits flush on the tab bar with short and long content.
- In Select mode the title is plain text, not a link, so the keyboard can't navigate either.
- `delete_from_library` also calls `os.remove` for sidecars, so the `PermissionError` patch in the unit test must target D's file only.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. No new dependencies.
- **No database changes in this phase.** No new Alembic revision.
- `DESIGN.md` is the visual contract: red is the only accent, WCAG AA in both themes, 8 px control radius, pill buttons, 120–200 ms ease-out motion, 2 px `fg` focus outline, status never shown by colour alone. Phone is below 768 px: 44 px tap targets, 16 px inputs.
- UI tasks: before editing, read `~/.agents/skills/impeccable/reference/craft-floor.md` and `reference/operate.md` (this is an Operate surface: precision and restraint, known patterns). Use `~/.config/pi/skills/design-taste-frontend/SKILL.md` §6 "Never" as the anti-slop checklist. No new visual language, no decorative extras.
- Bulk delete touches only `done` rows and their own files and sidecars, and always confirms first.
- Single delete (card hover menu, Watch page) keeps working as today.
- Follow the existing test layout: pytest `apps/server/tests/unit`, `apps/server/tests/api`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `apps/server/tests/e2e_server.py`). API tests use the `client` and `db_session_visible` fixtures and add rows like `_add` in `tests/api/test_library_api.py`. Unit tests follow `tests/unit/test_library.py` (`enqueue_download` + `_mark_done`).

## Review Focus

1. Partial failure: the rest are deleted, and the failing ones stay listed and selected. Non-`done` and unknown ids are reported, never deleted.
2. In Select mode a tap toggles and never navigates (mouse, touch or keyboard). In-progress cards are not selectable.
3. Two-step confirm before any deletion. 44 px targets on phones, and the action bar sits flush on the tab bar.

---

### Task 11: `POST /api/library/delete`

**Files:**

- Modify: `apps/server/app/services/library.py`, `apps/server/app/api/library.py`, `apps/server/app/schemas.py`, `apps/web/src/lib/api.gen.ts` (typegen)
- Test: `apps/server/tests/unit/test_library.py`, `apps/server/tests/api/test_library_api.py`

**Interfaces:**

- Consumes: `delete_from_library(session, job_id) -> tuple[bool, str]` (already removes sidecars)
- Produces:
  - `delete_many(session: Session, ids: list[int]) -> tuple[list[int], list[tuple[int, str]]]` returns `(deleted, failed)`. It drops duplicate ids, keeps the first-seen order, and calls `delete_from_library` for each id (that function commits per row). Ids that come back ok, `file_missing` included, go in `deleted`. The others go in `failed` with their reason.
  - `class BulkDeleteIn(BaseModel): ids: list[int] = Field(min_length=1, max_length=500)` (same bounds as `EnqueueRequest.jobs`)
  - `class BulkDeleteFailure(BaseModel): id: int; reason: str`
  - `class BulkDeleteOut(BaseModel): deleted: list[int]; failed: list[BulkDeleteFailure]`
  - Route `POST /api/library/delete -> BulkDeleteOut`. It returns 200 even when some ids fail. Declare it next to `delete_job` in `api/library.py`. It doesn't clash with `DELETE /library/{job_id}`.

- [ ] **Step 1: Write the failing tests.**
  - unit `test_delete_many_partial`:
    - Rows: A (done, file exists, plus `A.en.srt`), B (done, `file_path` points at a missing file), C (queued, via `enqueue_download`), D (done, file exists), and the unknown id 999999.
    - Patch `app.services.library.os.remove` with a wrapper that raises `PermissionError` only for D's path and calls the real `os.remove` otherwise.
    - Expect `deleted == [A, B]` and `failed == [(C, "not_done"), (D, "delete_failed"), (999999, "not_found")]`.
    - A's file and `.srt` are gone. D's row and file still exist, and so does C's row.
  - unit `test_delete_many_dedupes`: `[A, A]` gives `([A], [])`.
  - api `test_bulk_delete`: one done row with a file plus id 999999 gives 200 and `{"deleted": [id], "failed": [{"id": 999999, "reason": "not_found"}]}`.
  - api `test_bulk_delete_validates`: `{"ids": []}` and 501 ids both give 422 with `body["error"]["code"] == "invalid_request"`.
- [ ] **Step 2: Run them and see them fail.** `cd apps/server && uv run pytest -q tests/unit/test_library.py tests/api/test_library_api.py`
- [ ] **Step 3: Implement** the service, schemas and route.
- [ ] **Step 4: Verify.** `cd apps/server && uv run pytest -q`, then `pnpm typegen` from the repo root.
- [ ] **Step 5: Commit** after `pnpm check`: `git commit -m "feat: bulk delete endpoint for the library"`

### Task 12: Select mode, action bar and bulk delete UI

**Files:**

- Modify: `apps/web/src/routes/Library.svelte`, `apps/web/src/components/JobCard.svelte`, `apps/web/src/lib/library.ts`, `apps/web/src/lib/toasts.ts`, `apps/web/src/components/Toasts.svelte`, `apps/web/src/App.svelte`, `apps/server/tests/e2e_server.py`, `DESIGN.md`
- Test: `apps/web/test/library.test.ts`, `apps/web/e2e/library.spec.ts`, `apps/web/e2e/phone.spec.ts`

**Interfaces:**

- Consumes: `POST /api/library/delete` (Task 11)
- Produces:
  - `JobCard` props: `{ job, ondeleted, selecting?: boolean = false, selected?: boolean = false, ontoggle?: (id: number) => void }`
  - `lib/library.ts`:
    - `toggle(selected: Set<number>, id: number): Set<number>` returns a new set.
    - `bulkResultText(deleted: number, failed: number): string` gives `"Deleted 3"`, `"Deleted 2, 1 failed"`, and `"Couldn't delete 2"` when `deleted === 0`.
  - `lib/toasts.ts`: `ToastKind` gains `"deleted"`.
  - `Library` props: `{ queue, ontoast: (t: Omit<Toast, "key">) => void }`. `App.svelte` passes `ontoast`, which adds a unique key (a counter), appends the toast, and closes it after `TOAST_MS`, the same as poll toasts.

**Behaviour:**

- **Toolbar.** A `Select` button (outlined pill, same classes as the `Try again` button in `Library.svelte`, ≥44 px on phones) sits after the search. It shows when `done.length > 0` and reads `Done` in Select mode. `Esc` (`<svelte:window onkeydown>`) also exits. Exiting clears the selection.
- **Cards in Select mode** (`selecting && job.status === "done"`):
  - The title renders as plain text, not a link, and the hover menu isn't rendered.
  - A `<label class="absolute inset-0 z-10 cursor-pointer">` covers the whole card. It holds a native `<input type="checkbox" aria-label={job.title ?? job.url} class="size-4 accent-(--color-action)">` inside a top-left box over the thumbnail: 44 × 44 px on phone, a 24 px `bg-black/60 rounded-control` chip on desktop, like `EntryCard.svelte`'s checkbox. Tapping anywhere on the card toggles it.
  - A selected card gets `ring-2 ring-fg` on the thumbnail box. Selection shows through the checkbox and the ring, never colour alone.
  - In-progress cards (the chips still put them in the list) get no checkbox and are never selectable.
- **Selection state** lives in `Library.svelte` as `Set<number>`. The count, Select all and Delete only use ids that are still in `done` (rows can vanish on a reload). Changing `q` or `chip` clears the selection. Task 15 extends this to sort and filter changes.
- **Action bar** (shown only in Select mode): `<div role="region" aria-label="Selection">`. Wrap the whole Library template in `<div class="flex min-h-full flex-col">`, and make the bar its last child with `sticky -bottom-4 z-10 mt-auto -mx-4 -mb-4 md:-bottom-6 md:-mx-6 md:-mb-6 flex items-center gap-3 border-t border-line bg-surface p-3`. The negative offsets cancel `main`'s `p-4 md:p-6`, so the bar sits flush on the tab bar on phones and on the window's bottom edge on desktop, with short or long lists (checked in Chrome). It needs no safe-area padding, because the tab bar already has it. Contents:
  - `{n} selected` (`tabular`, `aria-live="polite"`).
  - `Select all`, which selects every visible `done` item. It reads `Clear` when they're all selected, and it's disabled when nothing visible is `done`.
  - `Delete`, an outlined pill (same classes as Watch's `button`). It's disabled at 0 and while the request runs.
  - All buttons are ≥44 px on phones.
- **Delete** uses the existing two-step pattern:
  1. The first click relabels the button `Delete {n}?` for 4 s. Blur, or any change to the selection, resets it.
  2. The second click calls the API and removes the `deleted` ids from `done` and from the selection.
  3. It then raises an `ontoast({ kind: "deleted", title: "", body: bulkResultText(deleted, failed) })`. The failed ids stay selected.
  4. When nothing is left selected, Select mode ends.
  5. If the request itself fails, show `messageFor(err)` in the bar as `text-danger` with `role="alert"`, keep the selection, and raise no toast.
- **Toast.** Kind `deleted`: a trash icon (stroke, same size and stroke as the others) and the label `Bulk delete` in `muted`, over the body. Add it to `DESIGN.md` § Toasts. **Builder's call** on the label and icon; the spec only says "a toast with the result".

- [ ] **Step 1: Write the failing tests.**
  - unit (`library.test.ts`): `toggle` adds, then removes, and doesn't mutate its input. `bulkResultText(3,0)` gives `"Deleted 3"`, `(2,1)` gives `"Deleted 2, 1 failed"`, and `(0,2)` gives `"Couldn't delete 2"`.
  - `e2e_server._seed`: add two done rows, `Bulk A` and `Bulk B` (uploader `E2E`, files `bulk-a.mp4` and `bulk-b.mp4`, `finished_at=now`). The startup move puts them at `e2e/bulk-a.mp4` and `e2e/bulk-b.mp4`. They're used only by `"select and delete several"`.
  - e2e desktop `"select and delete several"`:
    1. Assert `e2e/bulk-a.mp4` and `e2e/bulk-b.mp4` exist.
    2. Click `Select` and check `getByRole("checkbox", { name: "Bulk A" })` and `{ name: "Bulk B" }`. Expect `2 selected`.
    3. Click `Delete`, then `Delete 2?`.
    4. Both articles disappear, and polling `existsSync` shows both files gone.
    5. The toast `Deleted 2` is visible, and the `Select` button is back (Select mode ended).
  - e2e desktop `"select mode does not navigate"`:
    1. Click `Select`.
    2. The `Seeded video` link is gone: `getByRole("link", { name: "Seeded video" })` has count 0.
    3. Click the card's title text. The URL stays at `#/` and the checkbox is checked.
    4. Press `Escape`. The checkbox is gone and the link is back.
    5. Don't delete anything.
  - e2e phone `"select mode on phone"` in `phone.spec.ts`:
    1. Tap `Select`. `expectTarget` passes on the `Phone video` checkbox's 44 px box and on the bar's buttons.
    2. Tap the `Phone video` card. Expect `1 selected`, with the URL still at `#/`.
    3. The bar's bottom equals the tab bar's top (±1 px).
    4. No sideways scroll.
    5. Don't delete anything.
- [ ] **Step 2: Run them and see them fail.** `pnpm test` (repo root) and `pnpm e2e`.
- [ ] **Step 3: Implement.** Read `craft-floor.md` and `operate.md` first, and the taste skill's §6 "Never" list. Keep the copy plain.
- [ ] **Step 4: Verify.** Run `pnpm check` and `pnpm e2e`. Then take screenshots at 1440 px (desktop) and 390 px (phone), in both themes, with Select mode on and two items selected, plus one of the toast. Check them against `DESIGN.md`. Also check the bar on a short list (search for one item) and on a long one.
- [ ] **Step 5: Commit.** `git commit -m "feat: select several library items and delete them together"`
