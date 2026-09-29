// Dashboard: one-click starter picks for new members and "Coming up for you".
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const STARTER_GOAL = 5;
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks',
  };
  const RADAR_TO_LIBRARY = { movies: 'movies', tv: 'tv-shows', anime: 'anime', games: 'video-games' };
  const state = { request: 0, libraryTotal: 0, added: 0, busy: new Set() };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');

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

  function storageKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) {
      // Fall back to a shared key.
    }
    return `omnitrackr_starter_picks_hidden_${name}`;
  }

  function starterDismissed() {
    try { return localStorage.getItem(storageKey()) === '1'; } catch (error) { return false; }
  }

  function dismissStarter() {
    try { localStorage.setItem(storageKey(), '1'); } catch (error) { /* session-only */ }
    $('starterPicks').hidden = true;
  }

  function friendlyDate(iso) {
    if (!iso) return 'Date to be announced';
    const date = new Date(`${iso}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return 'Date to be announced';
    const today = new Date();
    const days = Math.round((date - Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate(), 12)) / 86400000);
    const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
    if (days === 0) return `Today · ${label}`;
    if (days === 1) return `Tomorrow · ${label}`;
    if (days > 1 && days < 7) return `In ${days} days · ${label}`;
    if (days < 0) return `Out now · ${label}`;
    return label;
  }

  function art(image, title) {
    const frame = el('div', 'for-you-item__art');
    if (image) {
      const img = document.createElement('img');
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.replaceWith(el('span', 'for-you-item__initial', (title || '?').slice(0, 1).toUpperCase())));
      frame.appendChild(img);
    } else {
      frame.appendChild(el('span', 'for-you-item__initial', (title || '?').slice(0, 1).toUpperCase()));
    }
    return frame;
  }

  function itemCard({ image, title, meta, note, action, link }) {
    const card = el('article', 'for-you-item');
    card.appendChild(art(image, title));
    const body = el('div', 'for-you-item__body');
    const heading = el('h4', 'for-you-item__title');
    heading.title = title;
    if (link) {
      const anchor = el('a', '', title);
      anchor.href = link;
      heading.appendChild(anchor);
    } else {
      heading.textContent = title;
    }
    body.append(heading, el('p', 'for-you-item__meta', meta));
    if (note) body.appendChild(el('p', 'for-you-item__note', note));
    if (action) body.appendChild(action);
    card.appendChild(body);
    return card;
  }

  function addButton(label, onAdd) {
    const button = el('button', 'for-you-item__add', label);
    button.type = 'button';
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      button.textContent = 'Adding…';
      const ok = await onAdd();
      button.textContent = ok ? '✓ Added' : label;
      button.classList.toggle('is-added', ok);
      button.disabled = ok;
    });
    return button;
  }

  function refreshLibrary(category) {
    const loader = window[LOADERS[category]] || (typeof globalThis[LOADERS[category]] === 'function' ? globalThis[LOADERS[category]] : null);
    try {
      if (typeof loader === 'function') loader();
    } catch (error) {
      // The list refreshes on the next visit.
    }
    if (typeof scheduleLibraryLaunchpadRefresh === 'function') {
      try { scheduleLibraryLaunchpadRefresh(); } catch (error) { /* optional */ }
    }
  }

  function updateProgress() {
    const total = state.libraryTotal + state.added;
    const progress = $('starterPicksProgress');
    if (!progress) return;
    progress.textContent = total >= STARTER_GOAL ? `${total} titles saved — nice start!` : `${total} of ${STARTER_GOAL} titles saved`;
    progress.classList.toggle('is-done', total >= STARTER_GOAL);
  }

  async function postJson(path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    return { ok: response.ok, data };
  }

  async function addPopular(pick) {
    const { ok, data } = await postJson('/api/for-you/starter-picks/add', { category: pick.category, title: pick.title });
    return afterAdd(ok, data, pick.category, pick.title);
  }

  async function addRadar(card) {
    const { ok, data } = await postJson('/api/release-radar/save', { category: card.category, window: card.window, key: card.key });
    return afterAdd(ok, data, RADAR_TO_LIBRARY[card.category], card.title);
  }

  function afterAdd(ok, data, category, title) {
    const status = $('starterPicksStatus');
    if (!ok) {
      if (status) status.textContent = data.detail || `Couldn't add ${title}. Please try again.`;
      return false;
    }
    if (data.state === 'created') state.added += 1;
    if (status) status.textContent = data.state === 'existing' ? `${title} was already in your library.` : `Added ${title} to your library.`;
    updateProgress();
    refreshLibrary(category);
    return true;
  }

  function renderStarter(data) {
    const section = $('starterPicks');
    state.libraryTotal = Number(data.library_total || 0);
    state.added = 0;
    const popular = $('starterPicksPopular');
    const upcoming = $('starterPicksUpcoming');
    popular.replaceChildren();
    upcoming.replaceChildren();
    (data.popular || []).slice(0, 12).forEach(pick => {
      const meta = [pick.label, pick.year, pick.creator].filter(Boolean).join(' · ');
      popular.appendChild(itemCard({
        image: pick.image, title: pick.title, meta,
        note: `Saved by ${pick.members} members`,
        action: addButton('Add', () => addPopular(pick)),
      }));
    });
    (data.upcoming || []).slice(0, 6).forEach(card => {
      upcoming.appendChild(itemCard({
        image: card.image, title: card.title, meta: `${card.label} · ${friendlyDate(card.date)}`,
        link: card.url, action: addButton('Want to see', () => addRadar(card)),
      }));
    });
    $('starterPicksUpcomingTitle').hidden = !(data.upcoming || []).length;
    popular.hidden = !(data.popular || []).length;
    $('starterPicksStatus').textContent = '';
    updateProgress();
    section.hidden = !(data.popular || []).length && !(data.upcoming || []).length;
  }

  function renderComingUp(data) {
    const section = $('comingUp');
    const list = $('comingUpList');
    list.replaceChildren();
    const matches = data.matches || [];
    const popular = data.popular || [];
    if (!data.library_total || (!matches.length && !popular.length)) {
      section.hidden = true;
      return;
    }
    const summary = $('comingUpSummary');
    if (matches.length) {
      summary.textContent = `${matches.length} new release${matches.length === 1 ? '' : 's'} connected to titles you track.`;
    } else {
      summary.textContent = "Nothing from your library is on the schedule right now. Here's what's popular instead.";
    }
    const cards = matches.length ? matches.concat(popular.slice(0, Math.max(0, 6 - matches.length))) : popular;
    cards.forEach(card => {
      const fromLibrary = Boolean(card.reason);
      list.appendChild(itemCard({
        image: card.image, title: card.title,
        meta: `${card.label} · ${friendlyDate(card.date)}`,
        note: card.reason || (card.details || [])[0] || '',
        link: card.url,
        action: fromLibrary ? null : addButton('Want to see', () => addRadar(card)),
      }));
    });
    renderEmail(data.email || {});
    section.hidden = false;
  }

  function renderEmail(email) {
    const wrap = $('comingUpEmail');
    const toggle = $('comingUpEmailToggle');
    if (!wrap || !toggle) return;
    wrap.hidden = !email.available && !email.enabled;
    toggle.checked = Boolean(email.enabled);
  }

  async function saveEmail(event) {
    const toggle = event.target;
    const status = $('comingUpStatus');
    toggle.disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/for-you/email`, fetchOptions({
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: toggle.checked }),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        toggle.checked = !toggle.checked;
        status.textContent = data.detail || 'Could not update the weekly email. Please try again.';
      } else {
        toggle.checked = Boolean(data.enabled);
        status.textContent = data.enabled
          ? 'Weekly email on. Your first one arrives within a day; every email has a one-click unsubscribe.'
          : 'Weekly email off.';
      }
    } catch (error) {
      toggle.checked = !toggle.checked;
      status.textContent = 'Could not update the weekly email. Please try again.';
    } finally {
      toggle.disabled = false;
    }
  }

  async function getJson(path) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions());
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function refreshForYou() {
    const request = ++state.request;
    if (!$('starterPicks') || !$('comingUp')) return;
    try {
      const comingUp = await getJson('/api/for-you/coming-up');
      if (request !== state.request) return;
      let starterShown = false;
      // Starter picks count every category; coming-up counts only radar ones, so ask separately.
      if (!starterDismissed()) {
        const picks = await getJson('/api/for-you/starter-picks');
        if (request !== state.request) return;
        if (Number(picks.library_total || 0) < STARTER_GOAL) {
          renderStarter(picks);
          starterShown = !$('starterPicks').hidden;
        } else {
          $('starterPicks').hidden = true;
        }
      } else {
        $('starterPicks').hidden = true;
      }
      // While quick start is showing its own release picks, only show real library matches here.
      renderComingUp(starterShown ? { ...comingUp, popular: [] } : comingUp);
    } catch (error) {
      // Suggestions are optional; the library works without them.
    }
  }

  function resetForYou() {
    state.request += 1;
    ['starterPicks', 'comingUp'].forEach(id => { const node = $(id); if (node) node.hidden = true; });
  }

  function init() {
    document.addEventListener('click', event => {
      const target = event.target.closest && event.target.closest('[data-for-you-action="dismiss-starter"]');
      if (target) dismissStarter();
    });
    const toggle = $('comingUpEmailToggle');
    if (toggle) toggle.addEventListener('change', saveEmail);
  }

  window.refreshForYou = refreshForYou;
  window.resetForYou = resetForYou;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { friendlyDate, renderStarter, renderComingUp, state, STARTER_GOAL };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
