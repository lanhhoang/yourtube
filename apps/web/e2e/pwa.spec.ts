import { expect, test } from "@playwright/test";

test("manifest is served", async ({ request }) => {
  const res = await request.get("/manifest.webmanifest");
  const manifest = await res.json();
  expect(manifest.name).toBe("YourTube");
  expect(manifest.share_target.action).toBe("/");
});

test("a shared link opens the fetch route and leaves the URL", async ({ page }) => {
  await page.goto("/?share=https%3A%2F%2Fe2e.test%2Fvideo");
  await expect(page).toHaveURL(/\/#\/fetch\/https%3A%2F%2Fe2e\.test%2Fvideo$/);
  await expect(page.getByRole("heading", { name: "E2E Video" })).toBeVisible();
});

test("the service worker controls the page and leaves the API alone", async ({ page }) => {
  await page.goto("/#/");
  expect(await page.evaluate(() => navigator.serviceWorker.ready.then((r) => !!r.active))).toBe(
    true,
  );
  await page.reload();
  expect(await page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  const res = await page.goto("/api/queue");
  expect(res?.headers()["content-type"]).toContain("application/json");
});
