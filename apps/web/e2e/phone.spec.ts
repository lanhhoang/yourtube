import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

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
