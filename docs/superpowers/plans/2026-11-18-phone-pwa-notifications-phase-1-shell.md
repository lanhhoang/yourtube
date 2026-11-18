# Phase 1: Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the YourTube player mark next to the wordmark, swap in the new play-circle favicon, and make the rail theme switch one icon button that cycles Dark → Light → System.

**Usable result:** The top bar shows the red player mark (a rounded screen with a play triangle and a scrub bar), and the browser tab shows the new play-circle favicon. One tile in the rail switches the theme, and Settings keeps its three-option control. Both stay in sync.

**Architecture:** Web only. A `LogoMark` component, a replaced `public/favicon.svg`, plus a shared theme state module (`theme-state.svelte.ts`) used by the rail tile and the Settings control. No server changes.

**Tech Stack:** Svelte 5 runes, Tailwind 4, Vitest, Playwright. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§3 Logo, §4 Theme switch)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 1, 2. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** `main` at `4ae33a5` or later (the design doc is committed). Nothing from other phases.

**Before you start:** e2e needs a Playwright browser. If `pnpm e2e` fails with "Executable doesn't exist", run `pnpm --filter @app/web exec playwright install chromium`, or set `PW_CHANNEL=chrome` to use the installed Google Chrome. Pass Playwright arguments straight after `e2e` (`pnpm --filter @app/web e2e shell.spec.ts`). Don't put `--` in front of them: pnpm forwards the `--` to Playwright, which then ignores the file filter and `-g` and runs the whole suite.

## Global Constraints

- Run `pnpm check` (repo root) before every commit. Run `pnpm format` to fix formatting. After any API schema change, run `pnpm typegen` and commit `apps/web/src/lib/api.gen.ts`.
- Stack stays: FastAPI + yt-dlp + SQLite (Alembic) + worker threads; Svelte 5 + Vite + Tailwind 4; one process, one port. The Docker image ships everything.
- `DESIGN.md` is the visual contract. Red is the only accent. WCAG AA in both themes. Status is never shown by colour alone.
- Nothing loads from a CDN at runtime.
- Streams are copied and remuxed, never transcoded. No HDR output.
- Never silently download below the chosen cap (existing principle, unchanged).
- Never break or lose existing library files. A failed move leaves the file and its row as they were.
- A 500-video playlist must not send 500 pushes: jobs in a batch send no per-job push and no per-job toast.
- No login, no multi-user accounts. Tailscale is the access boundary. Never expose the app to the public internet.
- iOS: PWA install and Web Push need HTTPS and a home-screen install (iOS 16.4+). iOS has no Web Share Target.
- Phone layout is below 768 px. Touch targets are at least 44 px.
- Database changes go through a new Alembic revision. Never edit an existing revision.
- Follow the existing test layout: pytest `tests/unit`, `tests/api`, `tests/integration`; Vitest `apps/web/test`; Playwright `apps/web/e2e` (stubbed server `tests/e2e_server.py`).

## Review Focus

