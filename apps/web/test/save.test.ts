import { expect, test, vi } from "vitest";
import { fetchBlob, fileName, SHARE_LIMIT_BYTES, saveMode } from "../src/lib/save.ts";

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

test("fetchBlob reassembles a folded multi-chunk body and reports progress", async () => {
  const chunk = new Uint8Array(10 * 1024 * 1024).fill(7);
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      for (let i = 0; i < 4; i++) c.enqueue(chunk);
      c.close();
    },
  });
  const res = new Response(body, {
    headers: { "Content-Length": String(chunk.length * 4), "Content-Type": "video/mp4" },
  });
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(res);
  const seen: number[] = [];
  const blob = await fetchBlob("/x", (f) => seen.push(f), new AbortController().signal);
  spy.mockRestore();
  expect(blob.size).toBe(chunk.length * 4);
  expect(blob.type).toBe("video/mp4");
  expect(seen.at(-1)).toBe(1);
});
