import { expect, test } from "vitest";
import {
  DEFAULT_VIEW,
  SORT_OPTIONS,
  activeFilterCount,
  bulkResultText,
  dropStale,
  facets,
  filterItems,
  formatSize,
  qualityLabel,
  readView,
  sameFilters,
  sortItems,
  toggle,
  watchMeta,
} from "../src/lib/library.ts";
import type { JobOut } from "../src/lib/queue.ts";

const job = (id: number, f: Partial<JobOut> = {}) =>
  ({ id, media_kind: "video", resolution_height: null, ...f }) as JobOut;

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

test("toggle adds, then removes, and never mutates", () => {
  const start = new Set([1]);
  const added = toggle(start, 2);
  expect([...added]).toEqual([1, 2]);
  expect([...start]).toEqual([1]);
  expect([...toggle(added, 1)]).toEqual([2]);
  expect([...added]).toEqual([1, 2]);
});

test("bulkResultText", () => {
  expect(bulkResultText(3, 0)).toBe("Deleted 3");
  expect(bulkResultText(2, 1)).toBe("Deleted 2, 1 failed");
  expect(bulkResultText(0, 2)).toBe("Couldn't delete 2");
});

const ids = (xs: JobOut[]) => xs.map((x) => x.id);

test("sortItems", () => {
  expect(SORT_OPTIONS.map((o) => o.label)).toEqual([
    "Newest first",
    "Oldest first",
    "Title A–Z",
    "Longest first",
    "Largest first",
  ]);
  const a = job(1, {
    finished_at: "2026-01-02T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    title: "b2",
    duration: 10,
    file_size: null,
  });
  const b = job(2, {
    finished_at: null,
    created_at: "2026-01-03T00:00:00Z",
    title: null,
    duration: null,
    file_size: 5,
  });
  const c = job(3, {
    finished_at: "2026-01-01T12:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    title: "B10",
    duration: 10,
    file_size: 9,
  });
  const items = [a, b, c];
  expect(ids(sortItems(items, "added-desc"))).toEqual([2, 1, 3]);
  expect(ids(sortItems(items, "added-asc"))).toEqual([3, 1, 2]);
  expect(ids(sortItems(items, "title"))).toEqual([1, 3, 2]);
  expect(ids(sortItems(items, "duration"))).toEqual([1, 3, 2]);
  expect(ids(sortItems(items, "size"))).toEqual([3, 2, 1]);
  expect(ids(items)).toEqual([1, 2, 3]);
});

test("filterItems ANDs and is strict", () => {
  const items = [
    job(1, { uploader: "A", playlist_title: "P", media_kind: "audio" }),
    job(2, { uploader: "A", playlist_title: "P" }),
    job(3, { uploader: "B", playlist_title: "P", media_kind: "audio" }),
  ];
  const v = { ...DEFAULT_VIEW, kind: "audio" as const, channel: "A", playlist: "P" };
  expect(ids(filterItems(items, v))).toEqual([1]);
  expect(filterItems(items, { ...DEFAULT_VIEW, channel: "Z" })).toEqual([]);
  expect(ids(filterItems(items, DEFAULT_VIEW))).toEqual([1, 2, 3]);
});

test("facets", () => {
  const f = facets([
    job(1, { uploader: "b", playlist_title: "" }),
    job(2, { uploader: "a", playlist_title: "P" }),
    job(3, { uploader: "b", playlist_title: null }),
    job(4, { uploader: null }),
  ]);
  expect(f.channels).toEqual([
    { value: "a", count: 1 },
    { value: "b", count: 2 },
  ]);
  expect(f.playlists).toEqual([{ value: "P", count: 1 }]);
});

test("dropStale", () => {
  const f = { channels: [{ value: "a", count: 1 }], playlists: [{ value: "P", count: 1 }] };
  expect(dropStale({ ...DEFAULT_VIEW, channel: "x", playlist: "y" }, f)).toEqual(DEFAULT_VIEW);
  const ok = { ...DEFAULT_VIEW, channel: "a", playlist: "P" };
  expect(dropStale(ok, f)).toBe(ok);
});

test("activeFilterCount and sameFilters", () => {
  expect(activeFilterCount(DEFAULT_VIEW)).toBe(0);
  expect(activeFilterCount({ ...DEFAULT_VIEW, kind: "video", channel: "a", playlist: "P" })).toBe(
    3,
  );
  expect(sameFilters(DEFAULT_VIEW, { ...DEFAULT_VIEW, sort: "title" })).toBe(true);
  expect(sameFilters(DEFAULT_VIEW, { ...DEFAULT_VIEW, kind: "audio" })).toBe(false);
});

test("readView", () => {
  expect(readView(null)).toEqual(DEFAULT_VIEW);
  expect(readView("{bad")).toEqual(DEFAULT_VIEW);
  expect(readView('{"sort":"nope","kind":"audio"}')).toEqual({ ...DEFAULT_VIEW, kind: "audio" });
  expect(readView('{"channel":""}')).toEqual(DEFAULT_VIEW);
  expect(readView('{"channel":"a","playlist":"P","sort":"size"}')).toEqual({
    sort: "size",
    kind: "any",
    channel: "a",
    playlist: "P",
  });
});
