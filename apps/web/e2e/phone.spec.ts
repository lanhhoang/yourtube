import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";
import { expectNoSideScroll, expectTarget } from "./phone-helpers.ts";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

test("Paste fills the field without fetching", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(`${APP}#/`);
  await page.evaluate(() => navigator.clipboard.writeText("https://youtu.be/a"));
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(page.getByRole("textbox", { name: "Video or playlist URL" })).toHaveValue(
    "https://youtu.be/a",
  );
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole("button", { name: "Paste" })).toBeHidden();
});

test("Paste falls back to focusing the field", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { readText: () => Promise.reject(new Error("denied")) },
    });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("button", { name: "Paste" }).click();
  await expect(page.getByRole("textbox", { name: "Video or playlist URL" })).toBeFocused();
});

test("tab bar navigates and the rail is hidden", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Tabs" })).toBeVisible();
  await page.getByRole("link", { name: "Queue" }).tap();
  await expect(page).toHaveURL(/#\/queue$/);
  await expect(page.getByRole("link", { name: "Queue" })).toHaveAttribute("aria-current", "page");
});

test("no sideways scroll on library, queue and settings", async ({ page }) => {
  for (const [hash, heading] of [
    ["#/", /.*/],
    ["#/queue", "Queue"],
    ["#/settings", "Settings"],
  ] as const) {
    await page.goto(`${APP}${hash}`);
    if (hash !== "#/")
      await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expectNoSideScroll(page);
  }
});

test("shell targets are at least 44 px", async ({ page }) => {
  await page.goto(`${APP}#/`);
  for (const name of ["Library", "Queue", "Settings"]) {
    await expectTarget(page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name }));
  }
  await expectTarget(page.getByRole("button", { name: "Fetch", exact: true }));
  await expectTarget(page.getByRole("button", { name: "Fetch options" }));
});

test("theme tile is hidden; Settings has the theme radios; field is 16 px", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.getByRole("button", { name: /^Theme: / })).toBeHidden();
  for (const name of ["Dark", "Light", "System"]) {
    await expect(page.getByRole("radio", { name })).toBeVisible();
  }
  const size = await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .evaluate((el) => Number.parseFloat(getComputedStyle(el).fontSize));
  expect(size).toBeGreaterThanOrEqual(16);
});

test("toast sits at the top, under the top bar", async ({ page }) => {
  let polls = 0;
  const job = {
    id: 9001,
    url: "https://e2e.test/toast",
    title: "Phone toast",
    uploader: null,
    duration: null,
    thumbnail: null,
    status: "done",
    progress: 100,
    quality_cap: null,
    hdr: false,
    error_code: null,
    error_message: null,
    media_kind: "video",
    file_size: 4,
    media_format: "mp4",
    resolution_height: 1080,
    created_at: "2026-11-18T00:00:00",
    finished_at: "2026-11-18T00:00:01",
  };
  await page.route("**/api/queue", (route) => {
    polls += 1;
    return route.fulfill({
      json: { active: [], failed: [], completed: polls === 1 ? [] : [job] },
    });
  });
  await page.goto(`${APP}#/`);
  const toast = page.getByText("Phone toast");
  await expect(toast).toBeVisible({ timeout: 10_000 });
  const box = await toast.boundingBox();
  expect(box?.y ?? 999).toBeLessThan(120);
});
