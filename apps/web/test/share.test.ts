import { expect, test } from "vitest";
import { sharedUrl } from "../src/lib/share.ts";

test("sharedUrl", () => {
  expect(sharedUrl("?share=https%3A%2F%2Fyoutu.be%2Fa")).toBe("https://youtu.be/a");
  expect(sharedUrl("?text=Watch%20this%20https%3A%2F%2Fyoutu.be%2Fb%20!")).toBe(
    "https://youtu.be/b",
  );
  expect(sharedUrl("?title=x")).toBeNull();
  expect(sharedUrl("")).toBeNull();
});
