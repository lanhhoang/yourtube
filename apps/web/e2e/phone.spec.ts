import { expect, type Page, test } from "@playwright/test";
import { APP } from "./app.ts";
import { expectNoSideScroll, expectTarget } from "./phone-helpers.ts";

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

test("tab bar navigates and the rail is hidden", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Tabs" })).toBeVisible();
  await page.getByRole("link", { name: "Queue" }).tap();
  await expect(page).toHaveURL(/#\/queue$/);
  await expect(page.getByRole("link", { name: "Queue" })).toHaveAttribute("aria-current", "page");
});

test("no sideways scroll on library, queue and settings", async ({ page }) => {
  for (const [hash, heading] of [
    ["#/", "Library"],
    ["#/queue", "Queue"],
    ["#/settings", "Settings"],
  ] as const) {
    await page.goto(`${APP}${hash}`);
    if (hash !== "#/")
      await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await expectNoSideScroll(page);
  }
});

test("shell targets are at least 44 px", async ({ page }) => {
  await page.goto(`${APP}#/`);
  for (const name of ["Library", "Queue", "Settings"]) {
    await expectTarget(page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name }));
  }
  await expectTarget(page.getByRole("button", { name: "Fetch", exact: true }));
  await expectTarget(page.getByRole("button", { name: "Fetch options" }));
});

test("theme tile is hidden; Settings has the theme radios; field is 16 px", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.getByRole("button", { name: /^Theme: / })).toBeHidden();
  for (const name of ["Dark", "Light", "System"]) {
    await expect(page.getByRole("radio", { name })).toBeVisible();
  }
  const size = await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .evaluate((el) => Number.parseFloat(getComputedStyle(el).fontSize));
  expect(size).toBeGreaterThanOrEqual(16);
});

test("toast sits at the top, under the top bar", async ({ page }) => {
  let polls = 0;
  const job = {
    id: 9001,
    url: "https://e2e.test/toast",
    title: "Phone toast",
    uploader: null,
    duration: null,
    thumbnail: null,
    status: "done",
    progress: 100,
    quality_cap: null,
    hdr: false,
    error_code: null,
    error_message: null,
    media_kind: "video",
    file_size: 4,
    media_format: "mp4",
    resolution_height: 1080,
    batch_id: null,
    created_at: "2026-11-18T00:00:00",
    finished_at: "2026-11-18T00:00:01",
  };
  await page.route("**/api/queue", (route) => {
    polls += 1;
    return route.fulfill({
      json: { active: [], failed: [], completed: polls === 1 ? [] : [job], batches: [] },
    });
  });
  await page.goto(`${APP}#/`);
  const toast = page.getByText("Phone toast");
  await expect(toast).toBeVisible({ timeout: 10_000 });
  const box = await toast.boundingBox();
  const header = await page.locator("header").first().boundingBox();
  expect(box?.y ?? 999).toBeGreaterThanOrEqual((header?.y ?? 0) + (header?.height ?? 999) - 1);
  expect(box?.y ?? 999).toBeLessThan(120);
});

test("library: no sideways scroll, tap opens the player", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const link = page.getByRole("link", { name: "Phone video" });
  await expect(link).toBeVisible();
  await expectNoSideScroll(page);
  // Row layout: the thumbnail box sits left of the title, not above it.
  const card = page.getByRole("article").filter({ hasText: "Phone video" });
  const thumb = await card.locator("div").first().boundingBox();
  const title = await link.boundingBox();
  expect((title?.x ?? 0) >= (thumb?.x ?? 0) + (thumb?.width ?? 0)).toBe(true);
  await link.tap();
  await expect(page).toHaveURL(/#\/watch\/\d+$/);
});

test("select mode on phone", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page.getByRole("button", { name: "Select", exact: true }).tap();
  const box = page.getByRole("checkbox", { name: "Phone video" });
  await expect(box).toBeVisible();
  await expectTarget(box.locator("xpath=.."));
  const bar = page.getByRole("region", { name: "Selection" });
  for (const b of await bar.getByRole("button").all()) await expectTarget(b);
  await page.getByRole("article").filter({ hasText: "Phone video" }).tap();
  await expect(page.getByText("1 selected")).toBeVisible();
  await expect(page).toHaveURL(/#\/$/);
  const barBox = await bar.boundingBox();
  const tabBox = await page.locator("nav").last().boundingBox();
  expect(
    Math.abs((barBox?.y ?? 0) + (barBox?.height ?? 0) - (tabBox?.y ?? -99)),
  ).toBeLessThanOrEqual(1);
  await expectNoSideScroll(page);
});

