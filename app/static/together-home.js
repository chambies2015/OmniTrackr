// "Watch together" on the member home: each plan the member shares with friends, where everyone is,
// this week's stretch, and a button that moves them one episode or chapter on. The card only shows
// while a plan is running; the plans themselves live on /together (together.js, app/together.py).
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 20 * 1000;
  const SHOWN = 3;
  const state = { epoch: 0, data: null, request: null, loadedAt: 0, busy: false };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  // Minutes east of UTC, so "this week" follows the member's own clock.
  const tz = () => -new Date().getTimezoneOffset();

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function letterOf(title) {
    return (String(title || '').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase();
  }

  function safePath(path) {
    return typeof path === 'string' && /^\/together\/\d+$/.test(path) ? path : '/together';
  }

  // Where the bar's pieces sit, as percentages of the whole plan: this week's stretch and each person.
  function trackParts(plan) {
    const total = Math.max(1, Number(plan.total) || 1);
    const pct = value => Math.round(Math.max(0, Math.min(total, Number(value) || 0)) / total * 1000) / 10;
    const parts = { week: null, you: 0, people: [] };
    const first = Number(plan.week_first);
    const last = Number(plan.week_last);
    if (plan.started && first > 0 && last >= first) parts.week = { from: pct(first - 1), to: pct(last) };
    const shared = new Map();
    (Array.isArray(plan.people) ? plan.people : []).forEach(person => {
      const at = pct(person.position);
      if (person.you) parts.you = at;
      // People on the same episode sit side by side instead of hiding each other.
      const stack = shared.get(at) || 0;
      shared.set(at, stack + 1);
      parts.people.push({ at, stack, you: Boolean(person.you), initials: String(person.initials || '?').slice(0, 2), name: String(person.username || '') });
    });
    return parts;
  }

  function savedLine(label, opened) {
    const said = String(label || 'Saved');
    const done = `Saved: ${said.charAt(0).toLowerCase()}${said.slice(1)}.`;
    const count = Number(opened) || 0;
    if (!count) return done;
    return `${done} ${count === 1 ? 'A note from a friend just opened.' : `${count} notes from friends just opened.`}`;
  }

  function unreadWords(count) {
    const n = Number(count) || 0;
    return n === 1 ? '1 new note' : `${n} new notes`;
  }

  function cover(plan) {
    const link = el('a', 'together-home__cover');
    link.href = safePath(plan.path);
    link.tabIndex = -1;
    link.setAttribute('aria-hidden', 'true');
    const image = typeof plan.image === 'string' && /^https:\/\//.test(plan.image) ? plan.image : '';
    const letter = () => {
      link.classList.add('together-home__cover--letter');
      link.textContent = letterOf(plan.title);
    };
    if (!image) { letter(); return link; }
    const img = el('img');
    img.src = image;
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.referrerPolicy = 'no-referrer';
    img.width = 64;
    img.height = 96;
    img.addEventListener('error', () => { img.remove(); letter(); }, { once: true });
    link.appendChild(img);
    return link;
  }

  function track(plan) {
    const parts = trackParts(plan);
    const bar = el('div', 'together-home__track');
    bar.setAttribute('role', 'img');
    const where = (Array.isArray(plan.people) ? plan.people : [])
      .map(person => `${person.you ? 'you' : person.username} at ${Number(person.position) || 0}`).join(', ');
    bar.setAttribute('aria-label', `Out of ${plan.total}: ${where}`);
    if (parts.week) {
      const week = el('span', 'together-home__week');
      week.style.left = `${parts.week.from}%`;
      week.style.width = `${Math.max(0, parts.week.to - parts.week.from)}%`;
      bar.appendChild(week);
    }
    const fill = el('span', 'together-home__fill');
    fill.style.width = `${parts.you}%`;
    bar.appendChild(fill);
    parts.people.forEach(person => {
      const dot = el('span', `together-home__dot${person.you ? ' together-home__dot--you' : ''}`, person.initials);
      dot.style.left = `${person.at}%`;
      if (person.stack) dot.style.marginLeft = `${person.stack * 20}px`;
      dot.title = person.you ? 'You' : person.name;
      bar.appendChild(dot);
    });
    return bar;
  }

  function row(plan) {
    const item = el('li', 'together-home__plan');
    item.dataset.status = String(plan.status || '');
    item.appendChild(cover(plan));
    const body = el('div', 'together-home__body');
    const name = el('p', 'together-home__name');
    const link = el('a', null, plan.title);
    link.href = safePath(plan.path);
    name.appendChild(link);
    const meta = [plan.scope || plan.label, plan.started ? `Week ${plan.week} of ${plan.weeks_total}` : '', plan.with]
      .filter(Boolean).join(' · ');
    if (meta) name.appendChild(el('small', null, meta));
    body.appendChild(name);
    if (plan.headline) body.appendChild(el('p', 'together-home__line', plan.headline));
    body.appendChild(track(plan));
    const actions = el('div', 'together-home__actions');
    if (plan.next_label) {
      const next = el('button', 'together-home__next', plan.next_label);
      next.type = 'button';
      next.dataset.planId = String(plan.id);
      next.dataset.position = String((Number(plan.position) || 0) + 1);
      actions.appendChild(next);
    }
    const open = el('a', 'together-home__open', 'Open');
    open.href = safePath(plan.path);
    if (Number(plan.unread) > 0) {
      open.textContent = `Open · ${unreadWords(plan.unread)}`;
      open.classList.add('together-home__open--new');
    }
    actions.appendChild(open);
    body.appendChild(actions);
    item.appendChild(body);
    return item;
  }

  function render(data) {
    state.data = data;
    const section = $('togetherHome');
    const list = $('togetherHomeList');
    if (!section || !list) return;
    const running = data && Array.isArray(data.running) ? data.running : [];
    if (!running.length) {
      section.hidden = true;
      list.replaceChildren();
      return;
    }
    list.replaceChildren(...running.slice(0, SHOWN).map(row));
    const more = section.querySelector('.together-home__more');
    if (more) more.textContent = running.length > SHOWN ? `All ${running.length} plans` : 'All plans';
    section.hidden = false;
    if (window.OmniHomeLayout && typeof window.OmniHomeLayout.schedule === 'function') window.OmniHomeLayout.schedule();
  }

  function setStatus(text) {
    const node = $('togetherHomeStatus');
    if (node) node.textContent = text || '';
  }

  async function step(button) {
    if (state.busy) return;
    const planId = Number(button.dataset.planId);
    const position = Number(button.dataset.position);
    if (!Number.isSafeInteger(planId) || planId <= 0 || !Number.isSafeInteger(position) || position < 0) return;
    state.busy = true;
    button.disabled = true;
    setStatus('');
    const label = button.textContent;
    const epoch = state.epoch;
    try {
      const response = await fetch(`${apiBase()}/api/together/${planId}/position?card=1&tz=${encodeURIComponent(tz())}`, fetchOptions({
        method: 'PUT',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ position }),
      }));
      let data = {};
      try { data = await response.json(); } catch (error) { data = {}; }
      if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
        throw new Error(typeof detail === 'string' ? detail : 'That didn’t save. Please try again.');
      }
      if (epoch !== state.epoch) return;
      state.loadedAt = Date.now();
      render(data);
      setStatus(savedLine(label, data.opened));
      // The library moved forward too, so Continue shows the new episode or chapter.
      if (data.library_saved && typeof window.refreshLibraryPulse === 'function') {
        Promise.resolve(window.refreshLibraryPulse()).catch(() => {});
      }
    } catch (error) {
      setStatus(error.message);
      if (button.isConnected) button.disabled = false;
    } finally {
      state.busy = false;
    }
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/together?tz=${encodeURIComponent(tz())}`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.data = null;
    state.request = null;
    state.loadedAt = 0;
    state.busy = false;
    const section = $('togetherHome');
    if (section) section.hidden = true;
    $('togetherHomeList')?.replaceChildren();
    setStatus('');
  }

  function wire() {
    $('togetherHomeList')?.addEventListener('click', event => {
      const button = event.target.closest('.together-home__next');
      if (button && !button.disabled) step(button);
    });
    // The dashboard's first batch of cards can run before this deferred script, so ask once here too.
    refresh();
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { trackParts, savedLine, unreadWords, safePath, state };
  }
  if (typeof document === 'undefined') return;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  window.OmniTogether = { refresh, reset, render };
})();
