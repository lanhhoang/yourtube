import { expect, test } from "vitest";
import { formatSize, libraryItems, qualityLabel, watchMeta } from "../src/lib/library.ts";
import type { JobOut } from "../src/lib/queue.ts";

const job = (id: number, f: Partial<JobOut> = {}) =>
  ({ id, media_kind: "video", resolution_height: null, ...f }) as JobOut;

test("libraryItems per chip", () => {
  const d1 = job(1);
  const a1 = job(2);
  expect(libraryItems([d1], [a1], "all").map((j) => j.id)).toEqual([2, 1]);
  expect(libraryItems([d1], [a1], "downloading")).toEqual([a1]);
  const video = job(3);
  const audio = job(4, { media_kind: "audio" });
  expect(libraryItems([video, audio], [], "audio")).toEqual([audio]);
  expect(libraryItems([video, audio], [], "video")).toEqual([video]);
  expect(libraryItems([video], [audio], "audio")).toEqual([audio]);
});

test("qualityLabel", () => {
  expect(qualityLabel(job(1, { resolution_height: 1080 }))).toBe("1080p");
  expect(qualityLabel(job(2, { media_kind: "audio" }))).toBe("Audio");
  expect(qualityLabel(job(3))).toBe("");
});

test("formatSize", () => {
  expect(formatSize(null)).toBe("");
  expect(formatSize(512)).toBe("512 B");
  expect(formatSize(1536)).toBe("1.5 KB");
  expect(formatSize(5 * 1024 ** 2)).toBe("5.0 MB");
  expect(formatSize(5 * 1024 ** 3)).toBe("5.0 GB");
});

test("libraryItems drops an active job that is already done", () => {
  const finished = job(5, { status: "done" });
  const stale = job(5, { status: "active" });
  expect(libraryItems([finished], [stale], "all")).toEqual([finished]);
  expect(libraryItems([finished], [stale], "video")).toEqual([finished]);
});

test("watchMeta", () => {
  const v = {
    uploader: "Chan",
    media_kind: "video",
    resolution_height: 1080,
    dynamic_range: "SDR",
    file_size: 300 * 1024 ** 2,
    vcodec: "av01.0.08M.08",
    acodec: "mp4a.40.2",
    media_format: "mp4",
  } as JobOut;
  expect(watchMeta(v)).toBe("Chan · 1080p · SDR · 300.0 MB · av1 · aac · mp4");
  expect(watchMeta({ ...v, dynamic_range: "HDR10", resolution_height: 2160 })).toContain(
    "2160p · HDR10",
  );
  const a = {
    ...v,
    media_kind: "audio",
    resolution_height: null,
    dynamic_range: null,
    vcodec: null,
    acodec: "opus",
    media_format: "webm",
  } as JobOut;
  expect(watchMeta(a)).toBe("Chan · Audio · 300.0 MB · opus · webm");
  expect(watchMeta({ ...v, vcodec: null, acodec: null, dynamic_range: null })).toBe(
    "Chan · 1080p · 300.0 MB · mp4",
  );
});
