// Numra service worker (V1.5 Epic I). Scope is intentionally narrow: it only ever
// caches immutable, versioned static assets. It must NEVER cache anything under
// /api/ -- that is the same-origin backend proxy (src/app/api/[...path]/route.ts)
// and every response there can carry session-authenticated personal data (profiles,
// calculations, reports). Caching that would be a privacy defect, not a feature.
const CACHE_NAME = "numra-shell-v1";
const PRECACHE_URLS = ["/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function isCacheableStaticAsset(url) {
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest"
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only ever handle same-origin GET requests. Everything under /api/ (auth,
  // people, calculations, reports, relationships, exports -- all of it) is
  // deliberately left untouched here and falls through to the network exactly as
  // if this service worker did not exist.
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }

  if (isCacheableStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then(
        (cached) =>
          cached ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
            return res;
          }),
      ),
    );
    return;
  }

  // Page navigations and everything else: network-only. No response body from
  // this branch is ever written to a cache, so there is no stale/offline copy of
  // any server-rendered page (which may embed per-user data) to accidentally serve
  // to a different visitor sharing this browser profile.
  event.respondWith(fetch(req).catch(() => caches.match(req)));
});
