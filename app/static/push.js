// Dashboard: turn phone/desktop notifications on or off for this device, from the bell,
// and choose which kinds are pushed and when to keep quiet.
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

  function timeZone() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch (error) { return null; }
  }

  function subscriptionBody(subscription) {
    return JSON.stringify({ ...subscription.toJSON(), time_zone: timeZone() });
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
    const more = $('pushSettingsBtn');
    if (more) more.hidden = state !== 'on';
    if (state !== 'on') closeSettings();
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
    await api('/notifications/push/subscription', { method: 'POST', body: subscriptionBody(subscription) });
    render('on');
  }

  async function turnOff() {
    const subscription = await currentSubscription();
    if (subscription) {
      try {
        await api('/notifications/push/subscription/remove', {
          method: 'POST', body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
      } catch (error) {
        // The browser subscription is removed regardless; the server drops the stale row on its next send.
      }
      await subscription.unsubscribe();
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
      await api('/notifications/push/subscription', { method: 'POST', body: subscriptionBody(subscription) });
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

  // ------------------------------------------------ what gets pushed, and quiet hours

  function hourLabel(hour) {
    try {
      return new Date(2000, 0, 1, hour).toLocaleTimeString([], { hour: 'numeric' });
    } catch (error) {
      return `${hour}:00`;
    }
  }

  function make(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([name, value]) => {
      if (name === 'text') node.textContent = value;
      else if (name.startsWith('aria-')) node.setAttribute(name, value);
      else node[name] = value;
    });
    children.forEach(child => node.appendChild(child));
    return node;
  }

  function hourSelect(name, value, label) {
    const select = make('select', { name, className: 'push-settings__hour', 'aria-label': label });
    for (let hour = 0; hour < 24; hour += 1) {
      select.appendChild(make('option', { value: String(hour), text: hourLabel(hour), selected: hour === value }));
    }
    return select;
  }

  function settingRow(input, name, hint) {
    return make('label', { className: 'push-settings__row' }, [
      input,
      make('span', { className: 'push-settings__label' }, [
        make('span', { className: 'push-settings__name', text: name }),
        make('span', { className: 'push-settings__hint', text: hint }),
      ]),
    ]);
  }

  function buildSettings(form, settings) {
    form.textContent = '';
    form.appendChild(make('p', { className: 'push-settings__title', text: 'Send to my devices' }));
    settings.topics.forEach(topic => {
      form.appendChild(settingRow(make('input', { type: 'checkbox', name: 'topic', value: topic.key, checked: !!topic.on }),
        topic.label, topic.hint));
    });
    const quiet = settings.quiet_hours || { on: true, start: 22, end: 8 };
    form.appendChild(make('div', { className: 'push-settings__quiet' }, [
      settingRow(make('input', { type: 'checkbox', name: 'quiet_hours', checked: !!quiet.on }), 'Quiet hours',
        'Anything that comes in is held, then sent as one catch-up when they end.'),
      make('div', { className: 'push-settings__hours' }, [
        make('span', { text: 'From' }), hourSelect('quiet_start', quiet.start, 'Quiet from'),
        make('span', { text: 'to' }), hourSelect('quiet_end', quiet.end, 'Quiet until'),
      ]),
    ]));
    form.appendChild(make('p', { className: 'push-settings__foot' }, [
      make('span', { text: 'The bell still lists everything. ' }),
      make('span', { id: 'pushSettingsStatus', className: 'push-settings__status', role: 'status' }),
    ]));
    syncHours(form);
  }

  function syncHours(form) {
    const on = form.querySelector('input[name="quiet_hours"]').checked;
    form.querySelectorAll('.push-settings__hour').forEach(select => { select.disabled = !on; });
  }

  function readSettings(form) {
    const topics = {};
    form.querySelectorAll('input[name="topic"]').forEach(input => { topics[input.value] = input.checked; });
    const body = {
      topics,
      quiet_hours: form.querySelector('input[name="quiet_hours"]').checked,
      quiet_start: Number(form.querySelector('select[name="quiet_start"]').value),
      quiet_end: Number(form.querySelector('select[name="quiet_end"]').value),
    };
    const zone = timeZone();
    if (zone) body.time_zone = zone;
    return body;
  }

  function setStatus(message) {
    const status = $('pushSettingsStatus');
    if (status) status.textContent = message;
  }

  let saving = Promise.resolve();

  function saveSettings() {
    const form = $('pushSettings');
    if (!form) return saving;
    syncHours(form);
    const body = JSON.stringify(readSettings(form));
    setStatus('Saving…');
    // One save at a time, in the order the switches were flipped.
    saving = saving.then(() => api('/notifications/push/settings', { method: 'PUT', body }))
      .then(() => setStatus('Saved.'))
      .catch(() => setStatus('That didn’t save. Please try again.'));
    return saving;
  }

  function closeSettings() {
    const form = $('pushSettings');
    const more = $('pushSettingsBtn');
    const dropdown = $('notificationDropdown');
    if (form) form.hidden = true;
    if (more) {
      more.setAttribute('aria-expanded', 'false');
      more.textContent = 'Choose what to get';
    }
    if (dropdown) dropdown.classList.remove('push-settings-open');
  }

  async function openSettings() {
    const form = $('pushSettings');
    const more = $('pushSettingsBtn');
    const dropdown = $('notificationDropdown');
    if (!form || !more) return;
    if (!form.hidden) {
      closeSettings();
      return;
    }
    more.disabled = true;
    try {
      buildSettings(form, await api('/notifications/push/settings'));
      form.hidden = false;
      more.setAttribute('aria-expanded', 'true');
      more.textContent = 'Back to notifications';
      if (dropdown) dropdown.classList.add('push-settings-open');
    } catch (error) {
      const text = $('pushOptInText');
      if (text) text.textContent = 'Your settings didn’t load. Please try again.';
    } finally {
      more.disabled = false;
    }
  }

  document.addEventListener('change', event => {
    if (event.target.closest && event.target.closest('#pushSettings')) saveSettings();
  });

  document.addEventListener('click', async event => {
    if (event.target.closest && event.target.closest('#notificationBell')) {
      closeSettings();
      refresh();
      return;
    }
    if (event.target.closest && event.target.closest('#pushSettingsBtn')) {
      event.preventDefault();
      event.stopPropagation();
      openSettings();
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

  window.omniPush = { refresh, forgetDevice, openSettings, saveSettings };

  if (document.readyState === 'complete') sync();
  else window.addEventListener('load', sync);
})();
