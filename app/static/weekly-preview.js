// "Your weekly email": a peek at what this member's weekly email would say this week, shown in place
// (Settings → Notifications, the For you invites and the home "stay posted" card). The server builds it
// with the same code as the real email (GET /api/weekly-email/preview); nothing is sent unless the member
// presses "Send me this week's", and nothing is switched on unless they press "Email me this every week".
// Hosts are any element with data-weekly-preview="<place>"; it fills in the first time it becomes visible.
// data-weekly-actions="copy" leaves the subscribe button to the host (it already has one).
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const PLACES = ['settings', 'for_you', 'home_card'];
  const state = { observer: null, hosts: new Set(), data: null, loadedAt: 0, pending: null, flash: '' };
  const FRESH_MS = 2 * 60 * 1000;

  function options(extra = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(extra);
    return { credentials: 'same-origin', ...extra };
  }

  function apiBase() {
    return typeof API_BASE === 'string' ? API_BASE : '';
  }

  async function send(method, url, body) {
    const response = await fetch(`${apiBase()}${url}`, options({
      method,
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data && data.detail;
      const error = new Error(typeof detail === 'string' ? detail
        : (detail && typeof detail.message === 'string' ? detail.message : 'That didn’t work. Please try again.'));
      error.reason = detail && detail.reason;
      throw error;
    }
    return data;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function safePath(url) {
    return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') ? url : '';
  }

  function safeImage(url) {
    return typeof url === 'string' && /^https:\/\//.test(url) ? url : '';
  }

  function and(list) {
    if (list.length < 2) return list.join('');
    return `${list.slice(0, -1).join(', ')} and ${list[list.length - 1]}`;
  }

  function dayText(iso) {
    const when = new Date(iso);
    if (Number.isNaN(when.getTime())) return '';
    return when.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function placeOf(host) {
    const place = host.dataset.weeklyPreview;
    return PLACES.includes(place) ? place : 'settings';
  }

  async function load(place, fresh) {
    if (!fresh && state.data && Date.now() - state.loadedAt < FRESH_MS) return state.data;
    if (state.pending) return state.pending;
    state.pending = send('GET', `/api/weekly-email/preview?place=${encodeURIComponent(place)}`)
      .then(data => { state.data = data; state.loadedAt = Date.now(); return data; })
      .finally(() => { state.pending = null; });
    return state.pending;
  }

  // ------------------------------------------------ drawing

  function item(line) {
    const row = el('li', `wk-peek__item wk-peek__item--${line.section}`);
    const image = safeImage(line.image);
    if (image) {
      const poster = el('img', 'wk-peek__poster');
      poster.src = image;
      poster.alt = '';
      poster.loading = 'lazy';
      poster.decoding = 'async';
      poster.referrerPolicy = 'no-referrer';
      poster.addEventListener('error', () => poster.replaceWith(el('span', 'wk-peek__dot')), { once: true });
      row.append(poster);
    } else {
      row.append(el('span', 'wk-peek__dot'));
    }
    const body = el('div', 'wk-peek__line');
    body.append(el('span', 'wk-peek__kicker', line.heading));
    const href = safePath(line.url);
    if (href) {
      const link = el('a', 'wk-peek__title', line.title);
      link.href = href;
      body.append(link);
    } else {
      body.append(el('span', 'wk-peek__title', line.title));
    }
    const bits = [line.detail, line.note].filter(Boolean).join(' · ');
    if (bits) body.append(el('span', 'wk-peek__detail', bits));
    row.append(body);
    return row;
  }

  function moreText(data) {
    const parts = [];
    if (data.more) parts.push(`${data.more} more line${data.more === 1 ? '' : 's'}`);
    if (Array.isArray(data.also) && data.also.length) parts.push(and(data.also.slice(0, 3)));
    return parts.length ? `Also in it: ${and(parts)}.` : '';
  }

  function arrival(data) {
    if (data.subscribed) {
      return data.last_sent_at ? `Your next one · last sent ${dayText(data.last_sent_at)}` : 'Your first one · on its way within a day';
    }
    return 'What yours would say this week';
  }

  function render(host, data) {
    const place = placeOf(host);
    if (!data.available) {
      host.hidden = true;  // email isn't set up on this server: nothing to offer
      host.dataset.weeklyPreviewState = 'ready';
      return;
    }
    const hostActions = host.dataset.weeklyActions === 'copy';
    const box = el('div', 'wk-peek');
    box.setAttribute('role', 'group');
    box.setAttribute('aria-label', 'Preview of your weekly email');

    const mail = el('div', 'wk-peek__mail');
    const from = el('div', 'wk-peek__from');
    from.append(el('span', 'wk-peek__badge', 'OT'));
    const who = el('span', 'wk-peek__who');
    who.append(el('strong', '', 'OmniTrackr weekly'), document.createTextNode(` · ${arrival(data)}`));
    from.append(who);
    mail.append(from);

    if (data.subject) mail.append(el('p', 'wk-peek__subject', data.subject));
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length) {
      const list = el('ul', 'wk-peek__items');
      items.forEach(line => list.append(item(line)));
      mail.append(list);
      const more = moreText(data);
      if (more) mail.append(el('p', 'wk-peek__more', more));
    } else {
      mail.append(el('p', 'wk-peek__empty', 'Nothing to put in it yet. Save a show you\'re watching or a movie that\'s coming out and this fills in.'));
    }
    box.append(mail);

    if (items.length && !data.personal) {
      box.append(el('p', 'wk-peek__lead', 'Nothing you track has news this week, so yours would be the monthly round-up. Save a show that\'s airing or a release that\'s coming and it lists yours instead.'));
    } else if (data.refreshing) {
      box.append(el('p', 'wk-peek__lead', 'Checking your shows for new episode dates. They show up here in a minute or two.'));
    }

    const actions = el('div', 'wk-peek__actions');
    const status = el('p', 'wk-peek__status', state.flash || '');
    state.flash = '';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    if (data.available && !data.subscribed && !hostActions && items.length) {
      const yes = el('button', 'wk-peek__yes', 'Email me this every week');
      yes.type = 'button';
      yes.addEventListener('click', () => subscribe(yes, status));
      actions.append(yes);
    }
    const copy = data.copy || {};
    if (data.available && !data.subscribed && items.length) {
      const button = el('button', 'wk-peek__copy', copy.can ? 'Send me this week\'s' : 'Copy sent');
      button.type = 'button';
      if (copy.can) button.addEventListener('click', () => sendCopy(button, status));
      else button.disabled = true;
      actions.append(button);
      if (!copy.can && copy.reason === 'recent' && copy.sent_at) {
        status.textContent = `We sent you a copy on ${dayText(copy.sent_at)}. You can ask for another after ${dayText(copy.again_at)}.`;
      } else if (!copy.can && copy.reason === 'verify') {
        button.hidden = true;
        status.textContent = 'Verify your email address and you can get a copy or turn it on.';
      }
    }
    const full = el('a', 'wk-peek__full', data.subscribed ? 'Open the full email' : 'See the whole email');
    full.href = '/email/weekly/preview';
    full.target = '_blank';
    full.rel = 'noopener';
    actions.append(full);
    box.append(actions, status);

    host.replaceChildren(box);
    host.dataset.weeklyPreviewState = 'ready';
    host.dataset.weeklyPreviewPlace = place;
  }

  function renderError(host, message) {
    const box = el('p', 'wk-peek__status wk-peek__status--error', message);
    host.replaceChildren(box);
    host.dataset.weeklyPreviewState = 'error';
  }

  // ------------------------------------------------ buttons

  function announce(enabled) {
    try { document.dispatchEvent(new CustomEvent('omni:weekly-email', { detail: { enabled, from: 'preview' } })); } catch (error) { /* old browsers */ }
  }

  async function subscribe(button, status) {
    button.disabled = true;
    status.textContent = 'Turning it on…';
    try {
      await send('PUT', '/api/for-you/email', { enabled: true, source: 'preview' });
      state.flash = 'Weekly email on. The first one comes within a day when something here is new, and every email has a one-click unsubscribe.';
      status.textContent = state.flash;
      if (state.data) state.data = { ...state.data, subscribed: true };
      announce(true);
      redrawAll(false);
    } catch (error) {
      button.disabled = false;
      status.textContent = error.message;
    }
  }

  async function sendCopy(button, status) {
    button.disabled = true;
    status.textContent = 'Sending…';
    try {
      const result = await send('POST', '/api/weekly-email/copy');
      button.textContent = 'Copy sent';
      status.textContent = `Sent. Look in your inbox for “${result.subject || 'Coming up for you'}”. If you like it, the button inside turns it on every week.`;
      if (state.data) state.data = { ...state.data, copy: result.copy || { can: false, reason: 'recent' } };
    } catch (error) {
      if (error.reason === 'recent' || error.reason === 'subscribed') button.textContent = 'Copy sent';
      else button.disabled = false;
      status.textContent = error.message;
    }
  }

  // ------------------------------------------------ hosts

  async function fill(host, fresh) {
    if (!host || host.dataset.weeklyPreviewState === 'loading') return;
    host.dataset.weeklyPreviewState = 'loading';
    if (!host.firstChild) host.append(el('p', 'wk-peek__status', 'Building your preview…'));
    try {
      render(host, await load(placeOf(host), fresh));
    } catch (error) {
      renderError(host, error.message || 'Couldn’t build your preview just now.');
    }
  }

  function redrawAll(fresh) {
    state.hosts.forEach(host => {
      if (host.dataset.weeklyPreviewState === 'ready' && state.data && !fresh) render(host, state.data);
      else if (host.dataset.weeklyPreviewState) fill(host, fresh);
    });
  }

  function watch(host) {
    if (state.hosts.has(host)) return;
    state.hosts.add(host);
    if (!('IntersectionObserver' in window)) { fill(host, false); return; }
    if (!state.observer) {
      state.observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting && !entry.target.dataset.weeklyPreviewState) fill(entry.target, false);
        });
      }, { rootMargin: '120px' });
    }
    state.observer.observe(host);
  }

  function scan() {
    if (typeof document.querySelectorAll !== 'function') return;
    document.querySelectorAll('[data-weekly-preview]').forEach(watch);
  }

  // Saving or removing a title changes what the email would say: draw it again next time it's looked at.
  function stale() {
    state.data = null;
    state.hosts.forEach(host => { if (host.dataset.weeklyPreviewState === 'ready') delete host.dataset.weeklyPreviewState; });
  }

  window.OmniWeeklyPreview = { scan, fill: host => fill(host, true), stale, render };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan, { once: true });
  else scan();
  // Turned on or off in another place (Settings, the home card): draw what that means here.
  document.addEventListener('omni:weekly-email', event => {
    if (!event.detail || event.detail.from === 'preview') return;
    state.data = null;
    state.hosts.forEach(host => { if (host.dataset.weeklyPreviewState === 'ready') fill(host, true); });
  });
})();
