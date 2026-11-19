import { expect, type Locator, type Page } from "@playwright/test";

// `main` scrolls on its own (overflow-y-auto), so it clips sideways overflow and
// documentElement alone misses it. Check both.
export async function expectNoSideScroll(page: Page): Promise<void> {
  const m = await page.evaluate(() => {
    const main = document.querySelector("main");
    return {
      doc: document.documentElement.scrollWidth - window.innerWidth,
      main: main ? main.scrollWidth - main.clientWidth : 0,
    };
  });
  expect(m).toEqual({ doc: 0, main: 0 });
}

export async function expectTarget(loc: Locator): Promise<void> {
  const box = await loc.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
}
