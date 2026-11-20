import { expect, test } from "vitest";
import type { JobOut, QueueOut } from "../src/lib/queue.ts";
import { newEvents, readSeen } from "../src/lib/toasts.ts";

const job = (id: number, extra: Partial<JobOut> = {}) =>
  ({ id, title: `t${id}`, url: `u${id}`, batch_id: null, ...extra }) as JobOut;

const queue = (q: Partial<QueueOut>): QueueOut => ({
  active: [],
  failed: [],
  completed: [],
  batches: [],
  ...q,
});

test("first poll is silent but marks every key seen", () => {
  const r1 = newEvents(
    new Set(),
    queue({
      completed: [job(1), job(2)],
      failed: [job(3)],
      batches: [
        { batch_id: "b", name: "Mix", done: 1, failed: 0, cancelled: 0, finished_at: null },
      ],
    }),
    true,
  );
  expect(r1.toasts).toEqual([]);
  expect([...r1.seen].sort()).toEqual(["batch:b", "done:1", "done:2", "failed:3"]);
});

test("a new completed job toasts once", () => {
  const q = queue({ completed: [job(2)] });
  const r = newEvents(new Set(["done:1"]), q, false);
  expect(r.toasts).toEqual([{ key: "done:2", kind: "done", title: "t2", body: "Downloaded" }]);
  expect(newEvents(r.seen, q, false).toasts).toEqual([]);
});

test("a new failed single job toasts as failed", () => {
  const r = newEvents(new Set(), queue({ failed: [job(4, { error_message: "Nope" })] }), false);
  expect(r.toasts).toEqual([
    { key: "failed:4", kind: "failed", title: "Download failed", body: "t4: Nope" },
  ]);
});

test("jobs in a batch never toast on their own", () => {
  const r = newEvents(
    new Set(),
    queue({ completed: [job(5, { batch_id: "b" })], failed: [job(6, { batch_id: "b" })] }),
    false,
  );
  expect(r.toasts).toEqual([]);
});

test("a new batch toasts with the push wording", () => {
  const b = { batch_id: "b", name: "Mix", done: 2, failed: 0, cancelled: 0, finished_at: null };
  const q = queue({ batches: [b] });
  const r = newEvents(new Set(), q, false);
  expect(r.toasts).toEqual([{ key: "batch:b", kind: "batch", title: "Mix", body: "2 downloaded" }]);
  expect(newEvents(r.seen, q, false).toasts).toEqual([]);
  const mixed = newEvents(
    new Set(),
    queue({ batches: [{ ...b, done: 0, failed: 1, cancelled: 3 }] }),
    false,
  );
  expect(mixed.toasts[0].body).toBe("1 failed, 3 cancelled");
  const none = newEvents(new Set(), queue({ batches: [{ ...b, done: 0 }] }), false);
  expect(none.toasts[0].body).toBe("0 downloaded");
});

test("readSeen tolerates bad input", () => {
  expect(readSeen(null)).toEqual(new Set());
  expect(readSeen("nope")).toEqual(new Set());
  expect(readSeen('{"a":1}')).toEqual(new Set());
  expect(readSeen('["4",5]')).toEqual(new Set(["4", "5"]));
});
