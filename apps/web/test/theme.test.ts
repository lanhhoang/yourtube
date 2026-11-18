import { expect, test } from "vitest";
import { isDark, nextTheme, readTheme, themeLabel } from "../src/lib/theme.ts";

test("readTheme defaults to dark", () => {
  expect(readTheme(null)).toBe("dark");
  expect(readTheme("light")).toBe("light");
  expect(readTheme("system")).toBe("system");
  expect(readTheme("x")).toBe("dark");
});

test("isDark", () => {
  expect(isDark("system", true)).toBe(true);
  expect(isDark("system", false)).toBe(false);
  expect(isDark("light", true)).toBe(false);
  expect(isDark("dark", false)).toBe(true);
});

test("nextTheme cycles", () => {
  expect(nextTheme("dark")).toBe("light");
  expect(nextTheme("light")).toBe("system");
  expect(nextTheme("system")).toBe("dark");
});

test("themeLabel names current and next", () => {
  expect(themeLabel("dark")).toBe("Theme: Dark. Switch to Light");
  expect(themeLabel("light")).toBe("Theme: Light. Switch to System");
  expect(themeLabel("system")).toBe("Theme: System. Switch to Dark");
});
