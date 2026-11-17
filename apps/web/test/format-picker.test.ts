import { expect, test } from "vitest";
import type { components } from "../src/lib/api.gen.ts";
import { expectedContainer, hasExact, toggle } from "../src/lib/format-picker.ts";

const picker = {
  video_streams: [],
  audio_streams: [],
  has_muxed_streams: false,
  expected_container_by_pair: { "137|140": "mp4", "|": "unknown" },
} as components["schemas"]["StreamPicker"];

test("toggle selects, switches and clears", () => {
  expect(toggle({ videoId: null, audioId: null }, "video", "137")).toEqual({
    videoId: "137",
    audioId: null,
  });
  expect(toggle({ videoId: "137", audioId: "140" }, "video", "299")).toEqual({
    videoId: "299",
    audioId: "140",
  });
  expect(toggle({ videoId: "137", audioId: null }, "video", "137")).toEqual({
    videoId: null,
    audioId: null,
  });
  expect(toggle({ videoId: null, audioId: "140" }, "audio", "140")).toEqual({
    videoId: null,
    audioId: null,
  });
});

test("expectedContainer", () => {
  expect(expectedContainer(picker, { videoId: "137", audioId: "140" })).toBe("mp4");
  expect(expectedContainer(picker, { videoId: "zzz", audioId: null })).toBe("unknown");
});

test("hasExact", () => {
  expect(hasExact({ videoId: null, audioId: null })).toBe(false);
  expect(hasExact({ videoId: null, audioId: "140" })).toBe(true);
});
