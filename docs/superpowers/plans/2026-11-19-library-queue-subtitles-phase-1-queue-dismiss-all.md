# Phase 1: Queue: dismiss all failed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear every failed download from the Queue in one click.

**Usable result:** With two or more failed jobs, the Queue's Failed heading shows **Dismiss all**; one click empties the list. Files are untouched.

**Spec:** `docs/superpowers/specs/2026-11-19-library-queue-subtitles-design.md`

**Parent plan:** `docs/superpowers/plans/2026-11-19-library-queue-subtitles.md`, Tasks 1, 2. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-19-library-queue-subtitles-phases.md`.

**Prerequisites:** None. Server endpoint plus one Svelte page.

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
- Pass e2e file filters without `--`: `pnpm e2e queue.spec.ts`. `pnpm e2e -- queue.spec.ts` forwards a literal `--` to Playwright, which then runs all 51 tests. If Playwright's bundled browser is missing, prefix `PW_CHANNEL=chrome` (uses installed Google Chrome) or run `pnpm --filter @app/web exec playwright install chromium` once.

## Review Focus

1. Only `error` rows are deleted; `queued`, `active` and `done` rows survive (`test_dismiss_failed_removes_only_error_rows`).
2. The button is hidden with fewer than two failures and is a 44 px target on phones.

---

### Task 1: `POST /api/queue/dismiss-failed`

**Files:**

- Modify: `apps/server/app/services/queue.py`, `apps/server/app/api/jobs.py`, `apps/server/app/schemas.py`
- Test: `apps/server/tests/unit/test_queue_retry_dismiss.py`, `apps/server/tests/api/test_queue_api.py`

**Interfaces:**

- Produces: `dismiss_failed(session: Session) -> int` (rows deleted). `class DismissFailedOut(BaseModel): dismissed: int`. Route `POST /api/queue/dismiss-failed -> DismissFailedOut` (200).

- [ ] **Step 1: Write the failing tests.**
  - `test_dismiss_failed_removes_only_error_rows` (unit): one row each in `error`, `error`, `done`, `queued`, `active` → returns `2`. The `done`/`queued`/`active` rows remain.
  - `test_dismiss_failed_endpoint` (api): two failed rows → `{"dismissed": 2}`, and `GET /api/queue` `failed == []`. Calling it again → `{"dismissed": 0}`.
- [ ] **Step 2: Run them and see them fail.** `cd apps/server && uv run pytest -q tests/unit/test_queue_retry_dismiss.py tests/api/test_queue_api.py` (unit: `ImportError` on `dismiss_failed`; api: 404/405).
- [ ] **Step 3: Implement.** One `delete(Download).where(Download.status == "error")` plus a commit. The route lives next to `dismiss`.
- [ ] **Step 4: Run them and see them pass** (same command). **Run `pnpm typegen`**, then `pnpm check`.
- [ ] **Step 5: Commit** (with `api.gen.ts`). `git commit -m "feat: dismiss all failed downloads endpoint"`

### Task 2: "Dismiss all" on the Queue page

**Files:**

- Modify: `apps/web/src/routes/Queue.svelte`
- Test: `apps/web/e2e/queue.spec.ts`

**Interfaces:**

- Consumes: `POST /api/queue/dismiss-failed` (Task 1)

UI: the "Failed" `<h2>` row becomes a flex row: `Failed` on the left and a `Dismiss all` button (same `btn` class) on the right. It's shown only when `queue.failed.length >= 2`. Click → disable it → call → `refresh()`. On error, show `messageFor(err)` under the heading (text-danger, `role="alert"`). There's no confirm, because dismissing removes no files. No toast either: the list emptying is the feedback.

- [ ] **Step 1: Write the failing e2e test** `"dismiss all clears failed downloads"`. Use `page.route("**/api/queue", …)` to serve two failed jobs (copy the job shape from the toasts test) until the dismiss call is seen, then `failed: []`. Use `page.route("**/api/queue/dismiss-failed", …)` and fulfil `{dismissed: 2}`. Click `Dismiss all` and expect both rows to have count 0. A second test, `"dismiss all is hidden for one failure"`, serves one failed job and expects the button to have count 0.
- [ ] **Step 2: Run it and see it fail.** `pnpm e2e queue.spec.ts`
- [ ] **Step 3: Implement.** Read `craft-floor.md` first (Global Constraints). The button must be a 44 px target on phones (the `btn` class already is).
- [ ] **Step 4: Run it and see it pass. Run `pnpm check`.**
- [ ] **Step 5: Commit.** `git commit -m "feat: Dismiss all on the queue page"`
