// Dashboard: one-click starter picks for new members and "Coming up for you".
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const STARTER_GOAL = 5;
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const RADAR_TO_LIBRARY = { movies: 'movies', tv: 'tv-shows', anime: 'anime', games: 'video-games' };
  const state = { request: 0, libraryTotal: 0, added: 0, busy: new Set(), email: {}, calendar: {} };

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

  // ---------------------------------------------------------- weekly email invite
  // Offered where members are engaged: once Quick start reaches its goal, and on the
  // "Coming up for you" card. Always opt-in; "Not now" hides it on this device.

  function weeklyKey() {
    return storageKey().replace('starter_picks_hidden', 'weekly_invite_hidden');
  }

  function weeklyDismissed() {
    try { return localStorage.getItem(weeklyKey()) === '1'; } catch (error) { return false; }
  }

  function canInvite() {
    return Boolean(state.email.available) && !state.email.enabled && !weeklyDismissed();
  }

  function renderInvites() {
    const find = selector => (typeof document.querySelector === 'function' ? document.querySelector(selector) : null);
    const starter = find('[data-weekly-invite="starter"]');
    const comingUp = find('[data-weekly-invite="coming-up"]');
    const starterSection = $('starterPicks');
    const showStarter = canInvite() && Boolean(starterSection && !starterSection.hidden)
      && state.libraryTotal + state.added >= STARTER_GOAL;
    if (starter) starter.hidden = !showStarter;
    if (comingUp) comingUp.hidden = !canInvite() || showStarter;
    const wrap = $('comingUpEmail');
    if (wrap) wrap.hidden = !state.email.enabled && (!state.email.available || canInvite());
    const toggle = $('comingUpEmailToggle');
    if (toggle) toggle.checked = Boolean(state.email.enabled);
  }

  async function setWeekly(enabled) {
    const response = await fetch(`${apiBase()}/api/for-you/email`, fetchOptions({
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, source: 'dashboard' }),
    }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Could not update the weekly email. Please try again.');
    state.email = { ...state.email, ...data };
    return data;
  }

  async function acceptInvite(invite) {
    const where = invite.dataset.weeklyInvite;
    const status = where === 'starter' ? $('starterPicksStatus') : $('comingUpStatus');
    const button = invite.querySelector('[data-weekly-action="subscribe"]');
    if (button) button.disabled = true;
    try {
      await setWeekly(true);
      if (status) status.textContent = 'Weekly email on. Your first one arrives within a day if something you track is coming up or a friend added something new; every email has a one-click unsubscribe.';
    } catch (error) {
      if (status) status.textContent = error.message;
    } finally {
      if (button) button.disabled = false;
      renderInvites();
    }
  }

  function dismissInvite() {
    try { localStorage.setItem(weeklyKey(), '1'); } catch (error) { /* session-only */ }
    renderInvites();
  }

  function friendlyDate(iso) {
    if (!iso) return 'Date to be announced';
    const date = new Date(`${iso}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return 'Date to be announced';
    const today = new Date();
    // Release dates are calendar days, so count from the member's own date, not UTC's.
    const days = Math.round((date - Date.UTC(today.getFullYear(), today.getMonth(), today.getDate(), 12)) / 86400000);
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
    renderInvites();
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
        link: typeof pick.url === 'string' && pick.url.startsWith('/titles/') ? pick.url : null,
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
      summary.textContent = `${matches.length} new release${matches.length === 1 ? '' : 's'} connected to titles you track. We'll send you a notification on the day each one comes out.`;
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
    state.email = email || {};
    renderInvites();
  }

  async function saveEmail(event) {
    const toggle = event.target;
    const status = $('comingUpStatus');
    toggle.disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/for-you/email`, fetchOptions({
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: toggle.checked, source: 'dashboard' }),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        toggle.checked = !toggle.checked;
        status.textContent = data.detail || 'Could not update the weekly email. Please try again.';
      } else {
        toggle.checked = Boolean(data.enabled);
        state.email = { ...state.email, ...data };
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

  // ---------------------------------------------------------- private release calendar

  function calendarStatus(text) {
    const status = $('releaseCalendarStatus');
    if (status) status.textContent = text;
  }

  function renderCalendar(data) {
    state.calendar = data || {};
    const panel = $('releaseCalendarPanel');
    const button = $('comingUpCalendarButton');
    if (!panel || !button) return;
    const links = state.calendar.enabled ? (state.calendar.links || {}) : null;
    const safe = (url, prefix) => (typeof url === 'string' && url.startsWith(prefix) ? url : '#');
    if (links) {
      $('releaseCalendarGoogle').href = safe(links.google, 'https://calendar.google.com/');
      $('releaseCalendarApple').href = safe(links.webcal, 'webcal://');
      $('releaseCalendarOutlook').href = safe(links.outlook, 'https://outlook.live.com/');
    }
    button.textContent = links ? 'My calendar' : 'Add to my calendar';
    const episodes = $('releaseCalendarEpisodes');
    if (episodes) episodes.checked = Boolean(links && state.calendar.include_episodes);
    const note = $('releaseCalendarEpisodesNote');
    if (note) {
      const soon = links && state.calendar.include_episodes ? Number(state.calendar.episodes_soon) || 0 : 0;
      note.textContent = soon ? `${soon} episode${soon === 1 ? '' : 's'} airing in the next two weeks.` : '';
    }
  }

  async function saveCalendarEpisodes() {
    const toggle = $('releaseCalendarEpisodes');
    if (!toggle) return;
    const wanted = toggle.checked;
    toggle.disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/calendar/episodes`, fetchOptions({
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: wanted }),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not update your calendar. Please try again.');
      renderCalendar(data);
      calendarStatus(wanted
        ? 'Episodes on. Each new episode gets its own entry, at the time it airs when the time is known. The first ones can take a few minutes to show up.'
        : 'Episodes off. Your calendar goes back to premieres, new seasons and release days on its next refresh.');
    } catch (error) {
      toggle.checked = !wanted;
      calendarStatus(error.message);
    } finally {
      toggle.disabled = false;
    }
  }

  async function calendarRequest(method, path) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({ method }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Could not update your calendar. Please try again.');
    return data;
  }

  async function openCalendar() {
    const panel = $('releaseCalendarPanel');
    const button = $('comingUpCalendarButton');
    if (!panel || !button) return;
    if (!panel.hidden) {
      panel.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      return;
    }
    button.disabled = true;
    try {
      renderCalendar(await calendarRequest('POST', '/api/calendar'));
      panel.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      calendarStatus('');
    } catch (error) {
      calendarStatus(error.message);
      const status = $('comingUpStatus');
      if (status) status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function copyCalendar() {
    const url = state.calendar && state.calendar.links && state.calendar.links.url;
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      calendarStatus('Address copied. In your calendar app, choose "Add calendar from URL" or "Subscribe" and paste it.');
    } catch (error) {
      calendarStatus(`Paste this address into your calendar app: ${url}`);
    }
  }

  async function resetCalendar() {
    try {
      renderCalendar(await calendarRequest('POST', '/api/calendar/reset'));
      calendarStatus('New address ready. The old one has stopped working, so add this one to your calendar again.');
    } catch (error) {
      calendarStatus(error.message);
    }
  }

  async function turnOffCalendar() {
    try {
      renderCalendar(await calendarRequest('DELETE', '/api/calendar'));
      $('releaseCalendarPanel').hidden = true;
      $('comingUpCalendarButton').setAttribute('aria-expanded', 'false');
      const status = $('comingUpStatus');
      if (status) status.textContent = 'Calendar turned off. Its address no longer works; you can remove it from your calendar app.';
    } catch (error) {
      calendarStatus(error.message);
    }
  }

  function openCalendarFromLink() {
    if (window.location.hash !== '#release-calendar' || state.calendarLinkHandled) return;
    const section = $('comingUp');
    if (!section || section.hidden) return;
    state.calendarLinkHandled = true;
    section.scrollIntoView({ block: 'start' });
    if ($('releaseCalendarPanel').hidden) openCalendar();
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
      // Both requests start together; on a phone, asking one after the other added
      // a full round trip before the card could appear.
      const picksRequest = starterDismissed() ? null : getJson('/api/for-you/starter-picks');
      if (picksRequest) picksRequest.catch(() => {});
      const comingUp = await getJson('/api/for-you/coming-up');
      if (request !== state.request) return;
      state.email = comingUp.email || {};
      let starterShown = false;
      // Starter picks count every category; coming-up counts only radar ones, so ask separately.
      if (picksRequest) {
        const picks = await picksRequest;
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
      renderInvites();
      openCalendarFromLink();
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
      const weekly = event.target.closest && event.target.closest('[data-weekly-action]');
      if (weekly) {
        const invite = weekly.closest('[data-weekly-invite]');
        if (weekly.dataset.weeklyAction === 'subscribe' && invite) acceptInvite(invite);
        if (weekly.dataset.weeklyAction === 'dismiss') dismissInvite();
      }
    });
    const toggle = $('comingUpEmailToggle');
    if (toggle) toggle.addEventListener('change', saveEmail);
    const episodes = $('releaseCalendarEpisodes');
    if (episodes) episodes.addEventListener('change', saveCalendarEpisodes);
    const handlers = {
      comingUpCalendarButton: openCalendar, releaseCalendarCopy: copyCalendar,
      releaseCalendarReset: resetCalendar, releaseCalendarOff: turnOffCalendar,
    };
    Object.entries(handlers).forEach(([id, handler]) => { const node = $(id); if (node) node.addEventListener('click', handler); });
    window.addEventListener('hashchange', () => { state.calendarLinkHandled = false; openCalendarFromLink(); });
  }

  window.refreshForYou = refreshForYou;
  window.resetForYou = resetForYou;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { friendlyDate, renderStarter, renderComingUp, renderInvites, acceptInvite, dismissInvite, state, STARTER_GOAL,
      renderCalendar, openCalendar, copyCalendar, resetCalendar, turnOffCalendar, saveCalendarEpisodes };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
