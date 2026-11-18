import { expect, test } from "@playwright/test";
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
