# Phase 6: Phone layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every screen a real phone layout below 768 px, built from owner-approved mockups.

**Usable result:** On the iPhone, the installed app has a bottom tab bar, a single-column library and queue, a stacked fetch flow with bottom-sheet overrides, and a stacked Settings page, with no sideways scrolling and 44 px targets.

**Architecture:** Web only. Mockups come first (Task 13 is a hard stop for owner approval). Then a `TabBar` replaces the rail below `md`, views get responsive classes, and `BottomSheet` wraps the override panel on phones. Desktop layouts are unchanged at ≥ 768 px.

**Tech Stack:** Svelte 5, Tailwind 4, Playwright (390×844 viewport with touch). Impeccable skill (shape, critique, polish) and taste-skill anti-slop checks. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§7 Phone layout, §4 (phone: theme in Settings only), §10 (DESIGN.md phone section))

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 13, 14, 15, 16, 17. The tasks below are copied from it verbatim (blank lines aside); the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** Phase 5 merged (`Watch.svelte`, the Paste button, `e2e/phone.spec.ts` and the PWA meta with `viewport-fit=cover` exist).

**Revised 2026-11-18 after a readiness review** (parent plan and spec updated to match). Each item was checked against the code or with a throwaway build:

- **The overflow check also looks at `main`.** `main` is `overflow-y-auto`, so it clips sideways overflow and `document.documentElement.scrollWidth` alone passes when content is too wide. With `min-width: 960px` removed, the fetch view's `main` measured 383 px of content in 318 px. A shared `expectNoSideScroll` helper checks both.
- **The TopBar's two `w-[120px]` blocks push the page to 493 px at 390 px wide.** Task 14 drops them below md.
- **The installed app draws under the status bar** (`black-translucent` + `viewport-fit=cover`, Phase 5). The top bar now pads `safe-area-inset-top`, as the tab bar pads the bottom.
- **The top-bar field is `text-sm` (under 16 px), so iOS zooms when it gets focus.** Below md it becomes `text-base`.
- **The library card menu (Download file / Delete) only shows on hover or focus**, so a finger can't use it. Task 13 asks the owner. The proposed default drops it below md, because Watch already has Save and Delete.
- **The video view's button says "Add to queue", not "Download".** Its test fetches `https://e2e.test/v/phone`, not `https://e2e.test/video`: a second "E2E Video" card would break `video.spec.ts`, which runs in parallel against the same server.
- **Phone tests don't touch "Seeded video" or "Slow video".** `library.spec.ts` deletes the first and `queue.spec.ts` cancels the second, in parallel. The e2e server seeds a "Phone video" for the library and Watch tests. The queue test posts its own slow job and cancels it. A new job would wait 20 s behind "Slow video" on the one worker, so the done row is seeded, not posted.
- **`OverridePanel` gets a `sheet` mode.** It has its own title, Close button and window Escape handler, and these would show twice inside `BottomSheet`.
- **`BottomSheet` is spelled out** (the `$effect` with `showModal`, focus return, `oncancel`, backdrop tap, lint ignores). A throwaway build passed typecheck and lint. At 390×844 with touch, the dialog docked at the bottom, Escape, Close and a backdrop tap closed it, and focus returned to the opener.
- **A toast test is added.** It stubs `/api/queue` with `page.route`. The toast showed at the bottom before the change.
- **`h-screen` becomes `h-dvh`, the Toasts close button and Fetch/options buttons go to 44 px, and `PRODUCT.md` drops "the dedicated phone layout comes later".**
- **Task 17 gains a by-hand check on the iPhone.** Safe areas and focus zoom can't be checked in Chromium.
- Checked: `pnpm check` passes on `c678db1`. `PW_CHANNEL=chrome pnpm e2e` passes 30 tests. Emulated 390×844 with `hasTouch` reports `pointer: coarse` and `navigator.canShare`, so Watch shows the share-mode Save button. Svelte 5.57 has `MediaQuery` in `svelte/reactivity`.
- Local note: if Playwright's bundled headless shell is missing, run the e2e suite with `PW_CHANNEL=chrome`.

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

1. Every phone screen has an `expectNoSideScroll` check that covers both the document and `main` (Tasks 14–16). Desktop e2e at 1440 px must still pass after each task. Safe areas: the tab bar and bottom sheet pad `safe-area-inset-bottom`; the top bar and toasts sit below `safe-area-inset-top` (Task 14).
2. Phone tests never use the shared seeded rows ("Seeded video", "Slow video") or `https://e2e.test/video`. Spec files run in parallel against one server.

---

