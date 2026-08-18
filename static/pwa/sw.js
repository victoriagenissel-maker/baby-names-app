const CACHE_NAME = "baby-names-v2";
const APP_SHELL = [
  "/",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/pwa/icon.svg",
  "/static/pwa/offline.html"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET") {
    return;
  }

  // Dynamic endpoints should always come from network.
  if (
    url.pathname.startsWith("/next") ||
    url.pathname.startsWith("/history") ||
    url.pathname.startsWith("/likes") ||
    url.pathname.startsWith("/dislikes") ||
    url.pathname.startsWith("/matches") ||
    url.pathname.startsWith("/users") ||
    url.pathname.startsWith("/filters")
  ) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() =>
        caches.match(request).then((cached) => {
          if (cached) {
            return cached;
          }
          if (request.mode === "navigate") {
            return caches.match("/static/pwa/offline.html");
          }
          return new Response("Offline", { status: 503, statusText: "Offline" });
        })
      )
  );
});
