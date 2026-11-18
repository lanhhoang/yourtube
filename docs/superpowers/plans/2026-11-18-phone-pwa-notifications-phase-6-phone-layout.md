# Phase 6: Phone layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every screen a real phone layout below 768 px, built from owner-approved mockups.

**Usable result:** On the iPhone, the installed app has a bottom tab bar, a single-column library and queue, a stacked fetch flow with bottom-sheet overrides, and a stacked Settings page, with no sideways scrolling and 44 px targets.

**Architecture:** Web only. Mockups come first (Task 13 is a hard stop for owner approval). Then a `TabBar` replaces the rail below `md`, views get responsive classes, and `BottomSheet` wraps the override panel on phones. Desktop layouts are unchanged at ≥ 768 px.

**Tech Stack:** Svelte 5, Tailwind 4, Playwright (390×844 viewport with touch). Impeccable skill (shape, critique, polish) and taste-skill anti-slop checks. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§7 Phone layout, §4 (phone: theme in Settings only), §10 (DESIGN.md phone section))

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 13, 14, 15, 16, 17. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 5 merged (`Watch.svelte`, the Paste button, `e2e/phone.spec.ts` and the PWA meta with `viewport-fit=cover` exist).

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output unless the job asks for HDR.
- Never silently download below the chosen cap (existing principle, unchanged).
- Never break or lose existing library files. A failed move leaves the file and its row as they were.
- A 500-video playlist must not send 500 pushes: jobs in a batch send no per-job push and no per-job toast.
- No login, no multi-user accounts. Tailscale is the access boundary. Never expose the app to the public internet.
- iOS: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. Every phone screen has a no-horizontal-overflow e2e check (Tasks 14–16). Desktop e2e at 1440 px must still pass after each task. Safe areas: the tab bar and bottom sheet pad `safe-area-inset-bottom`, and toasts sit below `safe-area-inset-top` (Task 14).

---

### Task 13: Phone mockups and owner approval (hard stop)

**Files:**
- Create: `docs/design/phone-mockups.html` (static, self-contained, no CDN, uses `DESIGN.md` tokens)
- Create: `docs/superpowers/specs/2026-11-18-phone-layout-mockups.md` (one section per screen: what changes and why, plus the owner's decision)

**Interfaces:**
- Produces: approved mockups at 390×844 for the shell (top bar, bottom tab bar, toasts at the top), Library list, Queue, Fetch video view with the override bottom sheet, playlist picker, Settings (theme control and the future notification toggle) and Watch. Tasks 14–17 build to them.

- [ ] **Step 1: Load the Impeccable skill (shape) with `DESIGN.md` and `PRODUCT.md` as context.** Draft the mockups, then check them against the taste-skill anti-slop rules.
- [ ] **Step 2: Render every screen in both themes** (a Playwright screenshot or a browser) and look at each one.
- [ ] **Step 3: Show the owner the screenshots and the notes. STOP until the owner approves.** Record the approval and any requested changes in the mockups doc.
- [ ] **Step 4: Commit** `docs: approved phone layout mockups`

### Task 14: Phone shell

**Files:**
- Create: `apps/web/src/components/TabBar.svelte`
- Modify: `apps/web/src/App.svelte`, `apps/web/src/app.css` (drop `min-width: 960px`, add safe-area padding), `apps/web/src/components/LeftRail.svelte` (`hidden md:flex`), `apps/web/src/components/TopBar.svelte` (below md: mark only, wordmark text visually hidden, field fills the width), `apps/web/src/components/Toasts.svelte` (top on phones, below `safe-area-inset-top`)
- Modify: `DESIGN.md` (Phone section: 768 px breakpoint, tab bar, 44 px targets, safe areas; remove the 960 px minimum)
- Test: `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Consumes: `section(route)`, the queue count from `App.svelte`, `LogoMark` (Task 1).
- Produces: `TabBar.svelte` with props `{ active: Section; queueCount: number }`. It renders links Library, Queue (red count badge with the number in text) and Settings, each at least 44 px tall. It pads `env(safe-area-inset-bottom)` and is `md:hidden`.

- [ ] **Step 1: Write the failing e2e tests** (390×844):
  - The tab bar's links navigate and set `aria-current="page"`. The rail is hidden.
  - `document.documentElement.scrollWidth <= innerWidth` on `#/`, `#/queue` and `#/settings`.
  - Every tab link's bounding box is at least 44 px tall.
  - The theme tile is not visible, and Settings has the theme radios.
- [ ] **Step 2: Run them and see them fail**, then build to the approved mockup.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`** (desktop specs must still pass at 1440 px). **Commit** `feat(web): phone shell with bottom tab bar`

### Task 15: Phone Library, Queue, Settings and Watch

**Files:**
- Modify: `apps/web/src/routes/Library.svelte` (single-column list below md: thumbnail left, title/meta right, tap opens `#/watch/<id>`), `apps/web/src/components/JobCard.svelte` (a list variant, or responsive classes), `apps/web/src/routes/Queue.svelte` (single column, actions 44 px), `apps/web/src/routes/Settings.svelte` (stacked form), `apps/web/src/routes/Watch.svelte` (full-width player, actions in thumb reach)
- Test: `apps/web/e2e/phone.spec.ts`

- [ ] **Step 1: Write the failing e2e tests** (390×844, seeded library and the slow queued job):
  - Library: no horizontal overflow. Tapping the seeded item opens `#/watch/<id>`.
  - Queue: no horizontal overflow. The Cancel button is at least 44 px.
  - Settings: no horizontal overflow, and every input is visible without sideways scrolling.
  - Watch: the video width is at most the viewport width. Save and Delete are at least 44 px.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone layout for library, queue, settings and player`

### Task 16: Phone Fetch views and override bottom sheet

**Files:**
- Create: `apps/web/src/components/BottomSheet.svelte`
- Modify: `apps/web/src/routes/VideoView.svelte`, `apps/web/src/routes/ListView.svelte`, `apps/web/src/components/EntryCard.svelte`, `apps/web/src/components/OverridePanel.svelte` (rendered inside `BottomSheet` below md, unchanged above)
- Test: `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Produces: `BottomSheet.svelte` with props `{ open: boolean; title: string; onclose: () => void; children: Snippet }`. It is a modal `<dialog>` docked to the bottom, max height 85vh, scrolls inside, closes on Escape, backdrop tap and a Close button, and returns focus to the opener. It pads `safe-area-inset-bottom`.

- [ ] **Step 1: Write the failing e2e tests** (390×844, stubbed `https://e2e.test/video` and the playlist URL used in `playlist.spec.ts`):
  - Video view: no horizontal overflow. "Download" is reachable and queues the job.
  - Playlist: no horizontal overflow. Opening an entry's override shows a `dialog` named after the panel title. Escape closes it and focus returns to the opener.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone fetch views with bottom-sheet overrides`

### Task 17: Critique and polish pass

**Files:** whichever phone views the critique flags. Also `DESIGN.md` if a rule changes.

- [ ] **Step 1: Run the Impeccable skill's critique and audit on every phone screen in both themes**, plus the taste-skill anti-slop checks. List the findings in the mockups doc.
- [ ] **Step 2: Fix each finding in its own small commit,** with a test where the finding is behavioural.
- [ ] **Step 3: Check contrast (AA) for the tab bar, the badges and the toasts in both themes.** Check that the phone e2e suite passes.
- [ ] **Step 4: Show the owner the final screenshots.** Commit `polish(web): phone layout critique fixes`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
