import { expect, test } from "vitest";
import { latest } from "../src/lib/latest.ts";

test("only the most recent ticket stays current", () => {
  const next = latest();
  const a = next();
  expect(a()).toBe(true);
  const b = next();
  expect(a()).toBe(false);
  expect(b()).toBe(true);
});

test("a late reply for an earlier request is dropped", async () => {
  const next = latest();
  let shown = "";
  const load = async (id: string, delay: number) => {
    const current = next();
    await new Promise((r) => setTimeout(r, delay));
    if (current()) shown = id;
  };
  await Promise.all([load("A", 20), load("B", 1)]);
  expect(shown).toBe("B");
});
