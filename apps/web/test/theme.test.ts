import { expect, test } from "vitest";
import { isDark, readTheme } from "../src/lib/theme.ts";

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
