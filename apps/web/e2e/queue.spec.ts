import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("cancel in queue", async ({ page }) => {
  await page.goto(`${APP}#/queue`);
  const row = page.getByRole("listitem").filter({ hasText: "Slow video" });
  await row.getByRole("button", { name: "Cancel" }).click();
  await expect(row).toHaveCount(0);
});
