// Dashboard: turn phone/desktop notifications on or off for this device, from the bell.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  let busy = false;

  function supported() {
    return window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  function signedIn() {
    try { return typeof isAuthenticated === 'function' && isAuthenticated(); } catch (error) { return false; }
  }

  function standalone() {
    try {
      return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    } catch (error) {
      return false;
    }
  }

  function iosBrowser() {
    const ua = window.navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && window.navigator.maxTouchPoints > 1);
  }

  async function api(path, options = {}) {
    const request = { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } };
    const response = typeof authenticatedFetch === 'function'
      ? await authenticatedFetch(`${apiBase()}${path}`, request)
      : await fetch(`${apiBase()}${path}`, { credentials: 'same-origin', ...request });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.json();
  }

  function keyBytes(base64url) {
    const padded = (base64url + '='.repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(padded);
    return Uint8Array.from(raw, char => char.charCodeAt(0));
  }

  function sameKey(subscription, key) {
    const current = subscription.options && subscription.options.applicationServerKey;
    if (!current) return true;
    const a = new Uint8Array(current);
    return a.length === key.length && a.every((byte, index) => byte === key[index]);
  }

  async function registration() {
    // pwa.js registers the worker on load; wait for it, but never forever.
    let timer;
    const timeout = new Promise(resolve => { timer = setTimeout(() => resolve(null), 8000); });
    try {
      return await Promise.race([navigator.serviceWorker.ready, timeout]);
    } finally {
      clearTimeout(timer);
    }
  }

  async function currentSubscription() {
    const reg = await registration();
    return reg ? reg.pushManager.getSubscription() : null;
  }

  function render(state, message) {
    const box = $('pushOptIn');
    const text = $('pushOptInText');
    const button = $('pushOptInBtn');
    if (!box || !text || !button) return;
    const copy = {
      off: ['Get these on this device too, even when OmniTrackr is closed.', 'Turn on'],
      on: ['Notifications are on for this device.', 'Turn off'],
      blocked: ['Notifications are blocked for OmniTrackr in this browser’s settings.', ''],
      install: ['On iPhone and iPad, add OmniTrackr to your Home Screen to get notifications.', 'Show me how'],
    }[state];
    if (!copy) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.dataset.state = state;
    text.textContent = message || copy[0];
    button.textContent = copy[1];
    button.hidden = !copy[1];
    button.disabled = false;
  }

  async function refresh() {
    if (!signedIn()) return render(null);
    if (!supported()) return render(iosBrowser() && !standalone() ? 'install' : null);
    if (Notification.permission === 'denied') return render('blocked');
    try {
      const subscription = await currentSubscription();
      render(subscription && Notification.permission === 'granted' ? 'on' : 'off');
    } catch (error) {
      render('off');
    }
  }

  async function turnOn() {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      render(permission === 'denied' ? 'blocked' : 'off');
      return;
    }
    const reg = await registration();
    if (!reg) throw new Error('Service worker unavailable');
    const { public_key: publicKey } = await api('/notifications/push/key');
    const key = keyBytes(publicKey);
    let subscription = await reg.pushManager.getSubscription();
    if (subscription && !sameKey(subscription, key)) {
      await subscription.unsubscribe();
      subscription = null;
    }
    subscription = subscription || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    await api('/notifications/push/subscription', { method: 'POST', body: JSON.stringify(subscription.toJSON()) });
    render('on');
  }

  async function turnOff() {
    const subscription = await currentSubscription();
    if (subscription) {
      try {
        await api('/notifications/push/subscription/remove', {
          method: 'POST', body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
      } finally {
        await subscription.unsubscribe();
      }
    }
    render('off');
  }

  // Keeps the server's record in step with this browser (new keys, or a different member signed in).
  async function sync() {
    if (!signedIn() || !supported() || Notification.permission !== 'granted') return;
    try {
      const subscription = await currentSubscription();
      if (!subscription) return;
      const { public_key: publicKey } = await api('/notifications/push/key');
      if (!sameKey(subscription, keyBytes(publicKey))) {
        await subscription.unsubscribe();
        return;
      }
      await api('/notifications/push/subscription', { method: 'POST', body: JSON.stringify(subscription.toJSON()) });
    } catch (error) { /* tried again next visit */ }
  }

  // Called before signing out so the next person on this device doesn't get this member's notifications.
  async function forgetDevice() {
    if (!supported()) return;
    try {
      let timer;
      const subscription = await Promise.race([
        currentSubscription(), new Promise(resolve => { timer = setTimeout(() => resolve(null), 2000); }),
      ]).finally(() => clearTimeout(timer));
      if (!subscription) return;
      try {
        await api('/notifications/push/subscription/remove', {
          method: 'POST', body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
      } catch (error) { /* the browser unsubscribe below still stops delivery */ }
      await subscription.unsubscribe();
    } catch (error) { /* signing out continues */ }
  }

  document.addEventListener('click', async event => {
    if (event.target.closest && event.target.closest('#notificationBell')) {
      refresh();
      return;
    }
    const button = event.target.closest && event.target.closest('#pushOptInBtn');
    if (!button || busy) return;
    event.preventDefault();
    event.stopPropagation();
    const state = $('pushOptIn') && $('pushOptIn').dataset.state;
    if (state === 'install') {
      const dialog = $('installAppDialog');
      if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
      return;
    }
    busy = true;
    button.disabled = true;
    try {
      if (state === 'on') await turnOff();
      else await turnOn();
    } catch (error) {
      render(state === 'on' ? 'on' : 'off', 'That didn’t work. Please try again.');
    } finally {
      busy = false;
      button.disabled = false;
    }
  });

  window.omniPush = { refresh, forgetDevice };

  if (document.readyState === 'complete') sync();
  else window.addEventListener('load', sync);
})();
