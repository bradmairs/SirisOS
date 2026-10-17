/* SirisOS service worker: shows phone notifications sent by SirisOS
   (push/notifier.py) and opens the right screen when one is tapped. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

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
