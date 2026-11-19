self.addEventListener("install", (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const requestId = event.notification.data?.requestId;
  const target = new URL("/dashboard/", self.location.origin);
  if (typeof requestId === "string") {
    target.hash = `request=${encodeURIComponent(requestId)}`;
  }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: "window", includeUncontrolled: true});
    for (const client of windows) {
      const clientUrl = new URL(client.url);
      if (clientUrl.origin !== self.location.origin || !clientUrl.pathname.startsWith("/dashboard")) continue;
      try {
        client.postMessage({type: "guardian:review-request", requestId: typeof requestId === "string" ? requestId : null});
        return await client.focus();
      } catch {
        try { return client.focus(); } catch {}
      }
    }
    return self.clients.openWindow(target.href);
  })());
});
