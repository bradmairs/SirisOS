/* SirisOS service worker:
   - keeps the app itself (the page and its scripts) so SirisOS opens with no
     signal; the data comes from the app's own on-device cache (api/resource.ts).
     /api/ is never touched here.
   - shows phone notifications sent by SirisOS (push/notifier.py) and opens
     the right screen when one is tapped. */

const SHELL = "sirisos-shell-v1";
const MAX_ASSETS = 150;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("sirisos-shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  ),
);

async function trim(cache) {
  const keys = (await cache.keys()).filter((r) => new URL(r.url).pathname.startsWith("/assets/"));
  await Promise.all(keys.slice(0, Math.max(0, keys.length - MAX_ASSETS)).map((r) => cache.delete(r)));
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  // The page: always try the network (so updates arrive), fall back to the last copy.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) caches.open(SHELL).then((c) => c.put("/", response.clone()));
          return response;
        })
        .catch(() => caches.open(SHELL).then((c) => c.match("/")).then((r) => r || Response.error())),
    );
    return;
  }

  // Hashed scripts and styles never change: cache first.
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.open(SHELL).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone()).then(() => trim(cache));
        return response;
      }),
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "SirisOS", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "SirisOS", {
      body: data.body || "",
      icon: "/siris-icon.png",
      badge: "/siris-icon.png",
      tag: data.tag || undefined,
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const win of windows) {
        if (new URL(win.url).origin === self.location.origin && "focus" in win) {
          win.navigate(url).catch(() => undefined);
          return win.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
