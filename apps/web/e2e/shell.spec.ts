import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("rail theme tile cycles, persists and stays in sync with Settings", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Theme: Dark. Switch to Light" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  await page.getByText("System", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  await expect(page.getByRole("button", { name: "Theme: System. Switch to Dark" })).toBeVisible();
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

test("wordmark shows the player mark", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const home = page.getByRole("link", { name: "yourtube", exact: true });
  await expect(home).toHaveAccessibleName("yourtube");
  await expect(home.getByRole("img")).toHaveCount(0);
  const mark = home.locator("svg[aria-hidden='true']");
  await expect(mark).toBeVisible();
  const box = await mark.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(17);
  expect(box?.height).toBeLessThanOrEqual(22);
  expect(box?.width).toBeGreaterThan(box?.height ?? 0);
});

test("system theme follows the OS, before and after a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(`${APP}#/settings`);
  await page.getByText("System", { exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass(/dark/);
});
