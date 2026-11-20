import { expect, test } from "@playwright/test";
import { APP } from "./app.ts";

test("cancel in queue", async ({ page }) => {
  await page.goto(`${APP}#/queue`);
  const row = page.getByRole("listitem").filter({ hasText: "Slow video" });
  await row.getByRole("button", { name: "Cancel" }).click();
  await expect(row).toHaveCount(0);
});

test("toasts for a failed single job and a settled batch", async ({ page }) => {
  let polls = 0;
  const job = {
    id: 9101,
    url: "https://e2e.test/failed",
    title: "Broken video",
    uploader: null,
    duration: null,
    thumbnail: null,
    status: "error",
    progress: 0,
    quality_cap: null,
    hdr: false,
    error_code: "x",
    error_message: "Nope",
    media_kind: "video",
    file_size: null,
    media_format: null,
    resolution_height: null,
    batch_id: null,
    created_at: "2026-11-18T00:00:00",
    finished_at: "2026-11-18T00:00:01",
  };
  const batch = {
    batch_id: "e2e-batch",
    name: "E2E mix",
    done: 2,
    failed: 0,
    cancelled: 0,
    finished_at: "2026-11-18T00:00:02",
  };
  await page.route("**/api/queue", (route) => {
    polls += 1;
    return route.fulfill({
      json: {
        active: [],
        failed: polls === 1 ? [] : [job],
        completed: [],
        batches: polls === 1 ? [] : [batch],
      },
    });
  });
  await page.goto(`${APP}#/`);
  await expect(page.getByText("Download failed")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Broken video: Nope")).toBeVisible();
  await expect(page.getByText("E2E mix")).toBeVisible();
  await expect(page.getByText("2 downloaded")).toBeVisible();
});
