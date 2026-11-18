# Phase 1: Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the YourTube play-circle next to the wordmark, and make the rail theme switch one icon button that cycles Dark → Light → System.

**Usable result:** The top bar shows the red play-circle mark. One tile in the rail switches the theme, and Settings keeps its three-option control. Both stay in sync.

**Architecture:** Web only. A `LogoMark` component, plus a shared theme state module (`theme-state.svelte.ts`) used by the rail tile and the Settings control. No server changes.

**Tech Stack:** Svelte 5 runes, Tailwind 4, Vitest, Playwright. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-18-phone-pwa-notifications-design.md` (§3 Logo, §4 Theme switch)

**Parent plan:** `docs/superpowers/plans/2026-11-18-phone-pwa-notifications.md`, Tasks 1, 2. The tasks below are copied from it verbatim; the parent plan wins if they ever differ. Phase index: `docs/superpowers/plans/2026-11-18-phone-pwa-notifications-phases.md`.

**Prerequisites:** `main` at `4ae33a5` or later (the design doc is committed). Nothing from other phases.

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

1. Theme state must stay shared: changing it in the rail must show in Settings without a reload (Task 2's e2e checks this). The mark must be decorative (`aria-hidden`), so the link name stays "yourtube" (Task 1).

---

### Task 1: Logo mark in the top bar

**Files:**
- Create: `apps/web/src/components/LogoMark.svelte`
- Modify: `apps/web/src/components/TopBar.svelte` (replace the red bar `<span class="block h-3 w-[18px] …">`)
- Modify: `DESIGN.md` (logo mark under the top bar)
- Test: `apps/web/e2e/shell.spec.ts`

**Interfaces:**
- Produces: `LogoMark.svelte` with prop `size?: number` (px, default 20). Inline SVG copied from `public/favicon.svg`: red `#DB2B42` circle, white triangle in both themes, `aria-hidden="true"`, `focusable="false"`. Tasks 9 and 12 reuse it.

- [ ] **Step 1: Write the failing e2e test**

```ts
test("wordmark shows the play-circle mark", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const home = page.getByRole("link", { name: "yourtube" });
  const mark = home.locator("svg[aria-hidden='true']");
  await expect(mark).toBeVisible();
  const box = await mark.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(17);
  expect(box?.height).toBeLessThanOrEqual(22);
});
```

- [ ] **Step 2: Run it and see it fail**

Run: `pnpm --filter @app/web e2e -- shell.spec.ts -g "play-circle"`
Expected: FAIL, no `svg` inside the link.

- [ ] **Step 3: Add `LogoMark.svelte` and use it in `TopBar.svelte`** in place of the red bar. The link's accessible name stays "yourtube". Add one line about the mark to `DESIGN.md`'s top-bar section.

- [ ] **Step 4: Run the e2e file and `pnpm check`**

Run: `pnpm --filter @app/web e2e -- shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 5: Commit** `feat(web): play-circle logo mark in the top bar`

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
Expected: FAIL, `nextTheme` is not exported.

- [ ] **Step 3: Implement `nextTheme`, `themeLabel`, `theme-state.svelte.ts`, `ThemeToggle.svelte`**

`ThemeToggle` is a rail-style tile `<button>`: it shows the moon (dark), sun (light) or monitor (system) icon as inline SVG with `aria-hidden`. `aria-label` and `title` are `themeLabel(choice)`, and a click calls `setTheme(nextTheme(choice))`. Replace `ThemeSelect` in the rail footer. Settings keeps `ThemeSelect`.

- [ ] **Step 4: Update the e2e theme test** in `shell.spec.ts`. Replace "dark by default, theme switch persists" with:

```ts
test("rail theme tile cycles and persists", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Theme: Dark. Switch to Light" }).click();
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Theme: Light. Switch to System" })).toBeVisible();
  await page.goto(`${APP}#/settings`);
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
});
```

- [ ] **Step 5: Run unit, e2e and `pnpm check`**

Run: `pnpm --filter @app/web e2e -- shell.spec.ts && pnpm check`
Expected: all pass.

- [ ] **Step 6: Commit** `feat(web): one-button theme tile in the rail`

---

## Done when

- Every task above is committed and `pnpm check && pnpm e2e` pass on the branch.
- The usable result above works by hand.
