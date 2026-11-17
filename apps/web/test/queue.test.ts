import { expect, test } from "vitest";
import { type JobOut, leftActive, newlyCompleted } from "../src/lib/queue.ts";

const job = (id: number) => ({ id }) as JobOut;

test("leftActive is true when a job disappeared", () => {
  expect(leftActive([job(1), job(2)], [job(2)])).toBe(true);
  expect(leftActive([job(1)], [job(1), job(2)])).toBe(false);
  expect(leftActive([], [])).toBe(false);
});

test("newlyCompleted spots ids that were not completed before", () => {
  expect(newlyCompleted([job(1)], [job(1), job(2)])).toBe(true);
  expect(newlyCompleted([job(1), job(2)], [job(2)])).toBe(false);
  expect(newlyCompleted([], [])).toBe(false);
});
