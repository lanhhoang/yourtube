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

const failedJob = (id: number, title: string) => ({
  id,
  url: `https://e2e.test/failed-${id}`,
  title,
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
});

test("dismiss all clears failed downloads", async ({ page }) => {
  let dismissed = false;
  await page.route("**/api/queue/dismiss-failed", (route) => {
    dismissed = true;
    return route.fulfill({ json: { dismissed: 2 } });
  });
  await page.route("**/api/queue", (route) =>
    route.fulfill({
      json: {
        active: [],
        failed: dismissed ? [] : [failedJob(9201, "Broken one"), failedJob(9202, "Broken two")],
        completed: [],
        batches: [],
      },
    }),
  );
  await page.goto(`${APP}#/queue`);
  const rows = page.getByRole("main").getByRole("listitem");
  await expect(rows.filter({ hasText: "Broken one" })).toHaveCount(1);
  await expect(rows.filter({ hasText: "Broken two" })).toHaveCount(1);
  await page.getByRole("button", { name: "Dismiss all" }).click();
  await expect(rows.filter({ hasText: "Broken one" })).toHaveCount(0);
  await expect(rows.filter({ hasText: "Broken two" })).toHaveCount(0);
});

test("dismiss all is hidden for one failure", async ({ page }) => {
  await page.route("**/api/queue", (route) =>
    route.fulfill({
      json: { active: [], failed: [failedJob(9203, "Lonely failure")], completed: [], batches: [] },
    }),
  );
  await page.goto(`${APP}#/queue`);
  await expect(
    page.getByRole("main").getByRole("listitem").filter({ hasText: "Lonely failure" }),
  ).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Dismiss all" })).toHaveCount(0);
});
