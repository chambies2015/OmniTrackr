// "Stay posted": the home-screen card that offers the weekly email, notifications on this device and the
// private calendar to members who have none of them yet, and the short note after saving a TV show or anime.
// The server decides when to ask (app/stay_posted.py); every button calls that channel's own endpoint, so
// nothing is ever switched on without a press. Server text is only set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const REFRESH_GAP_MS = 60 * 1000;
  const state = { ask: null, request: 0, seen: '', observer: null, lastRefresh: 0, calendar: null, afterBusy: false };

  function options(extra = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(extra);
    return { credentials: 'same-origin', ...extra };
  }

  async function send(method, url, body) {
    const response = await fetch(url, options({
      method,
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data && typeof data.detail === 'string' ? data.detail : 'That didn’t work. Please try again.');
    return data;
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text || '';
  }

  // ------------------------------------------------ can this browser take notifications?

  function pushSupported() {
    return Boolean(window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window
      && 'Notification' in window && window.omniPush);
  }

  // True when a press could turn notifications on here: supported, not blocked, not already on.
  async function pushPossible() {
    if (!pushSupported()) return false;
    try {
      if (Notification.permission === 'denied') return false;
      if (window.omniPush.state() === null || window.omniPush.state() === undefined) await window.omniPush.refresh();
      return window.omniPush.state() === 'off';
    } catch (error) {
      return false;
    }
  }

  // ------------------------------------------------ the card

  function dayLabel(iso) {
    try {
      const [year, month, day] = String(iso).split('-').map(Number);
      const when = new Date(year, month - 1, day);
      if (Number.isNaN(when.getTime())) return '';
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const days = Math.round((when - today) / 86400000);
      if (days === 0) return 'Today';
      if (days === 1) return 'Tomorrow';
      return when.toLocaleDateString(undefined, days < 7 ? { weekday: 'long' } : { weekday: 'short', month: 'short', day: 'numeric' });
    } catch (error) {
      return '';
    }
  }

  function renderItems(items) {
    const list = $('stayPostedItems');
    if (!list) return;
    list.replaceChildren();
    (items || []).slice(0, 3).forEach(item => {
      const row = document.createElement('li');
      row.className = 'stay-posted__item';
      const name = document.createElement('strong');
      name.textContent = item.title || '';
      const what = document.createElement('span');
      what.className = 'stay-posted__what';
      what.textContent = [item.label, item.kind === 'episode' ? item.what : 'Release day'].filter(Boolean).join(' · ');
      const when = document.createElement('span');
      when.className = 'stay-posted__when';
      when.textContent = dayLabel(item.date);
      row.append(name, what, when);
      list.appendChild(row);
    });
    list.hidden = !list.children.length;
  }

  function option(channel) {
    const card = $('stayPosted');
    return card ? card.querySelector(`.stay-posted__option[data-channel="${channel}"]`) : null;
  }

  async function render(ask) {
    const card = $('stayPosted');
    if (!card) return;
    state.ask = ask || null;
    if (!ask) {
      card.hidden = true;
      return;
    }
    const show = {
      push: await pushPossible(),
      email: Boolean(ask.offer && ask.offer.email),
      calendar: Boolean(ask.offer && ask.offer.calendar),
    };
    if (state.ask !== ask) return;  // a newer refresh or a sign-out got here first
    if (!show.push && !show.email && !show.calendar) {
      card.hidden = true;
      return;
    }
    card.classList.remove('is-done');
    setText('stayPostedEyebrow', ask.eyebrow);
    setText('stayPostedTitle', ask.title);
    setText('stayPostedBody', ask.body);
    setText('stayPostedStatus', '');
    renderItems(ask.items);
    Object.entries(show).forEach(([channel, visible]) => {
      const row = option(channel);
      if (!row) return;
      row.hidden = !visible;
      row.classList.remove('is-on');
      const button = row.querySelector('[data-stay-channel]');
      if (button) {
        button.disabled = false;
        button.textContent = { push: 'Notify me on this device', email: 'Send me the weekly email', calendar: 'Add to my calendar' }[channel];
      }
    });
    const links = $('stayPostedCalendarLinks');
    if (links) links.hidden = true;
    const foot = card.querySelector('.stay-posted__foot');
    if (foot) foot.hidden = false;
    card.hidden = false;
    watchSeen(card);
  }

  // Counted as shown once half the card is on screen, so a card nobody scrolled to doesn't use up a turn.
  function watchSeen(card) {
    if (state.observer) state.observer.disconnect();
    const moment = state.ask && state.ask.moment;
    if (!moment || state.seen === moment) return;
    const report = () => {
      if (state.seen === moment || !state.ask || state.ask.moment !== moment) return;
      state.seen = moment;
      send('POST', '/api/stay-posted/seen', { moment }).catch(() => { state.seen = ''; });
    };
    if (typeof IntersectionObserver !== 'function') {
      report();
      return;
    }
    state.observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.5 && !document.hidden)) {
        state.observer.disconnect();
        report();
      }
    }, { threshold: [0.5] });
    state.observer.observe(card);
  }

  function answer(reply, place = 'card') {
    return send('POST', '/api/stay-posted/answer', { answer: reply, place }).catch(() => null);
  }

  function markOn(channel, text) {
    const card = $('stayPosted');
    const row = option(channel);
    if (row) {
      row.classList.add('is-on');
      const button = row.querySelector('[data-stay-channel]');
      if (button) {
        button.disabled = true;
        button.textContent = text;
      }
    }
    if (card) {
      card.classList.add('is-done');
      const foot = card.querySelector('.stay-posted__foot');
      if (foot) foot.hidden = true;
    }
    setText('stayPostedStatus', 'Done. You can change this any time in Settings → Notifications.');
  }

  async function turnOnPush(button) {
    button.disabled = true;
    let result = 'off';
    try {
      result = await window.omniPush.turnOn('home_card');
    } catch (error) {
      result = 'off';
    }
    if (result === 'on') {
      markOn('push', '✓ Notifications on for this device');
      answer('push');
      return;
    }
    button.disabled = false;
    setText('stayPostedStatus', result === 'blocked'
      ? 'Notifications are blocked for OmniTrackr in this browser’s settings. The weekly email or the calendar work without them.'
      : 'Notifications didn’t turn on. You can try again, or pick another way.');
  }

  async function turnOnEmail(button) {
    button.disabled = true;
    try {
      await send('PUT', '/api/for-you/email', { enabled: true, source: 'home_card' });
      markOn('email', '✓ Weekly email on');
      try { document.dispatchEvent(new CustomEvent('omni:weekly-email', { detail: { enabled: true, from: 'home_card' } })); } catch (error) { /* old browsers */ }
      answer('email');
    } catch (error) {
      button.disabled = false;
      setText('stayPostedStatus', error.message);
    }
  }

  function safe(url, prefix) {
    return typeof url === 'string' && url.startsWith(prefix) ? url : null;
  }

  async function turnOnCalendar(button) {
    button.disabled = true;
    try {
      const data = await send('POST', '/api/calendar');
      state.calendar = data && data.links ? data.links : null;
      const links = state.calendar || {};
      const pairs = [['stayPostedGoogle', safe(links.google, 'https://calendar.google.com/')],
        ['stayPostedApple', safe(links.webcal, 'webcal://')], ['stayPostedOutlook', safe(links.outlook, 'https://outlook.live.com/')]];
      pairs.forEach(([id, url]) => {
        const link = $(id);
        if (!link) return;
        link.hidden = !url;
        if (url) link.href = url;
      });
      const box = $('stayPostedCalendarLinks');
      if (box) box.hidden = false;
      markOn('calendar', '✓ Calendar ready');
      setText('stayPostedStatus', 'Pick your calendar app above to add it. It refreshes by itself from then on.');
      answer('calendar');
    } catch (error) {
      button.disabled = false;
      setText('stayPostedStatus', error.message);
    }
  }

  async function copyCalendar() {
    const url = state.calendar && safe(state.calendar.url, 'https://');
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setText('stayPostedStatus', 'Address copied. In your calendar app, choose "Add calendar from URL" or "Subscribe" and paste it.');
    } catch (error) {
      setText('stayPostedStatus', `Paste this address into your calendar app: ${url}`);
    }
  }

  function bindCard() {
    const card = $('stayPosted');
    if (!card || card.dataset.bound) return;
    card.dataset.bound = '1';
    card.addEventListener('click', event => {
      const button = event.target.closest && event.target.closest('[data-stay-channel]');
      if (!button || button.disabled) return;
      const channel = button.dataset.stayChannel;
      if (channel === 'push') turnOnPush(button);
      else if (channel === 'email') turnOnEmail(button);
      else if (channel === 'calendar') turnOnCalendar(button);
    });
    // "See what yours would say" opens the member's own email in place (weekly-preview.js), not a new tab.
    $('stayPostedSample')?.addEventListener('click', event => {
      answer('sample');
      const peek = $('stayPostedPeek');
      if (!peek || !window.OmniWeeklyPreview) return;
      event.preventDefault();
      peek.hidden = !peek.hidden;
      event.currentTarget.setAttribute('aria-expanded', String(!peek.hidden));
      if (!peek.hidden && !peek.dataset.weeklyPreviewState) window.OmniWeeklyPreview.fill(peek);
    });
    $('stayPostedCopy')?.addEventListener('click', copyCalendar);
    $('stayPostedLater')?.addEventListener('click', () => {
      answer('later');
      card.hidden = true;
    });
    $('stayPostedStop')?.addEventListener('click', () => {
      answer('stop');
      card.querySelectorAll('.stay-posted__option, .stay-posted__items, .stay-posted__foot').forEach(node => { node.hidden = true; });
      setText('stayPostedStatus', 'Okay, we won’t ask again. The weekly email and notifications are in Settings → Notifications, and the calendar is under Coming up on the For you tab, if you change your mind.');
    });
  }

  async function refresh(force = false) {
    const card = $('stayPosted');
    if (!card) return;
    bindCard();
    const now = Date.now();
    if (!force && now - state.lastRefresh < REFRESH_GAP_MS) return;
    // Leave a card the member is answering right now alone.
    if (card.classList.contains('is-done') && !card.hidden) return;
    state.lastRefresh = now;
    const request = ++state.request;
    try {
      const data = await send('GET', '/api/stay-posted');
      if (request !== state.request) return;
      await render(data.ask);
    } catch (error) {
      // Optional card: the home screen works without it.
    }
  }

  function reset() {
    state.request += 1;
    state.ask = null;
    state.seen = '';
    state.lastRefresh = 0;
    state.calendar = null;
    if (state.observer) state.observer.disconnect();
    const card = $('stayPosted');
    if (card) {
      card.hidden = true;
      card.classList.remove('is-done');
    }
    document.querySelectorAll('.stay-note').forEach(node => node.remove());
  }

  // ------------------------------------------------ the note after saving a show

  function noticeStack() {
    let stack = $('appNotices');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'appNotices';
      stack.className = 'app-notices';
    }
    let host = document.body;
    try { host = document.querySelector('dialog:modal') || document.body; } catch (_) { /* older browsers */ }
    if (stack.parentNode !== host) host.appendChild(stack);
    return stack;
  }

  function showNote(offer) {
    document.querySelectorAll('.stay-note').forEach(node => node.remove());
    const note = document.createElement('div');
    note.className = 'app-notice app-notice--info stay-note';
    note.setAttribute('role', 'status');
    const body = document.createElement('div');
    body.className = 'stay-note__body';
    const text = document.createElement('p');
    text.className = 'stay-note__text';
    text.textContent = offer.text;
    const hint = document.createElement('p');
    hint.className = 'stay-note__hint';
    hint.textContent = offer.hint;
    const actions = document.createElement('div');
    actions.className = 'stay-note__actions';
    const yes = document.createElement('button');
    yes.type = 'button';
    yes.className = 'stay-note__yes';
    yes.textContent = offer.action;
    const later = document.createElement('button');
    later.type = 'button';
    later.className = 'stay-note__later';
    later.textContent = 'Not now';
    actions.append(yes, later);
    body.append(text, hint, actions);
    note.appendChild(body);
    const close = () => note.remove();
    // Stays a little longer than a plain notice, and never while the pointer or focus is on it.
    let timer = setTimeout(close, 20000);
    note.addEventListener('mouseenter', () => clearTimeout(timer));
    note.addEventListener('focusin', () => clearTimeout(timer));
    note.addEventListener('mouseleave', () => { clearTimeout(timer); timer = setTimeout(close, 8000); });
    later.addEventListener('click', () => { clearTimeout(timer); answer('later', 'after'); close(); });
    yes.addEventListener('click', async () => {
      clearTimeout(timer);
      yes.disabled = true;
      later.disabled = true;
      let ok = false;
      let message = '';
      try {
        if (offer.channel === 'push') {
          const result = await window.omniPush.turnOn('after_save');
          ok = result === 'on';
          if (result === 'blocked') message = 'Notifications are blocked for OmniTrackr in this browser’s settings.';
        } else {
          await send('PUT', '/api/for-you/email', { enabled: true, source: 'after_save' });
          ok = true;
        }
      } catch (error) {
        message = error.message;
      }
      if (ok) {
        answer(offer.channel, 'after');
        text.textContent = offer.channel === 'push'
          ? 'Done. You’ll get a notification on this device when a new episode is out.'
          : 'Done. The weekly email is on, and every one has a one-click unsubscribe.';
        hint.textContent = 'Settings → Notifications has the details.';
        actions.remove();
        timer = setTimeout(close, 6000);
        state.lastRefresh = 0;
        const card = $('stayPosted');
        if (card) card.hidden = true;
      } else {
        text.textContent = message || 'That didn’t work. You can turn it on later in Settings → Notifications.';
        actions.remove();
        timer = setTimeout(close, 8000);
      }
    });
    noticeStack().appendChild(note);
  }

  async function afterSave(category, title) {
    if (category !== 'tv-shows' && category !== 'anime') return;
    if (state.afterBusy) return;
    state.afterBusy = true;
    try {
      const push = await pushPossible();
      const data = await send('POST', '/api/stay-posted/after-save', { category, title: String(title || '').slice(0, 300), push });
      const offer = data && data.offer;
      if (!offer || (offer.channel === 'push' && !push)) return;
      // A beat after the "Added" notice, so the two don't land at once.
      setTimeout(() => showNote(offer), 900);
    } catch (error) {
      // Optional; saving already worked.
    } finally {
      state.afterBusy = false;
    }
  }

  function signedIn() {
    try { return typeof isAuthenticated === 'function' && isAuthenticated(); } catch (error) { return false; }
  }

  if (typeof window !== 'undefined') {
    window.OmniStayPosted = { refresh, reset, afterSave };
    // This file loads deferred, so the home screen's first refresh may have run before it was here.
    const first = () => { if (signedIn()) refresh(); };
    if (document.readyState === 'complete') first();
    else window.addEventListener('load', first);
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { dayLabel };
  }
})();
