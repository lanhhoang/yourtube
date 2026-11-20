import { expect, test } from "vitest";
import { pushSupport, urlBase64ToUint8Array } from "../src/lib/push.ts";

const base = {
  hasPushManager: true,
  isIOS: false,
  standalone: false,
  permission: "default",
} as const;

test("urlBase64ToUint8Array decodes url-safe base64 without padding", () => {
  expect(Array.from(urlBase64ToUint8Array("AQID"))).toEqual([1, 2, 3]);
  expect(Array.from(urlBase64ToUint8Array("-_8"))).toEqual([251, 255]);
  expect(Array.from(urlBase64ToUint8Array("AQI"))).toEqual([1, 2]);
});

test("pushSupport", () => {
  expect(pushSupport(base)).toBe("ready");
  expect(pushSupport({ ...base, permission: "granted" })).toBe("ready");
  expect(pushSupport({ ...base, permission: "denied" })).toBe("blocked");
  expect(pushSupport({ ...base, hasPushManager: false })).toBe("unsupported");
  expect(pushSupport({ ...base, permission: "unsupported" })).toBe("unsupported");
  expect(pushSupport({ ...base, isIOS: true, standalone: true })).toBe("ready");
});

test("pushSupport: iOS not installed comes first, even with no PushManager", () => {
  expect(pushSupport({ ...base, isIOS: true, hasPushManager: false })).toBe("install-first");
  expect(pushSupport({ ...base, isIOS: true, permission: "denied" })).toBe("install-first");
  expect(pushSupport({ ...base, isIOS: true, permission: "unsupported" })).toBe("install-first");
});
