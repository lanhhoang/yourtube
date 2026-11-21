import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
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
