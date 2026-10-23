/* SirisOS service worker:
   - keeps the app itself (the page and its scripts) so SirisOS opens with no
     signal; the data comes from the app's own on-device cache (api/resource.ts).
     /api/ is never touched here.
   - shows phone notifications sent by SirisOS (push/notifier.py) and opens
     the right screen when one is tapped.
   - runs a notification's buttons (Done, Snooze...: push/actions.py) right
     here, with the signed token in its /act?t= link; no sign-in needed.
     iPhone shows no buttons, so a tap opens that /act page instead. */

const SHELL = "sirisos-shell-v2";
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
      actions: Array.isArray(data.actions) ? data.actions.slice(0, 2) : [],
      data: { url: data.url || "/" },
    }),
  );
});

async function press(notification, action) {
  const link = new URL((notification.data && notification.data.url) || "/", self.location.origin);
  const response = await fetch("/api/v1/push/act", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: link.searchParams.get("t"), action }),
  });
  const body = await response.json().catch(() => ({}));
  await self.registration.showNotification(response.ok ? notification.title : "SirisOS couldn't do that", {
    body: response.ok ? body.message || "Done." : body.detail || "Open SirisOS to try again.",
    icon: "/siris-icon.png",
    badge: "/siris-icon.png",
    tag: notification.tag || undefined,
    silent: true,
    data: { url: response.ok ? body.url || "/" : link.href },
  });
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action) {
    event.waitUntil(press(event.notification, event.action));
    return;
  }
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
