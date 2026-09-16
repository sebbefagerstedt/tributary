// Caches the app shell so the feed opens instantly and survives a dropped
// connection. The feed data is deliberately never cached: a stale feed is worse
// than an honest error, and on a static host data.json is the only thing that
// ever changes.
//
// Paths are relative so the same file works at a domain root and at a GitHub
// Pages repository subpath.
const SHELL = 'tributary-shell-v2';
const ASSETS = ['./', './index.html', './manifest.json', './icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isData = url.pathname.endsWith('/data.json') || url.pathname.startsWith('/api/');
  if (event.request.method !== 'GET' || isData) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(SHELL).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match('./')))
  );
});
