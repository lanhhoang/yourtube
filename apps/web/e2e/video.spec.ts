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
