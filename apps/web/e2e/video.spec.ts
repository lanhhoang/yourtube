import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("fetch single video and add to queue", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("textbox", { name: "Video or playlist URL" }).fill("https://e2e.test/video");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Video" })).toBeVisible();
  await page.getByRole("combobox", { name: "Quality" }).selectOption("720");
  await page.getByRole("button", { name: "Add to queue" }).click();
  await expect(page.getByText("Added to queue.")).toBeVisible();
  await page.goto(`${APP}#/`);
  await expect(page.getByRole("article").filter({ hasText: "E2E Video" })).toBeVisible();
});

test("watch URL with a list opens the video", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/watch?v=e2e&list=PLe2e");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Video" })).toBeVisible();
});

test("a bad output template shows the server's message", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("textbox", { name: "Video or playlist URL" }).fill("https://e2e.test/video");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await page.getByRole("tab", { name: "Advanced" }).click();
  await page.getByLabel("Output template").fill("../x.%(ext)s");
  await page.getByRole("button", { name: "Add to queue" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
});

async function fetchVideo(page: import("@playwright/test").Page, url: string) {
  await page.goto(`${APP}#/`);
  await page.getByRole("textbox", { name: "Video or playlist URL" }).fill(url);
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
}

test("HDR is disabled when the video has no HDR", async ({ page }) => {
  await fetchVideo(page, "https://e2e.test/video");
  await expect(page.getByRole("checkbox", { name: "HDR (not offered)" })).toBeDisabled();
});

test("HDR can be ticked on an HDR video", async ({ page }) => {
  await fetchVideo(page, "https://e2e.test/v/a");
  const box = page.getByRole("checkbox", { name: "HDR", exact: true });
  await expect(box).toBeEnabled();
  await box.check();
  const request = page.waitForRequest((r) => r.url().endsWith("/api/downloads"));
  await page.getByRole("button", { name: "Add to queue" }).click();
  expect((await request).postDataJSON().jobs[0].hdr).toBe(true);
});

test("the HDR note appears only when the cap lands above the HDR size", async ({ page }) => {
  await fetchVideo(page, "https://e2e.test/v/lowhdr");
  await page.getByRole("checkbox", { name: "HDR", exact: true }).check();
  const note = page.getByText("HDR only up to 1080p. This cap gets SDR.");
  await expect(note).toHaveCount(0);
  await page.getByRole("combobox", { name: "Quality" }).selectOption("best");
  await expect(note).toBeVisible();
  await page.getByRole("combobox", { name: "Quality" }).selectOption("1080");
  await expect(note).toHaveCount(0);
});
