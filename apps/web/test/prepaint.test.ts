import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import { isDark, readTheme } from "../src/lib/theme.ts";

const html = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "index.html"),
  "utf8",
);
const inlineScript = html.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";

function runInlineScript(stored: string | null, prefersDark: boolean): boolean {
  const classes = new Set<string>();
  const env = {
    localStorage: { getItem: () => stored },
    matchMedia: () => ({ matches: prefersDark }),
    document: {
      documentElement: {
        classList: {
          toggle: (name: string, on: boolean) => (on ? classes.add(name) : classes.delete(name)),
        },
      },
    },
  };
  new Function("localStorage", "matchMedia", "document", inlineScript)(
    env.localStorage,
    env.matchMedia,
    env.document,
  );
  return classes.has("dark");
}

test("index.html has a pre-paint theme script", () => {
  expect(inlineScript).toContain("localStorage");
});

test.each([null, "system", "light", "dark", "purple"])(
  "pre-paint script matches theme.ts for stored %s",
  (stored) => {
    for (const prefersDark of [true, false]) {
      expect(runInlineScript(stored, prefersDark)).toBe(isDark(readTheme(stored), prefersDark));
    }
  },
);