### Task 13: Phone mockups and owner approval (hard stop)

**Files:**
- Create: `docs/design/phone-mockups.html` (static, self-contained, no CDN, uses the `DESIGN.md` tokens from `apps/web/src/app.css`)
- Create: `docs/superpowers/specs/2026-11-18-phone-layout-mockups.md` (one section per screen: what changes and why, plus the owner's decision)

**Interfaces:**
- Produces: approved mockups at 390×844 for the shell (top bar under the status bar, bottom tab bar, toasts at the top), Library list, Queue, Fetch video view, playlist picker with the override bottom sheet, Settings (theme radios and a placeholder for Phase 7's notification toggle) and Watch. Tasks 14–17 build to them.

The mockups must settle these, each with a proposed default the owner can change:

- **Library card actions on touch.** Today `JobCard`'s Download file / Delete menu only shows on hover or focus, so a finger can't reach it. Proposed: below md the menu is not rendered. A tap on the row opens Watch, which already has Save and Delete.
- **Top bar under the status bar.** `index.html` sets `apple-mobile-web-app-status-bar-style` to `black-translucent` and `viewport-fit=cover`, so the installed app draws under the status bar. Proposed: the top bar pads `env(safe-area-inset-top)` and keeps 56 px of content height. The mark replaces the wordmark. Field, Paste (when empty), Fetch, and options sit on one row. Fetch and options are 44 px.
- **Override sheet chrome.** The sheet has one title and one Close button. `OverridePanel`'s own header does not show twice.
- **Playlist select checkbox.** Proposed: the hit area grows to 44 px. The visible box stays small.

- [ ] **Step 1: Load the Impeccable skill (shape) with `DESIGN.md` and `PRODUCT.md` as context.** Draft the mockups, then check them against the taste-skill anti-slop rules. The desktop direction mockups (`direction-v2.html`, local only under `.superpowers/brainstorm/`) show the grammar to keep.
- [ ] **Step 2: Render every screen in both themes** (Playwright screenshots into `tmp/phone-mockups/`, which is git-ignored) and look at each one.
- [ ] **Step 3: Show the owner the screenshots and the notes. STOP until the owner approves.** Record the approval, the answers to the questions above and any requested changes in the mockups doc.
- [ ] **Step 4: Commit** `docs: approved phone layout mockups`

### Task 14: Phone shell

**Files:**
- Create: `apps/web/src/components/TabBar.svelte`
- Modify: `apps/web/src/App.svelte` (`h-screen` → `h-dvh`, render `TabBar`, `main` padding `p-4 md:p-6`), `apps/web/src/app.css` (drop `min-width: 960px`), `apps/web/src/components/LeftRail.svelte` (`hidden md:flex`), `apps/web/src/components/TopBar.svelte` (below md: mark only, the "yourtube" text `sr-only`, no fixed `w-[120px]` on the home link, the right spacer `hidden md:block`, the field fills the width, textarea `text-base md:text-sm` so iOS does not zoom on focus, Fetch and options 44 px, pad `env(safe-area-inset-top)`), `apps/web/src/components/Toasts.svelte` (below md: full width at the top, below `safe-area-inset-top`; close button 44 px; unchanged at md and up)
- Modify: `DESIGN.md` (Direction: drop "Computer only … no narrower than 960 px". Add a Phone section covering the 768 px breakpoint, the tab bar, 44 px targets, safe areas top and bottom, and 16 px inputs.) `PRODUCT.md` (drop "the dedicated phone layout comes later")
- Test: `apps/web/e2e/phone.spec.ts`, `apps/web/e2e/phone-helpers.ts` (new)

**Interfaces:**
- Consumes: `section(route)` from `lib/router.ts`, `queue?.active.length` from `App.svelte`, the rail's `LINKS` icons (copy them or move them into a shared module; your call).
- Produces: `TabBar.svelte` with props `{ active: Section; queueCount: number }`. It is a `<nav aria-label="Tabs">` with links Library, Queue and Settings. Queue has a red count badge with the number in text, using the rail's pattern `{n}<span class="sr-only"> in queue</span>`. Each link is at least 44 px tall and sets `aria-current="page"` when active. It pads `env(safe-area-inset-bottom)` and is `md:hidden`. It sits below `main` in the flex column, not `fixed`, so `main` never scrolls under it.
- Produces: `e2e/phone-helpers.ts`:

```ts
import { expect, type Locator, type Page } from "@playwright/test";

// `main` scrolls on its own (overflow-y-auto), so it clips sideways overflow and
// documentElement alone misses it. Check both.
export async function expectNoSideScroll(page: Page): Promise<void> {
  const m = await page.evaluate(() => {
    const main = document.querySelector("main");
    return {
      doc: document.documentElement.scrollWidth - window.innerWidth,
      main: main ? main.scrollWidth - main.clientWidth : 0,
    };
  });
  expect(m).toEqual({ doc: 0, main: 0 });
}

export async function expectTarget(loc: Locator): Promise<void> {
  const box = await loc.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
}
```

Tabs are named "Library", "Queue" and "Settings", the same as the rail's links. The rail is `display: none` below md, so `getByRole("link", { name: "Queue" })` finds only the tab. At 1440 px the tab bar is hidden, so the desktop specs (`shell.spec.ts`, `playlist.spec.ts`) find only the rail.

- [ ] **Step 1: Write the failing e2e tests** in `phone.spec.ts` (390×844, `hasTouch`, already set by `test.use`):
  - The Queue tab navigates and gets `aria-current="page"`. The `Main` nav (rail) is hidden. The `Tabs` nav is visible.
  - `expectNoSideScroll` on `#/`, `#/queue` and `#/settings`. Wait for each page's `h1` first.
  - `expectTarget` on every tab link, the Fetch button and the "Fetch options" button.
  - The theme tile (`/^Theme: /` button) is hidden. Settings shows the Dark, Light and System radios.
  - The top-bar field's computed `font-size` is at least 16 px.
  - Toast at the top: `page.route("**/api/queue", …)` answers `{active: [], failed: [], completed: []}` on the first poll and a done `JobOut` titled "Phone toast" after that. Every `JobOut` field must be present: `id, url, title, uploader, duration, thumbnail, status, progress, quality_cap, hdr, error_code, error_message, media_kind, file_size, media_format, resolution_height, created_at, finished_at`. The toast with "Phone toast" becomes visible, and its box's `y` is less than the top bar's bottom + 16. It is full width within the 16 px page margins.
- [ ] **Step 2: Run them and see them fail** (`PW_CHANNEL=chrome pnpm e2e -- phone` if the bundled headless shell is missing). Then build to the approved mockup.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`.** The desktop specs must still pass at 1440 px. **Commit** `feat(web): phone shell with bottom tab bar`

### Task 15: Phone Library, Queue, Settings and Watch

**Files:**
- Modify: `apps/server/tests/e2e_server.py` (seed one more done row, used only by `phone.spec.ts`: url `https://e2e.test/phone`, title "Phone video", uploader "E2E", file `phone.mp4` written with `b"data"`, same fields as "Seeded video". The lifespan moves it like the seeded file.)
- Modify: `apps/web/src/routes/Library.svelte` (below md: search full width on its own row, single-column list), `apps/web/src/components/JobCard.svelte` (below md: a row with the thumbnail on the left (about 40% wide) and title/meta on the right; the whole row opens `#/watch/<id>` through the existing title link overlay; the hover menu is not rendered below md, as decided in Task 13), `apps/web/src/components/Chips.svelte` (44 px tall below md, scroll sideways inside their own row if they don't fit; that row is `overflow-x-auto`, so it doesn't make `main` scroll), `apps/web/src/routes/Queue.svelte` (below md: thumbnail `w-28`, actions `min-h-11 min-w-11`), `apps/web/src/routes/Settings.svelte` (stacked form, Save/Reset 44 px), `apps/web/src/routes/Watch.svelte` (below md: player full bleed (negative `main` margin) or full width; Save and Delete `min-h-11`, full-width row in thumb reach)
- Test: `apps/web/e2e/phone.spec.ts`

Don't use "Seeded video" or "Slow video" in phone tests. Spec files run in parallel against one server. `library.spec.ts` deletes the seeded video and `queue.spec.ts` cancels the slow one.

- [ ] **Step 1: Write the failing e2e tests** (390×844):
  - Library: wait for "Phone video", then `expectNoSideScroll`. Tapping the "Phone video" link (`.tap()`) opens `#/watch/\d+`.
  - Queue: post your own slow job with `request.post("/api/downloads", { data: { jobs: [{ url: "https://e2e.test/slow-phone", title: "Phone slow video" }] } })` (201). Open `#/queue` and run `expectNoSideScroll`. Run `expectTarget` on that row's Cancel button. Tap Cancel and expect the row to go, so it doesn't hold the single worker for 20 s.
  - Settings: `expectNoSideScroll`. For every `textbox` and `spinbutton`, the bounding box's right edge is at most 390.
  - Watch (open "Phone video" from the library): the `video` box width is at most 390. `expectTarget` on `getByText("Save", { exact: true })` (a button here, since emulated touch makes `canShare` true) and on the Delete button. `expectNoSideScroll`.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone layout for library, queue, settings and player`

### Task 16: Phone Fetch views and override bottom sheet

**Files:**
- Create: `apps/web/src/components/BottomSheet.svelte`
- Modify: `apps/web/src/routes/VideoView.svelte` (below md: one column, `grid-cols-1 md:grid-cols-[minmax(0,1fr)_22rem]`; "Add to queue" 44 px), `apps/web/src/routes/ListView.svelte` (below md: toolbar wraps, buttons 44 px; the panel renders through `BottomSheet`), `apps/web/src/components/EntryCard.svelte` (select checkbox: 44 px hit area below md), `apps/web/src/components/OverridePanel.svelte` (new prop `sheet = false`; when true it renders only its body, without the `<aside>` frame, the title, the Close button or the window Escape handler, because the sheet provides them; unchanged when false)
- Test: `apps/web/e2e/phone.spec.ts`

**Interfaces:**
- Produces: `BottomSheet.svelte` with props `{ open: boolean; title: string; onclose: () => void; children: Snippet }`. This is a modal `<dialog>` docked to the bottom, `aria-labelledby` its `h2` (id from `$props.id()`). Max height `85dvh`, scrolls inside, pads `safe-area-inset-bottom`. It closes on Escape (`oncancel`: `preventDefault()` then `onclose()`), on a backdrop tap (`onclick` where `e.target === dialog`) and on a 44 px Close button, and returns focus to the opener. Shape checked in a throwaway build:

```svelte
$effect(() => {
  if (!open || !el) return;
  const dialog = el;
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  dialog.showModal();
  return () => {
    dialog.close();
    opener?.focus();
  };
});
```

Classes: `m-0 mt-auto max-h-[85dvh] w-full max-w-none overflow-y-auto rounded-t-control border-0 bg-surface p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-fg backdrop:bg-black/60`. The dialog's `onclick` needs `<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->` and `<!-- biome-ignore lint/a11y/useKeyWithClickEvents: Escape and the Close button cover keyboards -->`.
- In `ListView.svelte`: `const wide = new MediaQuery("(min-width: 768px)")` (from `svelte/reactivity`). Render `OverridePanel` as today when `wide.current`. Otherwise render it with `sheet` inside `<BottomSheet open title={…} onclose={() => (open = null)}>`. Only one renders at a time.

- [ ] **Step 1: Write the failing e2e tests** (390×844):
  - Video view: fetch `https://e2e.test/v/phone` (stubbed, title "Video Phone", lookup takes about 1 s). Don't use `https://e2e.test/video`, because a second "E2E Video" card breaks `video.spec.ts`. Wait for the `heading` "Video Phone", then `expectNoSideScroll`. `expectTarget` on "Add to queue". Tap it and expect "Added to queue.".
  - Playlist (`https://e2e.test/playlist`): wait for the `heading` "E2E Playlist", then `expectNoSideScroll`. Tap "Video A: customise". A `dialog` named "Video A" is visible and its bottom edge is at 844. Escape closes it and focus returns to "Video A: customise". Open it again and tap Close; it closes. Open it again and tap the backdrop (`page.mouse.click(195, 40)`); it closes.
  - The same playlist at 1440 px (`test.use` in a `describe` block) still shows the `complementary` "Settings for Video A" and no `dialog`.
- [ ] **Step 2: Run them and see them fail**, then build to the mockups.
- [ ] **Step 3: Run `pnpm check && pnpm e2e`. Commit** `feat(web): phone fetch views with bottom-sheet overrides`

### Task 17: Critique and polish pass

**Files:** whichever phone views the critique flags. Also `DESIGN.md` if a rule changes.

- [ ] **Step 1: Run the Impeccable skill's critique and audit on every phone screen in both themes**, plus the taste-skill anti-slop checks. List the findings in the mockups doc.
- [ ] **Step 2: Fix each finding in its own small commit,** with a test where the finding is behavioural.
- [ ] **Step 3: Check contrast (AA) for the tab bar, the badges and the toasts in both themes.** Check that the phone e2e suite passes.
- [ ] **Step 4: Check by hand on the iPhone (installed app):** no sideways scroll on any screen, the top bar clears the status bar, the tab bar clears the home indicator, the field does not zoom on focus, and the sheet scrolls inside. Record the result in the mockups doc.
- [ ] **Step 5: Show the owner the final screenshots.** Commit `polish(web): phone layout critique fixes`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
