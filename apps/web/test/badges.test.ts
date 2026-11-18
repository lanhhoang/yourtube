import { expect, test } from "vitest";
import type { components } from "../src/lib/api.gen.ts";
import { badgeFor } from "../src/lib/badges.ts";
import type { EntryState, Override } from "../src/lib/playlist.ts";

type Details = components["schemas"]["VideoDetails"];

const details = (
  best: number | null,
  size: { width: number | null; height: number } = { width: 2560, height: 1440 },
): Details => ({
  url: "u",
  title: "t",
  uploader: null,
  duration: null,
  thumbnail: null,
  picker: {
    video_streams: [
      {
        format_id: "v1440",
        ext: "mp4",
        resolution: null,
        height: size.height,
        width: size.width,
        vcodec: "a",
        acodec: null,
        abr: null,
        audio_channels: null,
        container: null,
        dynamic_range: null,
      },
    ],
    audio_streams: [],
    has_muxed_streams: false,
    expected_container_by_pair: {},
  },
  best_short_side: best,
  playlist_url: null,
});

const entry = { index: 0, url: "u", title: "t", uploader: null, duration: null, thumbnail: null };

const okEntry = (best: number): EntryState => ({
  entry,
  selected: true,
  check: { ok: true, details: details(best) },
  override: null,
});
const checkingEntry = (): EntryState => ({
  entry,
  selected: true,
  check: "checking",
  override: null,
});
const failedEntry = (message: string): EntryState => ({
  entry,
  selected: false,
  check: { ok: false, message },
  override: null,
});
const customEntry = (o: {
  videoShortSide?: number;
  audioOnly?: boolean;
  none?: boolean;
}): EntryState => {
  const override: Override = {
    selection: o.audioOnly
      ? { videoId: null, audioId: "a1" }
      : o.none
        ? { videoId: null, audioId: null }
        : { videoId: "v1440", audioId: null },
    subtitles: false,
    outputTemplate: "",
    audioBitrate: "",
  };
  return { ...okEntry(1440), override };
};

test("below the cap", () => {
  expect(badgeFor(okEntry(720), "1080")).toEqual({ kind: "below", label: "720p max" });
});
test("at the cap, none", () => {
  expect(badgeFor(okEntry(1080), "1080")).toBeNull();
});
test("best has no cap, none", () => {
  expect(badgeFor(okEntry(720), "best")).toBeNull();
});
test("not checked yet, none", () => {
  expect(badgeFor(checkingEntry(), "1080")).toBeNull();
});
test("custom video uses the short side", () => {
  expect(badgeFor(customEntry({ videoShortSide: 1440 }), "1080")).toEqual({
    kind: "custom",
    label: "1440p · custom",
  });
});
test("custom audio", () => {
  expect(badgeFor(customEntry({ audioOnly: true }), "1080")).toEqual({
    kind: "custom",
    label: "audio · custom",
  });
});
test("custom without exact ids uses the cap label", () => {
  expect(badgeFor(customEntry({ none: true }), "720")).toEqual({
    kind: "custom",
    label: "Up to 720p · custom",
  });
});
test("unavailable wins", () => {
  expect(badgeFor(failedEntry("Video unavailable"), "1080")).toEqual({
    kind: "unavailable",
    label: "Unavailable",
    message: "Video unavailable",
  });
});

test("custom vertical video uses the short side", () => {
  const e: EntryState = {
    ...customEntry({ videoShortSide: 1080 }),
    check: { ok: true, details: details(1080, { width: 1080, height: 1920 }) },
  };
  expect(badgeFor(e, "720")?.label).toBe("1080p · custom");
});
test("custom video without a width uses the height", () => {
  const e: EntryState = {
    ...customEntry({ videoShortSide: 1440 }),
    check: { ok: true, details: details(1440, { width: null, height: 1440 }) },
  };
  expect(badgeFor(e, "720")?.label).toBe("1440p · custom");
});