test("queue: no sideways scroll, Cancel is a 44 px target", async ({ page, request }) => {
  const res = await request.post("/api/downloads", {
    data: { jobs: [{ url: "https://e2e.test/slow-phone", title: "Phone queued job" }] },
  });
  expect(res.status()).toBe(201);
  await page.goto(`${APP}#/queue`);
  const row = page.getByRole("listitem").filter({ hasText: "Phone queued job" });
  await expect(row).toBeVisible();
  await expectNoSideScroll(page);
  const cancel = row.getByRole("button", { name: "Cancel" });
  await expectTarget(cancel);
  await cancel.tap();
  await expect(row).toHaveCount(0);
});

test("settings: no sideways scroll, inputs fit, buttons are 44 px", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  await expect(page.getByLabel("Proxy URL")).toBeVisible();
  await expectNoSideScroll(page);
  for (const box of await page.locator("main input:not([type=radio])").all()) {
    const b = await box.boundingBox();
    expect((b?.x ?? 0) + (b?.width ?? 0)).toBeLessThanOrEqual(390);
  }
  await expectTarget(page.getByRole("button", { name: "Save" }));
});

async function watchPage(page: Page) {
  await page.goto(`${APP}#/`);
  await page.getByRole("link", { name: "Phone video" }).tap();
}

test("watch: player fits, Save and Delete are 44 px", async ({ page }) => {
  // Share mode: touch makes the browser report file sharing, so Save is a button.
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "canShare", { value: () => true, configurable: true }),
  );
  await watchPage(page);
  const video = page.locator("video");
  await expect(video).toBeVisible();
  expect((await video.boundingBox())?.width ?? 999).toBeLessThanOrEqual(390);
  await expectTarget(page.getByRole("button", { name: "Save", exact: true }));
  await expectTarget(page.getByRole("button", { name: "Delete" }));
  await expectNoSideScroll(page);
});

test("watch: Save as a download link is a 44 px target too", async ({ page }) => {
  // Browsers without file sharing (and CI's Chromium) show Save as a link.
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "canShare", { value: undefined }),
  );
  await watchPage(page);
  await expectTarget(page.getByRole("link", { name: "Save", exact: true }));
});

test("fetch video: no sideways scroll, Add to queue queues the job", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/v/phone");
  await page.getByRole("button", { name: "Fetch", exact: true }).tap();
  await expect(page.getByRole("heading", { name: "Video Phone" })).toBeVisible();
  await expectNoSideScroll(page);
  const add = page.getByRole("button", { name: "Add to queue" });
  await expectTarget(add);
  await add.tap();
  await expect(page.getByText("Added to queue.")).toBeVisible();
});

async function openPlaylist(page: Page) {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/playlist");
  await page.getByRole("button", { name: "Fetch", exact: true }).click();
  await expect(page.getByRole("heading", { name: "E2E Playlist" })).toBeVisible();
}

test("playlist: no sideways scroll, override opens as a bottom sheet", async ({ page }) => {
  await openPlaylist(page);
  await expectNoSideScroll(page);
  const opener = page.getByRole("button", { name: "Video A: customise" });
  // The checkbox is wrapped in a label that carries the 44 px hit area.
  await expectTarget(page.getByRole("checkbox", { name: "Select Video A" }).locator(".."));
  await opener.tap();
  const sheet = page.getByRole("dialog", { name: "Video A" });
  await expect(sheet).toBeVisible();
  const box = await sheet.boundingBox();
  expect(Math.round((box?.y ?? 0) + (box?.height ?? 0))).toBe(844);
  expect(box?.height ?? 999).toBeLessThanOrEqual(844 * 0.85 + 1);
  await expectTarget(sheet.getByRole("button", { name: "Close" }));
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  await opener.tap();
  await sheet.getByRole("button", { name: "Close" }).tap();
  await expect(sheet).toBeHidden();
  await opener.tap();
  await expect(sheet).toBeVisible();
  await page.mouse.click(195, 40);
  await expect(sheet).toBeHidden();
});

