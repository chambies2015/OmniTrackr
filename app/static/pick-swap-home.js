// "Pick swap" on the member home: each swap the member is in, where it stands and the next thing to do
// (invite people, pick for the person they drew, unwrap). The card only shows while they're in one;
// the swaps themselves live on /swap (pick-swap.js, app/pick_swap.py). Server text is only set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 30 * 1000;
  const SHOWN = 3;
  const state = { epoch: 0, request: null, loadedAt: 0 };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
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

  function safePath(path) {
    return typeof path === 'string' && /^\/swap\/\d{1,10}$/.test(path) ? path : '/swap';
  }

  // What the card shows: urgent ones first (they come sorted), at most three.
  function shown(data) {
    const swaps = data && Array.isArray(data.swaps) ? data.swaps : [];
    return swaps.slice(0, SHOWN);
  }

  function row(swap) {
    const item = el('li', `swap-home__item${swap.urgent ? ' swap-home__item--urgent' : ''}`);
    item.dataset.state = String(swap.state || '');
    const box = el('span', 'swap-home__box');
    box.setAttribute('aria-hidden', 'true');
    item.appendChild(box);
    const body = el('div', 'swap-home__body');
    const name = el('a', 'swap-home__name', swap.name);
    name.href = safePath(swap.path);
    body.appendChild(name);
    body.appendChild(el('p', 'swap-home__line', swap.line));
    item.appendChild(body);
    if (swap.action) {
      const go = el('a', `swap-home__go${swap.urgent ? ' swap-home__go--urgent' : ''}`, swap.action.label);
      go.href = safePath(swap.action.path);
      item.appendChild(go);
    }
    return item;
  }

  function render(data) {
    const section = $('swapHome');
    const list = $('swapHomeList');
    if (!section || !list) return;
    const swaps = shown(data);
    if (!swaps.length) {
      section.hidden = true;
      list.replaceChildren();
      return;
    }
    list.replaceChildren(...swaps.map(row));
    const total = Array.isArray(data.swaps) ? data.swaps.length : 0;
    const more = section.querySelector('.swap-home__more');
    if (more) more.textContent = total > SHOWN ? `All ${total} swaps` : 'All swaps';
    section.hidden = false;
    if (window.OmniHomeLayout && typeof window.OmniHomeLayout.schedule === 'function') window.OmniHomeLayout.schedule();
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/swaps?tz=${encodeURIComponent(tz())}`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.request = null;
    state.loadedAt = 0;
    const section = $('swapHome');
    if (section) section.hidden = true;
    $('swapHomeList')?.replaceChildren();
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { safePath, shown, state };
  }
  if (typeof document === 'undefined') return;

  // The dashboard's first batch of cards can run before this deferred script, so ask once here too.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => refresh(), { once: true });
  else refresh();

  window.OmniSwapHome = { refresh, reset, render };
})();
