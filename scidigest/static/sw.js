/* Offline support: pages and data are fetched fresh when online and fall back to the last
   copy when offline. Version bumps clear old caches. */
const CACHE = "scidigest-v15";
const CORE = ["./", "index.html", "search.html", "saved.html", "idea.html", "privacy.html", "terms.html", "cookies.html", "credits.html", "app.js",
              "manifest.webmanifest", "apple-touch-icon.png", "icon-192.png", "data/index.json", "data/search.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).catch(() => {}).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;   // APIs and images: straight to network
  e.respondWith(
    fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then((hit) => hit || caches.match("index.html")))
  );
});
