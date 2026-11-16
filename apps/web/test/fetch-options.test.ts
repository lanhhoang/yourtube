import { expect, test } from "vitest";
import { readFetchOptions } from "../src/lib/fetch-options.ts";

const OFF = { useProxy: false, useCookies: false };

test("defaults to both off", () => {
  expect(readFetchOptions(null)).toEqual(OFF);
  expect(readFetchOptions("{bad")).toEqual(OFF);
  expect(readFetchOptions("5")).toEqual(OFF);
});

test("reads stored flags", () => {
  expect(readFetchOptions('{"useProxy":true,"useCookies":false}')).toEqual({
    useProxy: true,
    useCookies: false,
  });
  expect(readFetchOptions('{"useProxy":"yes"}')).toEqual(OFF);
});
