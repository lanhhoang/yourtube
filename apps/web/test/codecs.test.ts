import { expect, test } from "vitest";
import { shortCodec } from "../src/lib/codecs.ts";

test("shortCodec", () => {
  expect(shortCodec("av01.0.08M.08")).toBe("av1");
  expect(shortCodec("avc1.640028")).toBe("h264");
  expect(shortCodec("vp09.00.51.08")).toBe("vp9");
  expect(shortCodec("mp4a.40.2")).toBe("aac");
  expect(shortCodec("hev1.2.4.L153")).toBe("h265");
  expect(shortCodec("opus")).toBe("opus");
  expect(shortCodec("h264")).toBe("h264");
  expect(shortCodec("prores")).toBe("prores");
  expect(shortCodec(null)).toBe("");
});
