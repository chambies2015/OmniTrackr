// Dashboard: the seasonal hub card ("The Halloween hub is open", "The Holiday hub is open"), shown only while
// a season is running and until the member hides it for the year. Progress is
// counted from the member's own library by GET /api/seasonal/current.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { request: 0, data: null };
  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function safePath(value) {
    return typeof value === 'string' && /^\/(?!\/)[a-z0-9/-]*$/.test(value) ? value : null;
  }

  function dismissKey(data) {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_season_hidden_${name}_${data.season}_${data.year}`;
  }

  function dismissed(data) {
    try { return localStorage.getItem(dismissKey(data)) === '1'; } catch (error) { return false; }
  }

  function daysText(days) {
    if (days <= 0) return 'Last day of the hub on your dashboard.';
    if (days === 1) return '1 day left.';
    return `${days} days left.`;
  }

  function summaryText(data) {
    const total = data.total || 0;
    const tracked = data.tracked || 0;
    const done = data.done || 0;
    if (!tracked) return `${data.card} ${daysText(data.days_left)}`;
    const finished = done ? `, ${done} finished` : '';
    return `${tracked} of ${total} picks in your library${finished}. ${daysText(data.days_left)}`;
  }

  function render(data) {
    state.data = data;
    const section = $('seasonCard');
    if (!section) return;
    const path = data && safePath(data.path);
    if (!data || !data.season || !path || dismissed(data)) {
      section.hidden = true;
      delete document.body.dataset.season;
      return;
    }
    section.dataset.seasonTheme = String(data.theme || '');
    document.body.dataset.season = String(data.theme || '');
    $('seasonCardEyebrow').textContent = `${data.name} ${data.year}`;
    $('seasonCardTitle').textContent = `The ${data.name} hub is open`;
    $('seasonCardSummary').textContent = summaryText(data);
    const open = $('seasonCardOpen');
    open.href = path;
    open.textContent = data.tracked ? 'Pick up where you left off' : String(data.cta || 'Open the hub');
    const shelves = $('seasonCardShelves');
    shelves.replaceChildren();
    (data.shelves || []).forEach(shelf => {
      if (!shelf || typeof shelf.key !== 'string' || !/^[a-z0-9-]{1,40}$/.test(shelf.key)) return;
      const link = document.createElement('a');
      link.className = 'season-card__shelf';
      link.href = `${path}#${shelf.key}`;
      const name = document.createElement('strong');
      name.textContent = String(shelf.name || '');
      const tagline = document.createElement('span');
      tagline.textContent = String(shelf.tagline || '');
      link.append(name, tagline);
      shelves.appendChild(link);
    });
    section.hidden = false;
  }

  async function refreshSeasonCard() {
    if (!$('seasonCard')) return;
    const request = ++state.request;
    try {
      const response = await fetch(`${apiBase()}/api/seasonal/current`, fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      render(data);
    } catch (error) {
      // The card is optional; the dashboard works without it.
    }
  }

  function resetSeasonCard() {
    state.request += 1;
    state.data = null;
    const section = $('seasonCard');
    if (section) section.hidden = true;
    if (document.body) delete document.body.dataset.season;
  }

  function init() {
    document.addEventListener('click', event => {
      const target = event.target.closest && event.target.closest('#seasonCardDismiss');
      if (!target || !state.data || !state.data.season) return;
      try { localStorage.setItem(dismissKey(state.data), '1'); } catch (error) { /* session only */ }
      render(state.data);
    });
  }

  if (typeof window !== 'undefined') {
    window.refreshSeasonCard = refreshSeasonCard;
    window.resetSeasonCard = resetSeasonCard;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { summaryText, daysText, safePath, dismissKey, render };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
