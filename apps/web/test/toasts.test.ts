import { expect, test } from "vitest";
import type { JobOut } from "../src/lib/queue.ts";
import { newCompletions, readSeen } from "../src/lib/toasts.ts";

const job = (id: number) => ({ id, title: `t${id}` }) as JobOut;

test("first poll is silent, later polls toast only new ids", () => {
  const r1 = newCompletions(new Set(), [job(1), job(2)], true);
  expect(r1.toasts).toEqual([]);
  expect([...r1.seen]).toEqual(["1", "2"]);
  const r2 = newCompletions(r1.seen, [job(2), job(3)], false);
  expect(r2.toasts.map((j) => j.id)).toEqual([3]);
  expect([...r2.seen]).toEqual(["1", "2", "3"]);
});

test("readSeen tolerates bad input", () => {
  expect(readSeen(null)).toEqual(new Set());
  expect(readSeen("nope")).toEqual(new Set());
  expect(readSeen('{"a":1}')).toEqual(new Set());
  expect(readSeen('["4",5]')).toEqual(new Set(["4", "5"]));
});
