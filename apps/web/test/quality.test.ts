import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { CAP_OPTIONS, DEFAULT_CAP, isBelowCap, type QualityCap } from "../src/lib/quality.ts";

// tsconfig.node.json has no resolveJsonModule, so read the shared fixture from disk.
const cases = JSON.parse(
  readFileSync(new URL("../../server/tests/fixtures/quality_cases.json", import.meta.url), "utf8"),
) as { name: string; cap: QualityCap; best_short_side: number | null; below_cap: boolean }[];

for (const c of cases) {
  test(c.name, () => expect(isBelowCap(c.cap, c.best_short_side)).toBe(c.below_cap));
}

test("cap options", () => {
  expect(DEFAULT_CAP).toBe("1080");
  expect(CAP_OPTIONS.map((o) => o.value)).toEqual([
    "best",
    "2160",
    "1440",
    "1080",
    "720",
    "480",
    "audio",
  ]);
  expect(CAP_OPTIONS.find((o) => o.value === "1080")?.label).toBe("Up to 1080p");
});
