import { expect, test } from "vitest";
import { trackLabel } from "../src/lib/subtitles.ts";

test("trackLabel names the language and marks automatic captions", () => {
  expect(trackLabel("fr-orig", "en")).toBe("French (auto)");
  expect(trackLabel("en", "en")).toBe("English");
  expect(trackLabel("pt-BR", "en")).toBe("Brazilian Portuguese");
});

test("trackLabel falls back to the raw code when it is invalid", () => {
  expect(trackLabel("zz-invalid!", "en")).toBe("zz-invalid!");
});
