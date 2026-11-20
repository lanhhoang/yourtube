/// <reference lib="webworker" />
import { clientsClaim } from "workbox-core";
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

declare let self: ServiceWorkerGlobalScope;

self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("index.html"), {
    denylist: [/^\/api\//, /^\/health/],
  }),
);

type PushPayload = { title?: string; body?: string; tag?: string; url?: string };

self.addEventListener("push", (event) => {
  let payload: PushPayload = { title: "YourTube", body: "" };
  try {
    const parsed = event.data?.json() as PushPayload | undefined;
    if (parsed && typeof parsed === "object") payload = parsed;
  } catch {
    // keep the fallback
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "YourTube", {
      body: payload.body ?? "",
      tag: payload.tag,
      icon: "/pwa-192x192.png",
      data: { url: payload.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data as { url?: string } | null;
  const url = new URL(data?.url ?? "/", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const client = windows[0];
      if (client) {
        try {
          await client.focus();
          await client.navigate(url);
          return;
        } catch {
          // fall through to openWindow
        }
      }
      await self.clients.openWindow(url);
    })(),
  );
});
