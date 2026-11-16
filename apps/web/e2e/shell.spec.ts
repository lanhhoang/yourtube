import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("dark by default, theme switch persists", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByText("Light", { exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
});

test("rail navigates", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Queue" }).click();
  await expect(page).toHaveURL(/#\/queue$/);
  await expect(page.getByRole("link", { name: "Queue" })).toHaveAttribute("aria-current", "page");
});

test("fetch from the top bar opens the fetch route", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("textbox", { name: "Video or playlist URL" }).fill("https://youtu.be/a");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page).toHaveURL(/#\/fetch\/https%3A%2F%2Fyoutu\.be%2Fa$/);
});
