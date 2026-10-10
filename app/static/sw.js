/* OmniTrackr service worker.
 *
 * Deliberately small:
 *  - Versioned files under /static/ (the ones loaded with ?v=) are cached after
 *    first use, so repeat visits and the installed app open faster.
 *  - Pages always come from the network. Library pages are private, so no HTML
 *    is stored; when the network is down the visitor sees /offline instead.
 *  - API calls, sign-in and everything else are never touched.
 *  - Push messages show a notification; tapping it opens that page.
 */
const VERSION = '20261010-push-1';
const STATIC_CACHE = `omnitrackr-static-${VERSION}`;
const OFFLINE_CACHE = `omnitrackr-offline-${VERSION}`;
const OFFLINE_URL = '/offline';
const MAX_STATIC_ENTRIES = 80;

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(OFFLINE_CACHE)
      .then(cache => cache.add(new Request(OFFLINE_URL, { cache: 'reload' })))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys
        .filter(key => key.startsWith('omnitrackr-') && key !== STATIC_CACHE && key !== OFFLINE_CACHE)
        .map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function trimCache(cache) {
  const keys = await cache.keys();
  for (let index = 0; index < keys.length - MAX_STATIC_ENTRIES; index += 1) {
    await cache.delete(keys[index]);
  }
}

async function staticFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === 'basic') {
    cache.put(request, response.clone()).then(() => trimCache(cache)).catch(() => {});
  }
  return response;
}

async function pageWithOfflineFallback(request) {
  try {
    return await fetch(request);
  } catch (error) {
    const cache = await caches.open(OFFLINE_CACHE);
    return (await cache.match(OFFLINE_URL)) || Response.error();
  }
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(pageWithOfflineFallback(request));
    return;
  }
  // Only versioned static files: their content never changes for a given ?v=.
  if (url.pathname.startsWith('/static/') && url.searchParams.has('v')) {
    event.respondWith(staticFirst(request));
  }
});

// Phone and desktop notifications. The server only sends these to devices
// whose member turned them on from the notification bell.
self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { body: event.data ? event.data.text() : '' };
  }
  const url = typeof data.url === 'string' && data.url.startsWith('/') && !data.url.startsWith('//') ? data.url : '/';
  event.waitUntil(self.registration.showNotification(String(data.title || 'OmniTrackr'), {
    body: String(data.body || ''),
    icon: '/static/icons/icon-192.png?v=20261003-pwa-1',
    data: { url },
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin);
  if (url.origin !== self.location.origin) return;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const open = windows.find(client => new URL(client.url).origin === self.location.origin && 'focus' in client);
    if (open) {
      await open.focus();
      if ('navigate' in open) return open.navigate(url.href).catch(() => self.clients.openWindow(url.href));
      return undefined;
    }
    return self.clients.openWindow(url.href);
  })());
});
