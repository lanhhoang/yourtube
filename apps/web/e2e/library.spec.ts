import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

const downloads = resolve(import.meta.dirname, "../../../tmp/e2e/downloads");

test("delete in library", async ({ page }) => {
  // The startup move put the seeded file in its channel folder.
  const moved = resolve(downloads, "e2e/seeded-video.mp4");
  expect(existsSync(moved)).toBe(true);
  expect(existsSync(resolve(downloads, "seeded.mp4"))).toBe(false);

  await page.goto(`${APP}#/`);
  const card = page.getByRole("article").filter({ hasText: "Seeded video" });
  await card.hover();
  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Confirm delete" }).click();
  await expect(card).toHaveCount(0);
  await expect.poll(() => existsSync(moved)).toBe(false);
});
