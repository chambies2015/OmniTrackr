// "Save before you sign up": a visitor's list of titles, kept only in this browser.
// Homepage tiles and title pages add to it; after sign-up the dashboard moves it
// into the new library (POST /api/guest-list/import) and clears it.
(function () {
  'use strict';

  const KEY = 'omnitrackr_guest_list';
  const MAX = 30;
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book']);
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const LOADERS = ['loadMovies', 'loadTVShows', 'loadAnime', 'loadVideoGames', 'loadMusic', 'loadBooks'];

  function valid(item) {
    return item && KINDS.has(item.kind) && SLUG.test(item.slug || '') && typeof item.title === 'string';
  }

  function read() {
    try {
      const list = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(list) ? list.filter(valid).slice(0, MAX) : [];
    } catch (error) {
      return [];
    }
  }

  function write(list) {
    try {
      if (list.length) localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX)));
      else localStorage.removeItem(KEY);
      return true;
    } catch (error) {
      return false;
    }
  }

  function has(list, kind, slug) {
    return list.some(item => item.kind === kind && item.slug === slug);
  }

  function add(kind, slug, title) {
    const list = read();
    if (has(list, kind, slug)) return { list, added: false };
    if (list.length >= MAX) return { list, added: false, full: true };
    const item = { kind, slug, title: String(title || '').slice(0, 200) };
    if (!valid(item)) return { list, added: false };
    list.push(item);
    if (!write(list)) return { list: read(), added: false, storageError: true };
    report('guest_pick_added');
    return { list, added: true };
  }

  function remove(kind, slug) {
    const list = read().filter(item => !(item.kind === kind && item.slug === slug));
    return write(list) ? list : read();
  }

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') {
      window.reportFunnelEvent(event);
      return;
    }
    if (report.sent && report.sent.has(event)) return;
    report.sent = report.sent || new Set();
    report.sent.add(event);
    try {
        // A beacon never delays the page or navigation.
        if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
            navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
        }
    } catch (error) { /* analytics only */ }
  }

  function countText(count) {
    return count === 1 ? '1 title on your list' : `${count} titles on your list`;
  }

  // ------------------------------------------------------------ homepage tiles
  function setupTiles() {
    const tiles = Array.from(document.querySelectorAll('[data-guest-kind][data-guest-slug]:not([data-guest-save])'));
    if (!tiles.length) return;
    const bar = document.querySelector('[data-guest-bar]');
    const counter = document.querySelector('[data-guest-count]');
    const refresh = () => {
      const list = read();
      tiles.forEach(tile => {
        tile.setAttribute('aria-pressed', String(has(list, tile.dataset.guestKind, tile.dataset.guestSlug)));
      });
      if (bar) bar.hidden = list.length === 0;
      if (counter) counter.textContent = list.length ? `${countText(list.length)}. Create a free account to keep it.` : '';
    };
    tiles.forEach(tile => tile.addEventListener('click', () => {
      const { guestKind: kind, guestSlug: slug, guestTitle: title } = tile.dataset;
      if (has(read(), kind, slug)) remove(kind, slug);
      else add(kind, slug, title);
      refresh();
    }));
    refresh();
  }

  // ------------------------------------------------------------ title pages (guests)
  function setupTitleButtons() {
    document.querySelectorAll('[data-guest-save]').forEach(button => {
      const { guestKind: kind, guestSlug: slug, guestTitle: title } = button.dataset;
      const status = document.querySelector('.title-hero__status');
      const show = saved => {
        button.textContent = saved ? 'Saved to your list ✓' : 'Save to my list';
        button.setAttribute('aria-pressed', String(saved));
        if (status) {
          status.textContent = saved
            ? `${countText(read().length)}. Create a free account to keep it — it moves into your library when you log in.`
            : '';
        }
      };
      button.addEventListener('click', () => {
        const saved = has(read(), kind, slug);
        const result = saved ? remove(kind, slug) : add(kind, slug, title);
        const persisted = has(read(), kind, slug);
        show(persisted);
        if (status && !saved && !persisted) status.textContent = result.full
          ? 'Your list is full (30 titles). Remove a title before saving another.'
          : 'This browser could not save your list. Enable browser storage and try again.';
      });
      show(has(read(), kind, slug));
    });
  }

  // ------------------------------------------------------------ dashboard import
  function signedInDashboard() {
    if (document.documentElement.dataset.publicShell === 'true') return false;
    try { return typeof getUser === 'function' && !!getUser(); } catch (error) { return false; }
  }

  function toast(message) {
    const node = document.createElement('div');
    node.className = 'guest-import-toast';
    node.setAttribute('role', 'status');
    node.textContent = message;
    document.body.appendChild(node);
    setTimeout(() => node.remove(), 7000);
  }

  async function importList() {
    const list = read();
    if (!list.length || !signedInDashboard()) return null;
    const options = { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: list.map(({ kind, slug }) => ({ kind, slug })) }) };
    const base = typeof API_BASE === 'string' ? API_BASE : '';
    let response;
    try {
      response = await fetch(`${base}/api/guest-list/import`,
        typeof authFetchOptions === 'function' ? authFetchOptions(options) : { credentials: 'same-origin', ...options });
    } catch (error) {
      return null; // Try again next visit.
    }
    if (!response.ok) {
      if (response.status === 422 || response.status === 400) write([]);
      return null;
    }
    const result = await response.json().catch(() => null);
    if (!result || !Array.isArray(result.added) || !Array.isArray(result.existing)) return null;
    // Preserve titles saved in another tab while this request was running.
    write(read().filter(item => !has(list, item.kind, item.slug)));
    if (result) {
      const added = (result.added || []).length;
      if (added) {
        toast(`Added ${added} title${added === 1 ? '' : 's'} from the list you saved before signing up.`);
        LOADERS.forEach(name => { if (typeof window[name] === 'function') { try { window[name](); } catch (error) { /* ignore */ } } });
        if (typeof window.refreshForYou === 'function') window.refreshForYou();
      }
    }
    return result;
  }

  function init() {
    setupTiles();
    setupTitleButtons();
    setTimeout(importList, 800);
  }

  const api = { read, write, add, remove, importList, KEY, MAX };
  window.OmniGuestList = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
