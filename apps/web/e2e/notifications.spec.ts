import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

// Settings state lives in localStorage so the fake subscription survives a reload.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    const KEY = "e2e-push-sub";
    Object.defineProperty(Notification, "permission", { get: () => "default", configurable: true });
    Notification.requestPermission = () => Promise.resolve("granted");
    const make = () => {
      const endpoint = "https://push.example.test/e2e-notifications";
      return {
        endpoint,
        toJSON: () => ({ endpoint, keys: { p256dh: "BPkey", auth: "authkey" } }),
        unsubscribe: () => {
          localStorage.removeItem(KEY);
          return Promise.resolve(true);
        },
      };
    };
    PushManager.prototype.subscribe = () => {
      localStorage.setItem(KEY, "1");
      return Promise.resolve(make() as unknown as PushSubscription);
    };
    PushManager.prototype.getSubscription = () =>
      Promise.resolve(localStorage.getItem(KEY) ? (make() as unknown as PushSubscription) : null);
  });
});

test("turn notifications on and off for this device", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  const toggle = page.getByRole("switch", { name: "Notifications on this device", exact: true });
  await expect(toggle).toBeEnabled();
  await expect(toggle).not.toBeChecked();

  const posted = page.waitForResponse(
    (r) => r.url().endsWith("/api/push/subscriptions") && r.request().method() === "POST",
  );
  await toggle.check();
  expect((await posted).status()).toBe(204);
  await expect(toggle).toBeChecked();

  await page.reload();
  await expect(
    page.getByRole("switch", { name: "Notifications on this device", exact: true }),
  ).toBeChecked();

  const deleted = page.waitForResponse(
    (r) => r.url().endsWith("/api/push/subscriptions") && r.request().method() === "DELETE",
  );
  await page.getByRole("switch", { name: "Notifications on this device", exact: true }).uncheck();
  expect((await deleted).status()).toBe(204);
  await expect(
    page.getByRole("switch", { name: "Notifications on this device", exact: true }),
  ).not.toBeChecked();
});

test.describe("iPhone, not installed", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    viewport: { width: 390, height: 844 },
    hasTouch: true,
  });

  test("asks to add to the Home Screen first", async ({ page }) => {
    await page.goto(`${APP}#/settings`);
    await expect(page.getByText("Add YourTube to your Home Screen first.")).toBeVisible();
    await expect(
      page.getByRole("switch", { name: "Notifications on this device", exact: true }),
    ).toBeDisabled();
  });
});
