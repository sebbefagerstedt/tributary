// Retires version 1's service worker. That page cached its shell under this
// path; a phone that installed it keeps the worker until the worker itself
// changes. This one clears the old cache, unregisters, and reloads open tabs,
// so they show the current page. The current page registers no worker: a
// stale page is worse than a fresh load (VISION.md carries that lesson over).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) await caches.delete(key);
    await self.registration.unregister();
    for (const client of await self.clients.matchAll({ type: 'window' })) client.navigate(client.url);
  })());
});
