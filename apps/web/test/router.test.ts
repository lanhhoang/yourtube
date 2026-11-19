import { expect, test } from "vitest";
import { href, parseHash, section } from "../src/lib/router.ts";

const urls = "https://youtu.be/a https://www.youtube.com/watch?v=b&list=c";

test("parses simple routes", () => {
  expect(parseHash("")).toEqual({ name: "library" });
  expect(parseHash("#/")).toEqual({ name: "library" });
  expect(parseHash("#/queue")).toEqual({ name: "queue" });
  expect(parseHash("#/settings")).toEqual({ name: "settings" });
  expect(parseHash("#/nope")).toEqual({ name: "library" });
});

test("fetch route round-trips urls", () => {
  expect(parseHash(href({ name: "fetch", urls }))).toEqual({ name: "fetch", urls });
});

test("bad encoding falls back to library", () => {
  expect(parseHash("#/fetch/%E0%A4%A")).toEqual({ name: "library" });
  expect(parseHash("#/fetch/")).toEqual({ name: "library" });
  expect(parseHash("#/queue/extra")).toEqual({ name: "library" });
});

test("section maps routes to rail links", () => {
  expect(section({ name: "fetch", urls })).toBeNull();
  expect(section({ name: "queue" })).toBe("queue");
  expect(section({ name: "library" })).toBe("library");
});

test("watch route", () => {
  expect(parseHash("#/watch/12")).toEqual({ name: "watch", id: 12 });
  expect(parseHash("#/watch/x")).toEqual({ name: "library" });
  expect(parseHash("#/watch/")).toEqual({ name: "library" });
  expect(parseHash("#/watch/1.5")).toEqual({ name: "library" });
  expect(href({ name: "watch", id: 12 })).toBe("#/watch/12");
  expect(section({ name: "watch", id: 12 })).toBe("library");
});
