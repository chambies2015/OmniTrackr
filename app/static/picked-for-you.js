// Dashboard: the "For you" tab and its home card. Picks come from /api/for-you/picks,
// which ranks titles from other members' libraries for this member.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const FILTERS = [
    ['all', 'Everything'], ['movie', 'Movies'], ['tv', 'TV'], ['anime', 'Anime'], ['game', 'Games'],
    ['album', 'Albums'], ['book', 'Books'], ['manga', 'Manga'], ['podcast', 'Podcasts'], ['audiobook', 'Audiobooks'],
  ];
  const TEASER_SIZE = 4;
  const state = { data: null, request: null, filter: 'all', hidden: new Set(), saved: new Set(), hashHandled: false };

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

  function notify(message, tone) {
    if (typeof showNotice === 'function') showNotice(message, tone);
  }

  function teaserKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) {
      // Fall back to a shared key.
    }
    return `omnitrackr_picks_card_hidden_${name}`;
  }

  function teaserDismissed() {
    try { return localStorage.getItem(teaserKey()) === '1'; } catch (error) { return false; }
  }

  // ---------------------------------------------------------------- data

  function fetchPicks(force) {
    if (state.request && !force) return state.request;
    const request = fetch(`${apiBase()}/api/for-you/picks`, fetchOptions())
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(data => {
        if (state.request === request) {
          state.data = data;
          state.hidden = new Set();
        }
        return data;
      });
    state.request = request;
    request.catch(() => { if (state.request === request) state.request = null; });
    return request;
  }

  async function postPick(path, id) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }),
    }));
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const text = typeof apiErrorText === 'function' ? apiErrorText(body, '') : (typeof body.detail === 'string' ? body.detail : '');
      throw new Error(text || 'Something went wrong. Please try again.');
    }
    return body;
  }

  function visiblePicks() {
    const picks = (state.data && state.data.picks) || [];
    return picks.filter(pick => !state.hidden.has(pick.id));
  }

  function refreshLibrary(category) {
    const name = LOADERS[category];
    const loader = name && (window[name] || (typeof globalThis[name] === 'function' ? globalThis[name] : null));
    try {
      if (typeof loader === 'function' && typeof currentTab === 'string' && currentTab === category) loader();
    } catch (error) {
      // The list refreshes on the next visit.
    }
    if (typeof scheduleLibraryLaunchpadRefresh === 'function') {
      try { scheduleLibraryLaunchpadRefresh(); } catch (error) { /* optional */ }
    }
  }

  // ---------------------------------------------------------------- cards

  function poster(pick, className, initialClass) {
    const frame = el('div', className);
    const initial = () => el('span', initialClass, (pick.title || '?').slice(0, 1).toUpperCase());
    if (pick.image) {
      const img = document.createElement('img');
      img.src = pick.image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.replaceWith(initial()));
      frame.appendChild(img);
    } else {
      frame.appendChild(initial());
    }
    return frame;
  }

  function metaLine(pick) {
    return [pick.label, pick.year, pick.creator].filter(Boolean).join(' · ');
  }

  function saveButton(pick, className) {
    const saved = state.saved.has(pick.id);
    const button = el('button', className, saved ? '✓ Saved' : 'Save to library');
    button.type = 'button';
    button.disabled = saved;
    button.classList.toggle('is-added', saved);
    button.setAttribute('aria-label', saved ? `${pick.title} is in your library` : `Save ${pick.title} to your library`);
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      button.textContent = 'Saving…';
      try {
        const result = await postPick('/api/for-you/picks/add', pick.id);
        state.saved.add(pick.id);
        document.querySelectorAll(`[data-pick-save="${CSS.escape(pick.id)}"]`).forEach(other => {
          other.textContent = '✓ Saved';
          other.disabled = true;
          other.classList.add('is-added');
        });
        notify(result.state === 'existing' ? `${pick.title} was already in your library.` : `Saved ${pick.title} to your library.`, 'success');
        refreshLibrary(pick.category);
      } catch (error) {
        button.disabled = false;
        button.textContent = 'Save to library';
        notify(error.message, 'error');
      }
    });
    button.dataset.pickSave = pick.id;
    return button;
  }

  function dismissButton(pick) {
    const button = el('button', 'picks-card__dismiss', 'Not for me');
    button.type = 'button';
    button.setAttribute('aria-label', `Not for me: hide ${pick.title}`);
    button.addEventListener('click', () => dismiss(pick));
    return button;
  }

  function pickCard(pick, inRow) {
    const card = el('article', 'picks-card');
    card.dataset.pickId = pick.id;
    const link = el('a', 'picks-card__poster-link');
    link.href = pick.url;
    link.setAttribute('aria-label', `${pick.title}, open its page`);
    link.appendChild(poster(pick, 'picks-card__poster', 'picks-card__initial'));
    if (pick.average) link.appendChild(el('span', 'picks-card__score', `★ ${pick.average}`));
    card.appendChild(link);
    const body = el('div', 'picks-card__body');
    const heading = el('h4', 'picks-card__title');
    const anchor = el('a', '', pick.title);
    anchor.href = pick.url;
    heading.appendChild(anchor);
    heading.title = pick.title;
    body.append(heading, el('p', 'picks-card__meta', metaLine(pick)));
    // Inside a "Because you liked X" row the heading already gives the reason.
    if (!inRow) body.appendChild(el('p', 'picks-card__reason', pick.reason));
    if (pick.detail) body.appendChild(el('p', 'picks-card__detail', pick.detail));
    const actions = el('div', 'picks-card__actions');
    actions.append(saveButton(pick, 'picks-card__save'), dismissButton(pick));
    body.appendChild(actions);
    card.appendChild(body);
    return card;
  }

  function teaserCard(pick) {
    // Same shape as the other home suggestion cards (for-you-item).
    const card = el('article', 'for-you-item');
    card.appendChild(poster(pick, 'for-you-item__art', 'for-you-item__initial'));
    const body = el('div', 'for-you-item__body');
    const heading = el('h4', 'for-you-item__title');
    heading.title = pick.title;
    const anchor = el('a', '', pick.title);
    anchor.href = pick.url;
    heading.appendChild(anchor);
    const note = pick.anchor_title ? `For fans of ${pick.anchor_title}` : pick.reason;
    body.append(heading, el('p', 'for-you-item__meta', metaLine(pick)), el('p', 'for-you-item__note', note));
    body.appendChild(saveButton(pick, 'for-you-item__add'));
    card.appendChild(body);
    return card;
  }

  // ---------------------------------------------------------------- tab

  function summaryText(data) {
    if (!data || data.state === 'empty') {
      return 'Save a few things you love and rate them. Until then, these are the titles members track most.';
    }
    if (data.state === 'thin') {
      return 'Your library doesn’t overlap much with other members yet, so these are popular picks in the formats you use. Rating what you’ve finished sharpens them.';
    }
    const members = data.neighbours
      ? `${data.neighbours} ${data.neighbours === 1 ? 'member tracks' : 'members track'} a lot of what you track. `
      : '';
    return `${members}These picks come from what members with your taste liked and the genres you rate highest. Every rating you add sharpens them.`;
  }

  function renderFilters(picks) {
    const wrap = $('picksFilters');
    if (!wrap) return;
    wrap.replaceChildren();
    const kinds = new Set(picks.map(pick => pick.kind));
    if (kinds.size < 2) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    if (state.filter !== 'all' && !kinds.has(state.filter)) state.filter = 'all';
    FILTERS.filter(([key]) => key === 'all' || kinds.has(key)).forEach(([key, label]) => {
      const chip = el('button', 'picks-filter', label);
      chip.type = 'button';
      chip.setAttribute('aria-pressed', String(state.filter === key));
      chip.addEventListener('click', () => {
        state.filter = key;
        renderTab();
      });
      wrap.appendChild(chip);
    });
  }

  function renderRows(picks) {
    const wrap = $('picksRows');
    if (!wrap) return new Set();
    wrap.replaceChildren();
    const shown = new Set();
    if (state.filter !== 'all') {
      wrap.hidden = true;
      return shown;
    }
    const byId = new Map(picks.map(pick => [pick.id, pick]));
    ((state.data && state.data.rows) || []).forEach(row => {
      const items = row.picks.map(id => byId.get(id)).filter(Boolean);
      if (items.length < 3) return;
      const section = el('section', 'picks-row');
      const headingId = `picksRow-${row.anchor.replace(/[^a-z0-9]+/gi, '-')}`;
      section.setAttribute('aria-labelledby', headingId);
      const head = el('div', 'picks-row__head');
      head.appendChild(el('p', 'picks-row__eyebrow', row.rating !== null && row.rating !== undefined ? `You rated it ${row.rating}/10` : row.label));
      const title = el('h3', 'picks-row__title', `Because you liked ${row.title}`);
      title.id = headingId;
      head.appendChild(title);
      section.appendChild(head);
      const track = el('div', 'picks-row__track');
      items.forEach(pick => { track.appendChild(pickCard(pick, true)); shown.add(pick.id); });
      section.appendChild(track);
      wrap.appendChild(section);
    });
    wrap.hidden = !wrap.children.length;
    return shown;
  }

  function renderGuides() {
    const wrap = $('picksGuides');
    if (!wrap) return;
    wrap.replaceChildren();
    const guides = (state.data && state.data.guides) || [];
    if (!guides.length || state.filter !== 'all') {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    wrap.appendChild(el('h3', 'picks-guides__title', 'Hand-picked for titles you rated highly'));
    const list = el('div', 'picks-guides__list');
    guides.forEach(guide => {
      const link = el('a', 'picks-guide');
      link.href = guide.url;
      link.append(el('strong', '', guide.title), el('span', '', `Our guide to what to watch, play and read next`));
      list.appendChild(link);
    });
    wrap.appendChild(list);
  }

  function renderTab() {
    const grid = $('picksGrid');
    if (!grid) return;
    const data = state.data;
    const summary = $('picksSummary');
    if (summary) summary.textContent = summaryText(data);
    const picks = visiblePicks();
    renderFilters(picks);
    const shown = renderRows(picks);
    renderGuides();
    const rest = picks.filter(pick => !shown.has(pick.id) && (state.filter === 'all' || pick.kind === state.filter));
    grid.replaceChildren(...rest.map(pick => pickCard(pick, false)));
    const allTitle = $('picksAllTitle');
    if (allTitle) {
      allTitle.textContent = shown.size ? 'More picks for you' : (state.filter === 'all' ? 'Picks for you' : `${FILTERS.find(([key]) => key === state.filter)[1]} for you`);
      allTitle.parentElement.hidden = !rest.length;
    }
    const status = $('picksStatus');
    if (status) {
      status.textContent = picks.length ? '' : 'You’ve seen every pick we have for now. Rate a few more titles and check back; new picks show up as members add things.';
    }
  }

  async function load() {
    const status = $('picksStatus');
    if (!state.data && status) status.textContent = 'Finding picks for you…';
    try {
      await fetchPicks(Boolean(state.data));
      renderTab();
    } catch (error) {
      if (status) status.textContent = 'Picks couldn’t load right now. Your library is fine; try again in a moment.';
    }
  }

  async function dismiss(pick) {
    state.hidden.add(pick.id);
    renderTab();
    renderTeaser();
    try {
      await postPick('/api/for-you/picks/dismiss', pick.id);
      showUndo(pick);
    } catch (error) {
      state.hidden.delete(pick.id);
      renderTab();
      renderTeaser();
      notify(error.message, 'error');
    }
  }

  function showUndo(pick) {
    const bar = $('picksUndo');
    if (!bar) return;
    bar.replaceChildren(el('span', '', `Hid ${pick.title}. It won’t come back.`));
    const undo = el('button', 'picks-undo__button', 'Undo');
    undo.type = 'button';
    undo.addEventListener('click', async () => {
      bar.hidden = true;
      try {
        await postPick('/api/for-you/picks/restore', pick.id);
        state.hidden.delete(pick.id);
        renderTab();
        renderTeaser();
      } catch (error) {
        notify(error.message, 'error');
      }
    });
    bar.appendChild(undo);
    bar.hidden = false;
    clearTimeout(state.undoTimer);
    state.undoTimer = setTimeout(() => { bar.hidden = true; }, 8000);
  }

  // ---------------------------------------------------------------- home card

  function renderTeaser() {
    const section = $('picksTeaser');
    const list = $('picksTeaserList');
    if (!section || !list) return;
    const starter = $('starterPicks');
    const picks = visiblePicks();
    // Members still filling their library see Quick start's picks instead.
    const ready = state.data && state.data.state === 'ready' && Number(state.data.library_total || 0) >= 5;
    if (!ready || picks.length < TEASER_SIZE || teaserDismissed() || (starter && !starter.hidden)) {
      section.hidden = true;
      return;
    }
    list.replaceChildren(...picks.slice(0, TEASER_SIZE).map(teaserCard));
    section.hidden = false;
  }

  function openFromLink() {
    if (window.location.hash !== '#for-you' || state.hashHandled) return;
    state.hashHandled = true;
    if (typeof navigateLibraryTab === 'function') navigateLibraryTab('for-you');
    else if (typeof switchTab === 'function') switchTab('for-you');
  }

  async function refreshTeaser() {
    try {
      await fetchPicks(true);
      renderTeaser();
      if (typeof currentTab === 'string' && currentTab === 'for-you') renderTab();
      openFromLink();
    } catch (error) {
      // Picks are optional; the dashboard works without them.
    }
  }

  function reset() {
    state.data = null;
    state.request = null;
    state.hidden = new Set();
    state.saved = new Set();
    state.filter = 'all';
    const section = $('picksTeaser');
    if (section) section.hidden = true;
  }

  function init() {
    const hide = $('picksTeaserHide');
    if (hide) {
      hide.addEventListener('click', () => {
        try { localStorage.setItem(teaserKey(), '1'); } catch (error) { /* session-only */ }
        $('picksTeaser').hidden = true;
        notify('Hidden from home. Your picks are still under For you.', 'info');
      });
    }
    const refresh = $('picksRefresh');
    if (refresh) refresh.addEventListener('click', () => { state.request = null; state.data = null; load(); });
    window.addEventListener('hashchange', () => { state.hashHandled = false; openFromLink(); });
  }

  window.OmniPicks = { load, refreshTeaser, reset };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { state, renderTab, renderTeaser, summaryText, pickCard, load, dismiss, refreshTeaser, reset };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
