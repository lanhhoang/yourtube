import { expect, test } from "vitest";
import { fileName, SHARE_LIMIT_BYTES, saveMode } from "../src/lib/save.ts";

test("saveMode", () => {
  expect(saveMode(10, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES, true)).toBe("share");
  expect(saveMode(SHARE_LIMIT_BYTES + 1, true)).toBe("link");
  expect(saveMode(0, true)).toBe("link");
  expect(saveMode(null, true)).toBe("link");
  expect(saveMode(10, false)).toBe("link");
});

test("fileName", () => {
  expect(fileName("Seeded video", "mp4")).toBe("Seeded video.mp4");
  expect(fileName("a/b: c?", "webm")).toBe("a-b- c-.webm");
  expect(fileName("  ", "mp4")).toBe("download.mp4");
  expect(fileName(null, null)).toBe("download");
});
