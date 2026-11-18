import { expect, type Page, test } from "@playwright/test";
import { APP } from "./app.ts";

test("fetch playlist, wait for checks, add", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/playlist");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Playlist" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Checking \d+ \/ 3/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Add 2 to queue" })).toBeEnabled();
  await expect(page.getByText("720p max", { exact: true })).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Add 2 to queue" }).click();
  await expect(page.getByText("Added 2 to queue.")).toBeVisible();
});

// The checker runs two lookups at a time, so the third entry waits in the queue.
async function openPlaylist(page: Page): Promise<string[]> {
  const lookups: string[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/lookup")) lookups.push(r.postDataJSON().url);
  });
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/playlist");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Playlist" })).toBeVisible();
  return lookups;
}

test("deselecting a queued entry skips its check, reselecting runs it", async ({ page }) => {
  const lookups = await openPlaylist(page);
  await page.getByRole("checkbox", { name: "Select Video Gone" }).uncheck();
  await expect(page.getByRole("button", { name: "Add 2 to queue" })).toBeEnabled();
  expect(lookups).toEqual(["https://e2e.test/v/a", "https://e2e.test/v/b"]);
  await page.getByRole("checkbox", { name: "Select Video Gone" }).check();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  expect(lookups).toHaveLength(3);
});

test("leaving the playlist stops checking", async ({ page }) => {
  const lookups = await openPlaylist(page);
  await page.getByRole("link", { name: "Queue" }).click();
  await page.waitForTimeout(2500); // past when the queued third lookup would start
  expect(lookups).toEqual(["https://e2e.test/v/a", "https://e2e.test/v/b"]);
});

test("HDR badge follows the cap", async ({ page }) => {
  await openPlaylist(page);
  await expect(page.getByRole("button", { name: "Add 2 to queue" })).toBeEnabled();
  const card = (name: string) => page.getByRole("article").filter({ hasText: name });
  await page.getByRole("combobox", { name: "Quality" }).selectOption("best");
  await expect(card("Video A").getByText("HDR", { exact: true })).toBeVisible();
  await expect(card("Video B").getByText("HDR", { exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Quality" }).selectOption("1080");
  await expect(card("Video A").getByText(/^HDR/)).toHaveCount(0);
});
