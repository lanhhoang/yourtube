import { expect, test } from "vitest";
import { formatSize, libraryItems, qualityLabel } from "../src/lib/library.ts";
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
