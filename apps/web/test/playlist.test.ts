import { expect, test } from "vitest";
import type { components } from "../src/lib/api.gen.ts";
import {
  addState,
  applyResult,
  buildJobs,
  type EntryState,
  type Header,
  initialEntries,
  selectAll,
  setOverride,
  setSelected,
} from "../src/lib/playlist.ts";

type Details = components["schemas"]["VideoDetails"];
type Entry = components["schemas"]["SourceEntry"];

const base: Entry = {
  index: 0,
  url: "https://e/0",
  title: "E0",
  uploader: "U",
  duration: 5,
  thumbnail: "t0",
};
const details = (over: Partial<Details> = {}): Details => ({
  url: "https://e/canon",
  title: "D",
  uploader: null,
  duration: null,
  thumbnail: null,
  picker: {
    video_streams: [],
    audio_streams: [],
    has_muxed_streams: false,
    expected_container_by_pair: {},
  },
  best_short_side: 720,
  playlist_url: null,
  ...over,
});

const ok = (): EntryState => ({
  entry: base,
  selected: true,
  check: { ok: true, details: details() },
  override: null,
});
const checking = (): EntryState => ({
  entry: base,
  selected: true,
  check: "checking",
  override: null,
});
const idle = (): EntryState => ({ entry: base, selected: false, check: "idle", override: null });
const failed = (): EntryState => ({
  entry: base,
  selected: false,
  check: { ok: false, message: "x" },
  override: null,
});
const header: Header = { cap: "1080", subtitles: true, outputTemplate: "  ", audioBitrate: "" };

test("initialEntries: error entry is unavailable and deselected", () => {
  const r = initialEntries({
    kind: "list",
    title: null,
    video: null,
    skipped: 0,
    entries: [base, { ...base, index: 1, error_code: "c", error_message: "bad" }],
  });
  expect(r[1]).toMatchObject({ selected: false, check: { ok: false, message: "bad" } });
  expect(r[0]).toMatchObject({ selected: true, check: "checking" });
});

test("initialEntries: entry with details starts checked", () => {
  const r = initialEntries({
    kind: "list",
    title: null,
    video: null,
    skipped: 0,
    entries: [{ ...base, details: details() }],
  });
  expect(r[0]).toMatchObject({ selected: true, check: { ok: true } });
});

test("unavailable can't be selected", () => {
  expect(setSelected([failed()], 0, true)[0].selected).toBe(false);
  expect(selectAll([failed(), idle()], true).map((e) => e.selected)).toEqual([false, true]);
});

test("selecting and deselecting moves the check state", () => {
  expect(setSelected([idle()], 0, true)[0].check).toBe("checking");
  expect(setSelected([checking()], 0, false)[0].check).toBe("idle");
  expect(setSelected([ok()], 0, false)[0].check).toMatchObject({ ok: true });
});

test("applyResult: failure deselects", () => {
  const r = applyResult([checking()], 0, { ok: false, message: "x" })[0];
  expect(r.selected).toBe(false);
  expect(r.check).toEqual({ ok: false, message: "x" });
});

test("applyResult: ok is stored even when deselected", () => {
  const r = applyResult([idle()], 0, { ok: true, details: details() })[0];
  expect(r.selected).toBe(false);
  expect(r.check).toMatchObject({ ok: true });
});

test("addState", () => {
  expect(addState([checking(), ok()])).toEqual({ kind: "checking", done: 1, total: 2 });
  expect(addState([ok(), ok(), failed()])).toEqual({ kind: "ready", count: 2 });
  expect(addState([idle(), failed()])).toEqual({ kind: "empty" });
});

test("buildJobs", () => {
  const custom = setOverride([ok()], 0, {
    selection: { videoId: "137", audioId: "140" },
    subtitles: false,
    outputTemplate: "%(title)s",
    audioBitrate: "",
  })[0];
  const plain = { ...ok(), entry: { ...base, index: 1, url: "https://e/1" } };
  const off = { ...ok(), selected: false };
  const jobs = buildJobs([custom, plain, off], header);
  expect(jobs).toEqual([
    expect.objectContaining({
      url: "https://e/canon",
      title: "D",
      uploader: "U",
      duration: 5,
      thumbnail: "t0",
      video_format_id: "137",
      audio_format_id: "140",
      output_template: "%(title)s",
      subtitles: false,
      quality_cap: "1080",
    }),
    expect.objectContaining({
      video_format_id: null,
      audio_format_id: null,
      subtitles: true,
      output_template: null,
      audio_bitrate: null,
      quality_cap: "1080",
    }),
  ]);
});
