import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("delete in library", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const card = page.getByRole("article").filter({ hasText: "Seeded video" });
  await card.hover();
  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Confirm delete" }).click();
  await expect(card).toHaveCount(0);
});