1. Theme state must stay shared. Changing it in the rail must show in Settings without a reload, and the other way round (Task 2's e2e checks both). The mark must be decorative (`aria-hidden`), so the link name stays "yourtube" (Task 1).

---

### Task 1: Logo mark in the top bar, new favicon

The owner supplied two new marks (2026-11-18). Their cleaned markup is below, so you don't need the gitignored originals in `tmp/`.
- **Top-bar mark:** a red rounded screen with a white play triangle and a pale scrub bar. It's wide, about 1.44:1. Source: `tmp/icon.svg`.
- **Favicon:** a two-tone red play-circle with a white triangle. Source: `tmp/favicon.svg`. It replaces the old SVG Repo play-circle, and Phase 4 generates the PWA icons from it.

Both marks keep their own fixed colours in both themes. They don't use the `accent` token.

**Files:**
- Create: `apps/web/src/components/LogoMark.svelte`
- Modify: `apps/web/src/components/TopBar.svelte` (replace the red bar `<span class="block h-3 w-[18px] …">`)
- Replace: `apps/web/public/favicon.svg` (`index.html` already links it, so no change there)
- Modify: `DESIGN.md` (logo mark in Layout, `accent` row and colour rules)
- Test: `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Produces: `LogoMark.svelte`, with prop `size?: number` (height in px, default 20). Width is `Math.round(size * 90 / 62.583)`, which is 29 at 20 px. It has `aria-hidden="true"` and `focusable="false"`, and its colours are fixed in both themes. Phase 5 (phone top bar, mark only) reuses it.
- Produces: `public/favicon.svg`. Phase 4 builds `public/icon.svg` and the PWA PNGs from this mark.

`LogoMark.svelte` body (the viewBox is cropped to the screen shape, so there's no empty band above or below):

```svelte
<script lang="ts">
  let { size = 20 }: { size?: number } = $props();
</script>

<svg
  viewBox="0 13.708 90 62.583"
  width={Math.round((size * 90) / 62.583)}
  height={size}
  aria-hidden="true"
  focusable="false"
  class="block shrink-0"
>
  <path fill="#ff0000" d="M 83.494 76.291 H 6.506 C 2.913 76.291 0 73.379 0 69.786 V 20.214 c 0 -3.593 2.913 -6.506 6.506 -6.506 h 76.988 c 3.593 0 6.506 2.913 6.506 6.506 v 49.571 C 90 73.379 87.087 76.291 83.494 76.291 z" />
  <path fill="#ffffff" d="M 36.457 53.756 L 54.9 43.107 c 0.904 -0.522 0.904 -1.828 0 -2.35 l -18.443 -10.65 c -0.904 -0.522 -2.035 0.13 -2.035 1.175 v 21.299 C 34.422 53.626 35.552 54.278 36.457 53.756 z" />
  <path fill="#ff7c7c" d="M 81.317 67.598 h -6.608 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.457 -1.023 1.023 -1.023 h 6.608 c 0.565 0 1.023 0.457 1.023 1.023 C 82.34 67.14 81.882 67.598 81.317 67.598 z" />
  <path fill="#ff7c7c" d="M 65.764 67.598 H 21.513 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.458 -1.023 1.023 -1.023 h 44.251 c 0.565 0 1.023 0.457 1.023 1.023 C 66.787 67.14 66.329 67.598 65.764 67.598 z" />
  <path fill="#ff7c7c" d="M 14.992 67.598 H 8.684 c -0.565 0 -1.023 -0.457 -1.023 -1.023 c 0 -0.565 0.458 -1.023 1.023 -1.023 h 6.309 c 0.565 0 1.023 0.457 1.023 1.023 C 16.015 67.14 15.557 67.598 14.992 67.598 z" />
  <circle fill="#ff7c7c" cx="18.25" cy="66.58" r="3.26" />
</svg>
```

New `public/favicon.svg` (the full file):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 90">
  <title>YourTube</title>
  <path fill="#bb1a1a" d="M 45 90 C 20.187 90 0 69.813 0 45 c 31.16 -8.812 61.257 -9.555 90 0 C 90 69.813 69.813 90 45 90 z" />
  <path fill="#dd2222" d="M 45 0 C 20.187 0 0 20.187 0 45 h 90 C 90 20.187 69.813 0 45 0 z" />
  <path fill="#f0f0f0" d="M 63.885 47.325 l -14.816 8.554 l -14.816 8.554 c -1.79 1.033 -4.026 -0.258 -4.026 -2.325 V 45 c 10.606 -4.196 22.359 -3.855 35 0 C 65.227 45.904 64.78 46.808 63.885 47.325 z" />
  <path fill="#ffffff" d="M 63.885 42.675 l -14.816 -8.554 l -14.816 -8.554 c -1.79 -1.033 -4.026 0.258 -4.026 2.325 V 45 h 35 C 65.227 44.096 64.78 43.192 63.885 42.675 z" />
</svg>
```

- [ ] **Step 1: Write the failing e2e test**

```ts
test("wordmark shows the player mark", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const home = page.getByRole("link", { name: "yourtube" });
  const mark = home.locator("svg[aria-hidden='true']");
  await expect(mark).toBeVisible();
  const box = await mark.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(17);
  expect(box?.height).toBeLessThanOrEqual(22);
  expect(box?.width).toBeGreaterThan(box?.height ?? 0);
});
```

- [ ] **Step 2: Run it and see it fail**

Run: `pnpm --filter @app/web e2e shell.spec.ts -g "player mark"`
Expected: FAIL, no `svg` inside the link.

- [ ] **Step 3: Add `LogoMark.svelte`, use it in `TopBar.svelte` in place of the red bar, and replace `public/favicon.svg`** (markup above). Keep the link's `w-[120px]` and `gap-2`. A 29 px mark plus "yourtube" fits in 120 px; this was measured in the built app. The link's accessible name stays "yourtube". Update `DESIGN.md`:
  - Layout: change "wordmark (red mark + "yourtube")" to "wordmark (player mark, 20 px tall, + "yourtube")".
  - Colour table, `accent` row: drop "logo mark" from its uses.
  - Rules line: change "red marks the logo mark, progress bars, …" to "red marks progress bars, …". Then add one sentence: "The logo mark and favicon are fixed brand artwork in their own reds (`#ff0000` mark, `#dd2222`/`#bb1a1a` favicon). They are the same in both themes and are not tokens."

- [ ] **Step 4: Run the e2e file and `pnpm check`**

Run: `pnpm --filter @app/web e2e shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 5: Commit** `feat(web): player logo mark in the top bar and new favicon`

### Task 2: Theme tile that cycles Dark → Light → System

**Files:**
- Modify: `apps/web/src/lib/theme.ts`
- Create: `apps/web/src/lib/theme-state.svelte.ts`
- Create: `apps/web/src/components/ThemeToggle.svelte`
- Modify: `apps/web/src/components/ThemeSelect.svelte` (read and write the shared state instead of its own module `$state`)
- Modify: `apps/web/src/components/LeftRail.svelte` (footer uses `ThemeToggle`)
- Modify: `DESIGN.md` (theme tile)
- Test: `apps/web/test/theme.test.ts`, `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: `ThemeChoice`, `applyTheme`, `currentTheme` from `lib/theme.ts`.
- Produces:
  - `nextTheme(choice: ThemeChoice): ThemeChoice` (dark → light → system → dark)
  - `themeLabel(choice: ThemeChoice): string`, e.g. `"Theme: Dark. Switch to Light"`
  - `theme-state.svelte.ts`: `export const themeState: { choice: ThemeChoice }` (a `$state` object) and `setTheme(choice: ThemeChoice): void` (sets the state and calls `applyTheme`). `ThemeSelect` (Settings) and `ThemeToggle` (rail) both use it.

- [ ] **Step 1: Write the failing unit tests** in `test/theme.test.ts`

Extend the existing import to `import { isDark, nextTheme, readTheme, themeLabel } from "../src/lib/theme.ts";` and add:

```ts
test("nextTheme cycles", () => {
  expect(nextTheme("dark")).toBe("light");
  expect(nextTheme("light")).toBe("system");
  expect(nextTheme("system")).toBe("dark");
});
test("themeLabel names current and next", () => {
  expect(themeLabel("dark")).toBe("Theme: Dark. Switch to Light");
  expect(themeLabel("light")).toBe("Theme: Light. Switch to System");
  expect(themeLabel("system")).toBe("Theme: System. Switch to Dark");
});
```

- [ ] **Step 2: Run them and see them fail**

Run: `pnpm vitest run apps/web/test/theme.test.ts`
Expected: FAIL, because `nextTheme` and `themeLabel` don't exist yet.

- [ ] **Step 3: Implement `nextTheme`, `themeLabel`, `theme-state.svelte.ts`, `ThemeToggle.svelte`**

- `theme-state.svelte.ts`: `export const themeState = $state({ choice: currentTheme() })`. `setTheme` assigns `themeState.choice` and calls `applyTheme`. Export an object, because Svelte doesn't allow exporting a reassigned `$state` primitive.
- `ThemeSelect.svelte`: delete the `<script module>` block and its module `$state`. `checked` reads `themeState.choice`, and `onchange` calls `setTheme(c.value)`. Keep the `label` prop and markup.
- `ThemeToggle.svelte`: a `<button type="button">` built like the rail links (`w-16` with `py-1.5`, around a `size-7` `bg-raised` tile holding a `size-4` stroke icon), so the hit area is at least 44 px tall. It shows the moon (dark), sun (light) or monitor (system) as inline SVG with `aria-hidden`. There is no visible text label. `aria-label` and `title` are `themeLabel(themeState.choice)`, and a click calls `setTheme(nextTheme(themeState.choice))`. Keep the existing focus-visible outline style.
- `LeftRail.svelte`: swap `<div class="px-1"><ThemeSelect /></div>` for a centred `ThemeToggle`. Settings keeps `ThemeSelect` (its "Theme (settings)" label can stay).
- `DESIGN.md` → Layout: change "theme switch in the rail footer" to "theme tile in the rail footer (moon/sun/monitor, cycles Dark → Light → System; Settings keeps the three-option control)".

- [ ] **Step 4: Update the e2e theme test** in `shell.spec.ts`. Replace "dark by default, theme switch persists" with the test below. It runs on Settings so both controls are on screen. That way it checks the sync in both directions without a reload, then checks that the choice persists.

```ts
test("rail theme tile cycles, persists and stays in sync with Settings", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Theme: Dark. Switch to Light" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  await page.getByText("System", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
});
```

- [ ] **Step 5: Run unit, e2e and `pnpm check`** (`pnpm check` includes `vitest run`)

Run: `pnpm --filter @app/web e2e shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 6: Commit** `feat(web): one-button theme tile in the rail`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
