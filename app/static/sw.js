/* OmniTrackr service worker.
 *
 * Privacy first: this worker never stores library data, API responses, or
 * signed-in pages. It only keeps a tiny offline page and its assets so an
 * installed app shows a friendly message instead of a browser error when the
 * network drops. Everything else goes straight to the network as before.
 */
const CACHE_PREFIX = 'omnitrackr-';
const CACHE_NAME = `${CACHE_PREFIX}offline-v1`;
const OFFLINE_URL = '/offline';
const PRECACHE_URLS = [OFFLINE_URL, '/static/offline.css?v=1', '/static/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS.map((url) => new Request(url, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    if (self.registration.navigationPreload) {
      await self.registration.navigationPreload.enable();
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const preloaded = await event.preloadResponse;
        return preloaded || await fetch(request);
      } catch (error) {
        const offline = await caches.match(OFFLINE_URL);
        return offline || Response.error();
      }
    })());
    return;
  }

  if (PRECACHE_URLS.includes(url.pathname + url.search)) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
  }
});
