import { expect, test, vi } from "vitest";
import type { components } from "../src/lib/api.gen.ts";
import { type CheckResult, createChecker } from "../src/lib/checker.ts";

type Details = components["schemas"]["VideoDetails"];

const details = (url: string): Details => ({
  url,
  title: url,
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
});

function setup() {
  const pending: { url: string; resolve: (d: Details) => void; reject: (e: unknown) => void }[] =
    [];
  const results: [number, CheckResult][] = [];
  const checker = createChecker({
    lookup: (url) =>
      new Promise<Details>((resolve, reject) => {
        pending.push({ url, resolve, reject });
      }),
    onResult: (i, r) => results.push([i, r]),
  });
  return { pending, results, checker };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

test("never runs more than 2 lookups at once", async () => {
  const { pending, checker } = setup();
  for (let i = 0; i < 5; i++) checker.want(i, `u${i}`);
  expect(pending.map((p) => p.url)).toEqual(["u0", "u1"]);
  pending[0].resolve(details("u0"));
  await vi.waitFor(() => expect(pending).toHaveLength(3));
  expect(pending[2].url).toBe("u2");
});

test("does not look up the same index twice", async () => {
  const { pending, results, checker } = setup();
  checker.want(0, "u0");
  checker.want(0, "u0");
  expect(pending).toHaveLength(1);
  pending[0].resolve(details("u0"));
  await vi.waitFor(() => expect(results).toHaveLength(1));
  checker.want(0, "u0");
  await flush();
  expect(pending).toHaveLength(1);
});

test("drop removes a queued index", async () => {
  const { pending, checker } = setup();
  checker.want(0, "u0");
  checker.want(1, "u1");
  checker.want(2, "u2");
  checker.drop(2);
  pending[0].resolve(details("u0"));
  pending[1].resolve(details("u1"));
  await flush();
  expect(pending.map((p) => p.url)).toEqual(["u0", "u1"]);
});

test("a dropped index can be wanted again", async () => {
  const { pending, checker } = setup();
  checker.want(0, "u0");
  checker.want(1, "u1");
  checker.want(2, "u2");
  checker.drop(2);
  checker.want(2, "u2");
  pending[0].resolve(details("u0"));
  await vi.waitFor(() => expect(pending).toHaveLength(3));
});

test("a rejected lookup reports ok: false with the message", async () => {
  const { pending, results, checker } = setup();
  checker.want(0, "u0");
  pending[0].reject(new Error("boom"));
  await vi.waitFor(() => expect(results).toHaveLength(1));
  expect(results[0]).toEqual([0, { ok: false, message: "Something went wrong." }]);
});

test("checker ignores results after stop", async () => {
  const { pending, results, checker } = setup();
  checker.want(0, "u0");
  checker.want(1, "u1");
  checker.want(2, "u2");
  checker.stop();
  pending[0].resolve(details("u0"));
  await flush();
  expect(results).toEqual([]);
  expect(pending).toHaveLength(2);
});
