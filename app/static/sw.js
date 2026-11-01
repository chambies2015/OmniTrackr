/* OmniTrackr service worker.
 *
 * Deliberately small:
 *  - Versioned files (anything under /static/ loaded with ?v=, plus the root
 *    /app.js and /auth.js) and the self-hosted fonts are cached
 *    after first use, so repeat visits and the installed app open faster. When a
 *    new version of a file is cached, older versions of that same file are
 *    dropped, so the cache holds what the pages use today.
 *  - Pages always come from the network. Library pages are private, so no HTML
 *    is stored; when the network is down the visitor sees /offline instead.
 *    Navigation preload starts that network request while the worker boots,
 *    which on phones saves the worker's start-up time on every page open.
 *  - API calls, sign-in and everything else are never touched.
 *  - Push messages show a notification; tapping it opens that page.
 */
const VERSION = '20261101-speed-1';
// The static cache keeps its old name on purpose: renaming it would make every
// member download every file again after this update.
const STATIC_CACHE = 'omnitrackr-static-20261010-push-1';
const OFFLINE_CACHE = `omnitrackr-offline-${VERSION}`;
const OFFLINE_URL = '/offline';
// The dashboard alone uses about 80 files, so leave room for the public pages too.
const MAX_STATIC_ENTRIES = 220;
// Root scripts the server already marks immutable when they carry ?v=.
const VERSIONED_ROOT_FILES = new Set(['/app.js', '/auth.js']);

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
      .then(() => (self.registration.navigationPreload
        ? self.registration.navigationPreload.enable().catch(() => {})
        : undefined))
      .then(() => self.clients.claim())
  );
});

async function trimCache(cache, keep) {
  const keys = await cache.keys();
  // Older versions of the file just stored are never requested again.
  const keepUrl = new URL(keep.url);
  const stale = keys.filter(key => {
    const url = new URL(key.url);
    return url.pathname === keepUrl.pathname && url.search !== keepUrl.search;
  });
  await Promise.all(stale.map(key => cache.delete(key)));
  const rest = keys.filter(key => !stale.includes(key));
  for (let index = 0; index < rest.length - MAX_STATIC_ENTRIES; index += 1) {
    await cache.delete(rest[index]);
  }
}

async function staticFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === 'basic') {
    cache.put(request, response.clone()).then(() => trimCache(cache, request)).catch(() => {});
  }
  return response;
}

async function pageWithOfflineFallback(event) {
  try {
    const preloaded = await event.preloadResponse;
    if (preloaded) return preloaded;
    return await fetch(event.request);
  } catch (error) {
    const cache = await caches.open(OFFLINE_CACHE);
    return (await cache.match(OFFLINE_URL)) || Response.error();
  }
}

function cacheable(url) {
  if (url.pathname.startsWith('/static/fonts/')) return true;
  if (!url.searchParams.has('v')) return false;
  return url.pathname.startsWith('/static/') || VERSIONED_ROOT_FILES.has(url.pathname);
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(pageWithOfflineFallback(event));
    return;
  }
  // Only versioned files and fonts: their content never changes for a given URL.
  if (cacheable(url)) {
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
