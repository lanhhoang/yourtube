import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import type { components } from "../src/lib/api.gen.ts";
import {
  CAP_OPTIONS,
  cappedSide,
  DEFAULT_CAP,
  hdrAtCap,
  hdrSide,
  isBelowCap,
  isHdr,
  type QualityCap,
} from "../src/lib/quality.ts";

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

type Row = components["schemas"]["StreamRow"];
const row = (width: number, height: number, dr?: string): Row => ({
  format_id: `${width}x${height}${dr ?? ""}`,
  ext: "mp4",
  resolution: null,
  width,
  height,
  vcodec: "vp9",
  acodec: null,
  abr: null,
  audio_channels: null,
  container: null,
  dynamic_range: dr ?? null,
});

const S = [row(3840, 2160, "SDR"), row(1920, 1080, "SDR"), row(1920, 1080, "HDR10")];

test("isHdr and hdrSide", () => {
  expect(isHdr(row(1, 1, "SDR"))).toBe(false);
  expect(isHdr(row(1, 1))).toBe(false);
  expect(isHdr(row(1, 1, "HLG"))).toBe(true);
  expect(hdrSide(S)).toBe(1080);
  expect(hdrSide([row(1920, 1080, "SDR")])).toBeNull();
});

test("cappedSide follows res:N", () => {
  expect(cappedSide("best", S)).toBe(2160);
  expect(cappedSide("1440", S)).toBe(1080);
  expect(cappedSide("480", S)).toBe(1080);
  expect(cappedSide("audio", S)).toBeNull();
  expect(cappedSide("best", [])).toBeNull();
});

test("hdrAtCap", () => {
  expect(hdrAtCap("best", S)).toEqual({ kind: "below", side: 1080 });
  expect(hdrAtCap("1440", S)).toEqual({ kind: "yes" });
  expect(hdrAtCap("1080", S)).toEqual({ kind: "yes" });
  expect(hdrAtCap("audio", S)).toEqual({ kind: "none" });
  expect(hdrAtCap("best", [row(1920, 1080, "SDR")])).toEqual({ kind: "none" });
  expect(hdrAtCap("720", [row(1280, 720, "SDR"), row(3840, 2160, "HDR10")])).toEqual({
    kind: "none",
  });
  expect(hdrAtCap("best", [row(1080, 1920, "HLG")])).toEqual({ kind: "yes" });
  expect(hdrAtCap("best", [])).toEqual({ kind: "none" });
});
