import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { APP } from "./app.ts";

const downloads = resolve(import.meta.dirname, "../../../tmp/e2e/downloads");

test("player opens from the library and reports unplayable files", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Seeded video" }).click();
  await expect(page).toHaveURL(/#\/watch\/\d+$/);
  await expect(page.locator("video")).toHaveAttribute("src", /file\?inline=1$/);
  await expect(page.getByRole("button", { name: "Delete" })).toBeVisible();
  await expect(page.getByText("Save", { exact: true })).toBeVisible();
  await expect(page.getByText("E2E · 1080p · SDR · 4 B · h264 · aac · mp4")).toBeVisible();
  const tracks = page.locator("video track");
  await expect(tracks).toHaveCount(2);
  for (const [i, label, lang] of [
    [0, "French (auto)", "fr"],
    [1, "English", "en"],
  ] as const) {
    const t = tracks.nth(i);
    await expect(t).toHaveAttribute("label", label);
    await expect(t).toHaveAttribute("srclang", lang);
    await expect(t).toHaveAttribute("kind", "subtitles");
    await expect(t).not.toHaveAttribute("default");
  }
  const vtt = await page.request.get(
    new URL((await tracks.nth(0).getAttribute("src")) ?? "", page.url()).href,
  );
  expect(vtt.status()).toBe(200);
  expect(await vtt.text()).toMatch(/^WEBVTT/);
  await page.locator("video").evaluate((v) => v.dispatchEvent(new Event("error")));
  await expect(
    page.getByText("This device can't play this file. Save it and open it in VLC."),
  ).toBeVisible();
});

test("Save is a download link without share support", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "canShare", { value: undefined });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Seeded video" }).click();
  const save = page.getByRole("link", { name: "Save" });
  await expect(save).toHaveAttribute("download", "");
  await expect(save).toHaveAttribute("href", /\/file$/);
});

test("Save prepares the file, then shares it on a second tap", async ({ page }) => {
  await page.addInitScript(() => {
    const w = window as unknown as { __shared?: unknown };
    Object.defineProperty(navigator, "canShare", { value: () => true });
    const media = window.matchMedia.bind(window);
    window.matchMedia = (q: string) =>
      q === "(pointer: coarse)" ? ({ matches: true } as MediaQueryList) : media(q);
    Object.defineProperty(navigator, "share", {
      value: (d: { files: File[] }) => {
        w.__shared = d.files.map((f) => [f.name, f.size, f.type]);
        return Promise.resolve();
      },
    });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Seeded video" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await page.getByRole("button", { name: "Share file" }).click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __shared?: unknown }).__shared))
    .toEqual([["Seeded video.mp4", 4, "video/mp4"]]);
});

test("tapping the thumbnail opens the player", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const card = page.getByRole("article").filter({ hasText: "Seeded video" });
  await card.click({ position: { x: 20, y: 20 } }); // over the thumbnail
  await expect(page).toHaveURL(/#\/watch\/\d+$/);
});

test("desktop Save downloads even when files can be shared", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "canShare", { value: () => true });
  });
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Seeded video" }).click();
  await expect(page.getByRole("link", { name: "Save" })).toHaveAttribute("download", "");
});

test("a missing download says so", async ({ page }) => {
  await page.goto(`${APP}#/watch/999999`);
  await expect(page.getByText("This download no longer exists.")).toBeVisible();
});

test("select mode does not navigate", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.getByRole("link", { name: "Seeded video" })).toBeVisible();
  await page.getByRole("button", { name: "Select", exact: true }).click();
  await expect(page.getByRole("link", { name: "Seeded video" })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "Slow video" })).toHaveCount(0);
  const box = page.getByRole("checkbox", { name: "Seeded video" });
  // The card-wide label sits over the title, so click the title's position directly.
  await page.getByRole("heading", { name: "Seeded video" }).click({ force: true });
  await expect(page).toHaveURL(/#\/$/);
  await expect(box).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(box).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Seeded video" })).toBeVisible();
});

