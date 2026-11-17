import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { createPoller } from "../src/lib/poll.ts";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const slow = (ms: number, calls: number[]) => () => {
  calls.push(Date.now());
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
};

test("runs at once, then intervalMs after each run finishes", async () => {
  const t0 = Date.now();
  const calls: number[] = [];
  const p = createPoller(slow(5000, calls), 2000, () => false);
  p.start();
  await vi.advanceTimersByTimeAsync(0);
  expect(calls).toEqual([t0]);
  await vi.advanceTimersByTimeAsync(6999);
  expect(calls).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(calls).toEqual([t0, t0 + 7000]);
  p.stop();
});

test("does not run again after stop, even if a run was in flight", async () => {
  const calls: number[] = [];
  const p = createPoller(slow(5000, calls), 2000, () => false);
  p.start();
  await vi.advanceTimersByTimeAsync(1000);
  p.stop();
  await vi.advanceTimersByTimeAsync(60_000);
  expect(calls).toHaveLength(1);
});

test("skips runs while hidden and resumes when visible", async () => {
  let hidden = true;
  const task = vi.fn(async () => {});
  const p = createPoller(task, 1000, () => hidden);
  p.start();
  await vi.advanceTimersByTimeAsync(3500);
  expect(task).not.toHaveBeenCalled();
  hidden = false;
  await vi.advanceTimersByTimeAsync(1000);
  expect(task).toHaveBeenCalledTimes(1);
  p.stop();
});

test("keeps polling after a rejected run", async () => {
  const task = vi.fn(async () => {
    throw new Error("boom");
  });
  const p = createPoller(task, 1000, () => false);
  p.start();
  await vi.advanceTimersByTimeAsync(2500);
  expect(task).toHaveBeenCalledTimes(3);
  p.stop();
});
