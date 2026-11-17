import { expect, test } from "vitest";
import { type JobOut, leftActive } from "../src/lib/queue.ts";

const job = (id: number) => ({ id }) as JobOut;

test("leftActive is true when a job disappeared", () => {
  expect(leftActive([job(1), job(2)], [job(2)])).toBe(true);
  expect(leftActive([job(1)], [job(1), job(2)])).toBe(false);
  expect(leftActive([], [])).toBe(false);
});
