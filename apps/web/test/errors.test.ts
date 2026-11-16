import { expect, test } from "vitest";
import { ApiError, messageFor } from "../src/lib/errors.ts";

test("messageFor uses ApiError message", () => {
  expect(messageFor(new ApiError("disk_full", "Disk is full."))).toBe("Disk is full.");
});

test("messageFor falls back", () => {
  expect(messageFor(new Error("x"))).toBe("Something went wrong.");
  expect(messageFor(new ApiError("x", ""))).toBe("Something went wrong.");
  expect(messageFor(undefined)).toBe("Something went wrong.");
});
