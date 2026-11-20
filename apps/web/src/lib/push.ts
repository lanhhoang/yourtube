import { api, call } from "./api.ts";

export type PushEnv = {
  hasPushManager: boolean;
  isIOS: boolean;
  standalone: boolean;
  permission: NotificationPermission | "unsupported";
};

export type PushSupport = "ready" | "install-first" | "blocked" | "unsupported";

export function urlBase64ToUint8Array(s: string): Uint8Array<ArrayBuffer> {
  const padded = s + "=".repeat((4 - (s.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export function pushSupport(env: PushEnv): PushSupport {
  if (env.isIOS && !env.standalone) return "install-first";
  if (!env.hasPushManager || env.permission === "unsupported") return "unsupported";
  if (env.permission === "denied") return "blocked";
  return "ready";
}

export function pushEnv(): PushEnv {
  const nav = navigator as Navigator & { standalone?: boolean };
  const isIOS =
    /iPad|iPhone|iPod/.test(nav.userAgent) ||
    (nav.platform === "MacIntel" && nav.maxTouchPoints > 1);
  const standalone =
    nav.standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  return {
    hasPushManager: "PushManager" in window && "serviceWorker" in navigator,
    isIOS,
    standalone,
    permission: typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  };
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

function body(sub: PushSubscription) {
  const json = sub.toJSON();
  return {
    endpoint: sub.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
  };
}

/** Re-sends an existing subscription (an upsert), e.g. after a database reset. */
export async function syncSubscription(sub: PushSubscription): Promise<void> {
  await call(api.POST("/api/push/subscriptions", { body: body(sub) }));
}

export async function enablePush(publicKey: string): Promise<"on" | "blocked"> {
  // Must run straight from the tap: iOS rejects the permission request after an await on the network.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "blocked";
  const registration = await navigator.serviceWorker.ready;
  const sub = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  await syncSubscription(sub);
  return "on";
}

export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) return;
  await call(api.DELETE("/api/push/subscriptions", { body: { endpoint: sub.endpoint } }));
  await sub.unsubscribe();
}