test("library lists finished downloads only", async ({ page }) => {
  await page.route("**/api/queue", (route) =>
    route.fulfill({
      json: {
        active: [
          {
            id: 9201,
            url: "https://example.com/active",
            title: "Stubbed active",
            status: "active",
            progress: 40,
            media_kind: "video",
          },
        ],
        failed: [],
        completed: [],
        batches: [],
      },
    }),
  );
  await page.goto(`${APP}#/`);
  await expect(page.getByRole("link", { name: "Seeded video" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Stubbed active" })).toHaveCount(0);
  await expect(page.getByRole("radiogroup", { name: "Filter" })).toHaveCount(0);
});

test("delete in library", async ({ page }) => {
  // The startup move put the seeded file in its channel folder.
  const moved = resolve(downloads, "e2e/seeded-video.mp4");
  expect(existsSync(moved)).toBe(true);
  expect(existsSync(resolve(downloads, "seeded.mp4"))).toBe(false);
  const srts = ["e2e/seeded-video.en.srt", "e2e/seeded-video.fr-orig.srt"].map((f) =>
    resolve(downloads, f),
  );
  expect(existsSync(srts[0])).toBe(true);

  await page.goto(`${APP}#/`);
  const card = page.getByRole("article").filter({ hasText: "Seeded video" });
  await card.hover();
  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Confirm delete" }).click();
  await expect(card).toHaveCount(0);
  await expect.poll(() => existsSync(moved)).toBe(false);
  await expect.poll(() => srts.some((f) => existsSync(f))).toBe(false);
});

test("select and delete several", async ({ page }) => {
  const files = ["bulk-a.mp4", "bulk-b.mp4"].map((f) => resolve(downloads, "e2e", f));
  for (const f of files) expect(existsSync(f)).toBe(true);
  await page.goto(`${APP}#/`);
  await page.getByRole("button", { name: "Select", exact: true }).click();
  await page.getByRole("checkbox", { name: "Bulk A" }).check();
  await page.getByRole("checkbox", { name: "Bulk B" }).check();
  await expect(page.getByText("2 selected")).toBeVisible();
  const bar = page.getByRole("region", { name: "Selection" });
  await bar.getByRole("button", { name: "Delete", exact: true }).click();
  await bar.getByRole("button", { name: "Delete 2?" }).click();
  await expect(page.getByRole("article").filter({ hasText: "Bulk A" })).toHaveCount(0);
  await expect(page.getByRole("article").filter({ hasText: "Bulk B" })).toHaveCount(0);
  await expect.poll(() => files.some((f) => existsSync(f))).toBe(false);
  await expect(page.getByText("Deleted 2", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Select", exact: true })).toBeVisible();
});

const titles = (page: Page) => page.getByRole("heading", { level: 3 }).allTextContents();
const order = async (page: Page) => (await titles(page)).filter((t) => t.startsWith("Sort "));
const row = (page: Page, title: string) =>
  page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) });

test("sort by title", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(row(page, "Sort A")).toBeVisible();
  const byDate = await order(page);
  expect(byDate.indexOf("Sort B")).toBeLessThan(byDate.indexOf("Sort A"));
  await page.getByLabel("Sort").selectOption({ label: "Title A–Z" });
  await expect
    .poll(async () => {
      const t = await order(page);
      return t.indexOf("Sort A") < t.indexOf("Sort B");
    })
    .toBe(true);
});

test("filter by channel and clear", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(row(page, "Sort A")).toBeVisible();
  await page.getByRole("button", { name: /^Filter/ }).click();
  const dialog = page.getByRole("dialog", { name: "Filters" });
  await dialog.getByLabel("Channel").selectOption("Other");
  await expect(row(page, "Sort listed")).toBeVisible();
  await expect(row(page, "Sort A")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Filter · 1" })).toBeVisible();
  await expect(page.getByText("Channel: Other", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: "Remove filter Channel: Other" }).click();
  await expect(row(page, "Sort A")).toBeVisible();
});

test("filter by type audio", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(row(page, "Sort A")).toBeVisible();
  await page.getByRole("button", { name: /^Filter/ }).click();
  const dialog = page.getByRole("dialog", { name: "Filters" });
  await dialog.getByRole("radiogroup", { name: "Type" }).getByLabel("Audio").check({ force: true });
  await expect(row(page, "Sort audio")).toBeVisible();
  await expect(row(page, "Sort A")).toHaveCount(0);
  await expect(row(page, "Sort listed")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(row(page, "Sort A")).toBeVisible();
});

test("a search keeps the channel filter", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(row(page, "Sort A")).toBeVisible();
  await page.getByRole("button", { name: /^Filter/ }).click();
  await page.getByRole("dialog", { name: "Filters" }).getByLabel("Channel").selectOption("Other");
  await page.keyboard.press("Escape");
  await page.getByRole("searchbox", { name: "Search library" }).fill("Sort A");
  await expect(page.getByText("No videos match these filters.")).toBeVisible();
  await expect(page.getByText("Channel: Other", { exact: true })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search library" }).fill("");
  await expect(row(page, "Sort listed")).toBeVisible();
});

test("view persists; a stale channel is dropped", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByLabel("Sort").selectOption("added-asc");
  await page.reload();
  await expect(page.getByLabel("Sort")).toHaveValue("added-asc");
  await page.evaluate(() =>
    localStorage.setItem(
      "yt.library.view",
      '{"sort":"added-desc","kind":"any","channel":"Gone","playlist":null}',
    ),
  );
  await page.reload();
  await expect(row(page, "Sort A")).toBeVisible();
  await expect(page.getByText("Channel: Gone")).toHaveCount(0);
});