test("playlist cards are two-up", async ({ page }) => {
  await openPlaylist(page);
  const a = await page.getByRole("article").filter({ hasText: "Video A" }).boundingBox();
  const b = await page.getByRole("article").filter({ hasText: "Video B" }).boundingBox();
  expect(Math.abs((a?.y ?? 0) - (b?.y ?? 99))).toBeLessThan(4);
  expect(b?.x ?? 0).toBeGreaterThan((a?.x ?? 0) + (a?.width ?? 0) - 1);
});

test("top-bar placeholder fits the phone field", async ({ page }) => {
  await page.goto(`${APP}#/`);
  const fits = await page.getByRole("textbox", { name: "Video or playlist URL" }).evaluate((el) => {
    const c = document.createElement("canvas").getContext("2d");
    if (!c) return false;
    c.font = `${getComputedStyle(el).fontSize} ${getComputedStyle(el).fontFamily}`;
    const w = c.measureText((el as HTMLTextAreaElement).placeholder).width;
    const cs = getComputedStyle(el);
    return (
      w <= el.clientWidth - Number.parseFloat(cs.paddingLeft) - Number.parseFloat(cs.paddingRight)
    );
  });
  expect(fits).toBe(true);
});

test("settings theme choice is a full-width row of 44 px targets", async ({ page }) => {
  await page.goto(`${APP}#/settings`);
  const radios = page.getByRole("radiogroup", { name: "Theme (settings)" }).locator("label");
  const boxes = await radios.evaluateAll((els) =>
    els.map((e) => e.getBoundingClientRect().toJSON()),
  );
  expect(new Set(boxes.map((b) => Math.round(b.y))).size).toBe(1);
  for (const b of boxes) expect(b.height).toBeGreaterThanOrEqual(44);
});

test("fetch views: fields are 16 px and tap targets are 44 px", async ({ page }) => {
  await page.goto(`${APP}#/`);
  await page
    .getByRole("textbox", { name: "Video or playlist URL" })
    .fill("https://e2e.test/v/phone");
  await page.getByRole("button", { name: "Fetch", exact: true }).tap();
  await expect(page.getByRole("heading", { name: "Video Phone" })).toBeVisible();
  await page.getByRole("tab", { name: "Advanced" }).tap();
  const small = async (sel: string) =>
    page
      .locator(sel)
      .evaluateAll(
        (els) => els.filter((e) => Number.parseFloat(getComputedStyle(e).fontSize) < 16).length,
      );
  expect(await small("main input:not([type=checkbox]):not([type=radio]), main select")).toBe(0);
  for (const name of ["Video", "Audio", "Advanced"]) {
    await expectTarget(page.getByRole("tab", { name }));
  }
  for (const label of await page.locator("main label:has(input[type=checkbox])").all()) {
    expect((await label.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  for (const row of await page.getByRole("tabpanel").getByRole("button").all()) {
    expect((await row.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
});

test("override sheet: fields are 16 px and targets are 44 px", async ({ page }) => {
  await openPlaylist(page);
  await page.getByRole("button", { name: "Video A: customise" }).tap();
  const sheet = page.getByRole("dialog", { name: "Video A" });
  await sheet.getByRole("button", { name: "Custom" }).tap();
  await expectTarget(sheet.getByRole("button", { name: "Custom" }));
  await expectTarget(sheet.getByRole("button", { name: "Playlist setting" }));
  const small = await sheet
    .locator("input:not([type=checkbox]):not([type=radio]), select")
    .evaluateAll(
      (els) => els.filter((e) => Number.parseFloat(getComputedStyle(e).fontSize) < 16).length,
    );
  expect(small).toBe(0);
  for (const row of await sheet.getByRole("button").all()) {
    expect((await row.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
});

test.describe("desktop width", () => {
  test.use({ viewport: { width: 1440, height: 900 }, hasTouch: false });
  test("playlist override stays a side panel", async ({ page }) => {
    await openPlaylist(page);
    await page.getByRole("button", { name: "Video A: customise" }).click();
    await expect(page.getByRole("complementary", { name: "Settings for Video A" })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
});
