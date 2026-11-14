// Friends feed: the dashboard tab listing what friends recently added, finished, rated and
// reviewed, with a cheer, one-tap save to your own library, and a switch for sharing your own
// updates. Server text is only ever set as textContent.
(function () {
  'use strict';

  const SEEN_KEY = 'omnitrackr_friend_feed_seen';
  const TAB = 'friends-feed';
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const VERBS = {
    movies: 'watched', 'tv-shows': 'watched', anime: 'watched',
    'video-games': 'played', music: 'listened to', books: 'read', manga: 'read',
    podcasts: 'listened to', audiobooks: 'listened to',
  };
  const NOUN = {
    movies: 'a movie', 'tv-shows': 'a show', anime: 'an anime',
    'video-games': 'a game', music: 'an album', books: 'a book', manga: 'a manga',
    podcasts: 'a podcast', audiobooks: 'an audiobook',
  };
  const FILTERS = [
    ['all', 'Everything'],
    ['finished', 'Finished'],
    ['opinions', 'Ratings & reviews'],
    ['added', 'Added'],
  ];
  const VIEW_KEY = 'omnitrackr_social_view';
  const SPOILER = /\|\|([^|\n]{1,500})\|\|/g;
  const ICONS = {
    cheer: 'M12 3l1.8 4.6L18.5 9l-4.7 1.4L12 15l-1.8-4.6L5.5 9l4.7-1.4z M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z',
    queue: 'M12 5v14 M5 12h14',
    library: 'M6 4h12v16l-6-4-6 4z',
    check: 'M5 12.5l4.5 4.5L19 7.5',
  };
  const state = { items: [], next: null, loading: false, loaded: false, request: 0, peek: 0, filter: 'all', friends: 0, sharing: true };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    const headers = { ...(options.headers || {}) };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return { credentials: 'same-origin', ...options, headers };
  }

  async function api(path, options = {}) {
    const init = { ...options, headers: { Accept: 'application/json', ...(options.headers || {}) } };
    if (options.json !== undefined) {
      init.method = init.method || 'POST';
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.json);
      delete init.json;
    }
    const response = await fetch(`${apiBase()}${path}`, fetchOptions(init));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      const error = new Error(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(className, text, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', 'ffeed-icon');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', ICONS[name]);
    svg.appendChild(path);
    return svg;
  }

  function labelled(node, name, text) {
    node.replaceChildren(icon(name), el('span', '', text));
    return node;
  }

  // The server sends naive UTC times.
  function parseTime(value) {
    if (!value) return null;
    const text = /[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
    const date = new Date(text);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function ago(value, now = new Date()) {
    const date = parseTime(value);
    if (!date) return '';
    const seconds = Math.max(0, Math.floor((now - date) / 1000));
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // Groups the feed by day: "Today", "Yesterday", "This week", then "Earlier".
  function dayLabel(value, now = new Date()) {
    const date = parseTime(value);
    if (!date) return 'Earlier';
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const days = Math.round((start - day) / 86400000);
    if (days <= 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return 'This week';
    return 'Earlier';
  }

  // Review text with ||hidden bits|| kept back until tapped, like discussion posts.
  function spoilerParts(text) {
    const parts = [];
    let last = 0;
    String(text || '').replace(SPOILER, (match, hidden, offset) => {
      if (offset > last) parts.push({ text: text.slice(last, offset) });
      parts.push({ text: hidden, hidden: true });
      last = offset + match.length;
      return match;
    });
    if (last < String(text || '').length) parts.push({ text: String(text).slice(last) });
    return parts;
  }

  function reviewText(node, text) {
    spoilerParts(text).forEach(part => {
      if (!part.hidden) { node.append(document.createTextNode(part.text)); return; }
      const bit = el('button', 'ffeed-spoiler', part.text);
      bit.type = 'button';
      bit.setAttribute('aria-label', 'Hidden spoiler. Show it');
      bit.addEventListener('click', () => {
        bit.classList.add('is-shown');
        bit.removeAttribute('aria-label');
        bit.disabled = true;
      }, { once: true });
      node.append(bit);
    });
    return node;
  }

  function rating(value) {
    if (value === null || value === undefined) return '';
    const number = Number(value);
    return `${Number.isInteger(number) ? number : number.toFixed(1)}/10`;
  }

  // "finished a movie", "rated a book 8/10", "reviewed an album", "added a game"
  function action(item) {
    const noun = NOUN[item.category] || 'a title';
    if (item.kind === 'finished') return item.category === 'music' ? `${VERBS.music} ${noun}` : `finished ${noun}`;
    if (item.kind === 'reviewed') return `reviewed ${noun}`;
    if (item.kind === 'rated') return `rated ${noun}`;
    if (item.finished) return `added ${noun} they've ${VERBS[item.category] || 'finished'}`;
    return `added ${noun}`;
  }

  function matches(item, filter) {
    if (filter === 'all') return true;
    if (item.type === 'burst') return filter === 'added';
    if (filter === 'finished') return item.kind === 'finished' || (item.kind === 'added' && item.finished);
    if (filter === 'opinions') return item.kind === 'rated' || item.kind === 'reviewed' || Boolean(item.review) || item.rating !== null;
    if (filter === 'added') return item.kind === 'added';
    return true;
  }

  function safePath(path) {
    return typeof path === 'string' && /^\/titles\/[a-z]+\/[a-z0-9-]+$/.test(path) ? path : null;
  }

  function cover(item, className) {
    const initial = (item.title || '?').slice(0, 1).toUpperCase();
    if (!item.image) return el('span', `${className} ${className}--empty`, initial);
    const img = el('img', className);
    img.src = item.image;
    img.alt = '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.addEventListener('error', () => img.replaceWith(el('span', `${className} ${className}--empty`, initial)), { once: true });
    return img;
  }

  function avatar(friend) {
    const img = el('img', 'ffeed-avatar');
    img.src = friend.avatar || '/static/default-avatar.svg';
    img.alt = '';
    img.loading = 'lazy';
    img.dataset.fallbackSrc = '/static/default-avatar.svg';
    return img;
  }

  function who(item) {
    const head = el('div', 'ffeed-card__head');
    head.append(avatar(item.friend));
    const line = el('p', 'ffeed-card__who');
    const name = button('ffeed-card__name', item.friend.username);
    name.dataset.action = 'open-friend-profile';
    name.dataset.friendId = String(item.friend.id);
    name.title = `See ${item.friend.username}'s library`;
    line.append(name, document.createTextNode(` ${item.type === 'burst' ? `added ${item.count} titles` : action(item)}`));
    const time = el('time', 'ffeed-card__time', ago(item.at));
    time.dateTime = item.at;
    head.append(line, time);
    return head;
  }

  function titleLink(item) {
    const path = safePath(item.title_path);
    const node = el(path ? 'a' : 'span', 'ffeed-card__title', item.title);
    if (path) node.href = path;
    return node;
  }

  function review(item) {
    if (!item.review) return null;
    const quote = reviewText(el('blockquote', 'ffeed-card__review'), item.review);
    if (!item.spoiler) return quote;
    const box = el('details', 'ffeed-card__spoiler');
    box.append(el('summary', '', 'Spoilers. Show their review'), quote);
    return box;
  }

  function cheerLabel(node, item) {
    labelled(node, 'cheer', item.cheered ? `Cheered${item.cheers > 1 ? ` · ${item.cheers}` : ''}` : `Cheer${item.cheers ? ` · ${item.cheers}` : ''}`);
    node.setAttribute('aria-pressed', String(Boolean(item.cheered)));
    node.disabled = Boolean(item.cheered);
  }

  async function cheer(item, node) {
    node.disabled = true;
    try {
      const data = await api('/api/friend-feed/cheer', { json: { friend_id: item.friend.id, category: item.category, item_id: item.item_id } });
      item.cheered = true;
      item.cheers = data.cheers;
      cheerLabel(node, item);
    } catch (error) {
      node.disabled = false;
      note(node.closest('.ffeed-card'), error.message, 'error');
    }
  }

  async function save(item, card, nextUp) {
    const actions = card.querySelector('.ffeed-card__actions');
    actions.querySelectorAll('[data-feed-save]').forEach(node => { node.disabled = true; });
    try {
      const data = await api('/api/friend-feed/save', {
        json: { friend_id: item.friend.id, category: item.category, item_id: item.item_id, next_up: nextUp },
      });
      item.in_library = true;
      actions.querySelectorAll('[data-feed-save]').forEach(node => node.remove());
      actions.appendChild(owned());
      note(card, data.queued ? `Added to your Next Up.` : data.created ? 'Added to your library.' : 'Already in your library.');
      const loader = window[LOADERS[data.category]];
      if (data.created && typeof loader === 'function') {
        try { loader(); } catch (error) { /* refreshes on the next visit */ }
      }
      if (data.queued && typeof refreshNextUpQueue === 'function') refreshNextUpQueue();
    } catch (error) {
      actions.querySelectorAll('[data-feed-save]').forEach(node => { node.disabled = false; });
      note(card, error.message, 'error');
    }
  }

  function note(card, text, tone) {
    if (!card) return;
    const box = card.querySelector('.ffeed-card__note') || el('p', 'ffeed-card__note');
    box.setAttribute('role', 'status');
    box.textContent = text;
    box.dataset.tone = tone || '';
    card.querySelector('.ffeed-card__body').appendChild(box);
  }

  function owned() {
    return labelled(el('span', 'ffeed-card__owned'), 'check', 'In your library');
  }

  function titleCard(item) {
    const card = el('li', 'ffeed-card');
    card.dataset.kind = item.kind;
    card.dataset.feedId = item.id;
    if (item.category) card.dataset.format = item.category;
    card.append(who(item));
    const body = el('div', 'ffeed-card__body');
    const main = el('div', 'ffeed-card__main');
    main.append(cover(item, 'ffeed-card__cover'));
    const copy = el('div', 'ffeed-card__copy');
    copy.append(titleLink(item));
    const meta = [item.category_label, item.year, item.creator].filter(Boolean).join(' · ');
    if (meta) {
      const line = el('p', 'ffeed-card__meta');
      line.append(el('span', 'ffeed-card__format', item.category_label || ''), document.createTextNode([item.year, item.creator].filter(Boolean).join(' · ')));
      if (!item.category_label) line.firstChild.remove();
      copy.append(line);
    }
    const chips = el('p', 'ffeed-card__chips');
    if (item.rating !== null && item.rating !== undefined) chips.append(el('span', 'ffeed-chip ffeed-chip--rating', `★ ${rating(item.rating)}`));
    if (item.finished) chips.append(el('span', 'ffeed-chip ffeed-chip--done', 'Finished'));
    if (chips.childNodes.length) copy.append(chips);
    const text = review(item);
    if (text) copy.append(text);
    main.append(copy);
    body.append(main);

    const actions = el('div', 'ffeed-card__actions');
    const cheerButton = button('ffeed-btn ffeed-btn--cheer', '', () => cheer(item, cheerButton));
    cheerLabel(cheerButton, item);
    actions.append(cheerButton);
    if (item.in_library) {
      actions.append(owned());
    } else {
      const queue = labelled(button('ffeed-btn ffeed-btn--queue', '', () => save(item, card, true)), 'queue', 'Add to Next Up');
      queue.dataset.feedSave = 'next-up';
      const library = labelled(button('ffeed-btn ffeed-btn--quiet', '', () => save(item, card, false)), 'library', 'Add to library');
      library.dataset.feedSave = 'library';
      actions.append(queue, library);
    }
    body.append(actions);
    card.append(body);
    return card;
  }

  function burstCard(item) {
    const card = el('li', 'ffeed-card ffeed-card--burst');
    card.dataset.feedId = item.id;
    card.append(who(item));
    const body = el('div', 'ffeed-card__body');
    const row = el('ul', 'ffeed-burst');
    item.titles.forEach(title => {
      const entry = el('li', 'ffeed-burst__item');
      const path = safePath(title.title_path);
      const link = el(path ? 'a' : 'span', 'ffeed-burst__link');
      if (path) link.href = path;
      link.append(cover(title, 'ffeed-burst__cover'), el('span', 'ffeed-burst__title', title.title));
      link.title = `${title.title} (${title.category_label})`;
      entry.append(link);
      row.append(entry);
    });
    body.append(row);
    const more = item.count - item.titles.length;
    if (more > 0) body.append(el('p', 'ffeed-card__meta', `and ${more} more`));
    card.append(body);
    return card;
  }

  function emptyState() {
    const box = el('li', 'ffeed-empty');
    if (!state.friends) {
      box.append(el('h3', '', 'Your feed fills up with friends'),
        el('p', '', 'Add a friend and you\'ll see what they finish, rate and review here, and they\'ll see yours. Not on OmniTrackr yet? Send them your invite link and you become friends when they join.'));
      const add = button('action-btn', '+ Add a friend', () => {
        if (typeof window.openFriendRequestModal === 'function') window.openFriendRequestModal();
      });
      box.append(add);
    } else if (state.filter !== 'all' && state.items.length) {
      box.append(el('p', '', 'Nothing like that in the last 30 days. Try another filter.'));
    } else {
      box.append(el('h3', '', 'Quiet for now'),
        el('p', '', 'Nothing new from your friends in the last 30 days. When they add, finish, rate or review something, it shows up here.'));
    }
    return box;
  }

  function render() {
    const list = $('friendsFeedList');
    if (!list) return;
    const shown = state.items.filter(item => matches(item, state.filter));
    const rows = [];
    let day = null;
    const now = new Date();
    shown.forEach(item => {
      const label = dayLabel(item.at, now);
      if (label !== day) {
        day = label;
        const divider = el('li', 'ffeed-day');
        divider.append(el('h3', 'ffeed-day__label', label));
        rows.push(divider);
      }
      rows.push(item.type === 'burst' ? burstCard(item) : titleCard(item));
    });
    list.replaceChildren(...(rows.length ? rows : [emptyState()]));
    const more = $('friendsFeedMore');
    if (more) more.hidden = !state.next;
    document.querySelectorAll('[data-feed-filter]').forEach(node => {
      node.setAttribute('aria-pressed', String(node.dataset.feedFilter === state.filter));
    });
    const share = $('friendsFeedSharing');
    if (share) share.checked = state.sharing;
  }

  function status(text) {
    const node = $('friendsFeedStatus');
    if (node) node.textContent = text || '';
  }

  function readSeen() {
    try { return localStorage.getItem(SEEN_KEY) || ''; } catch (error) { return ''; }
  }

  function markSeen(at) {
    if (!at) return;
    try { if (at > readSeen()) localStorage.setItem(SEEN_KEY, at); } catch (error) { /* storage off */ }
    const dot = $('friendsFeedDot');
    if (dot) dot.hidden = true;
  }

  async function load(reset = true) {
    if (!$('friendsFeedList') || state.loading) return;
    const request = ++state.request;
    state.loading = true;
    if (reset) status(state.loaded ? '' : 'Loading your friends\' updates…');
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (!reset && state.next) params.set('before', state.next);
      const data = await api(`/api/friend-feed?${params}`);
      if (request !== state.request) return;
      state.items = reset ? data.items : state.items.concat(data.items);
      state.next = data.next_before;
      state.friends = data.friends;
      state.sharing = data.sharing !== false;
      state.loaded = true;
      status('');
      render();
      if (reset && state.items[0]) markSeen(state.items[0].at);
    } catch (error) {
      if (request === state.request) status(error.status === 401 ? '' : 'Couldn\'t load your friends feed. Please try again.');
    } finally {
      if (request === state.request) state.loading = false;
    }
  }

  // On sign-in: light the tab's dot when a friend posted since the feed was last opened.
  async function refresh() {
    const request = ++state.peek;
    try {
      const data = await api('/api/friend-feed?limit=1');
      if (request !== state.peek) return;
      const newest = data.items[0]?.at;
      const dot = $('friendsFeedDot');
      if (dot) dot.hidden = !(newest && newest > readSeen());
    } catch (error) {
      // Optional; the dashboard works without it.
    }
    openFromHash();
  }

  function reset() {
    state.request += 1;
    state.peek += 1;
    Object.assign(state, { items: [], next: null, loading: false, loaded: false, filter: 'all', friends: 0, sharing: true });
    $('friendsFeedList')?.replaceChildren();
    const dot = $('friendsFeedDot');
    if (dot) dot.hidden = true;
  }

  async function setSharing(input) {
    const wanted = input.checked;
    input.disabled = true;
    try {
      const data = await api('/api/friend-feed/sharing', { json: { sharing: wanted } });
      state.sharing = data.sharing;
      status(data.sharing ? 'Friends will see your new adds, finishes, ratings and reviews.' : 'Your updates are hidden from friends\' feeds.');
    } catch (error) {
      input.checked = !wanted;
      status(error.message);
    } finally {
      input.disabled = false;
    }
  }

  function openFromHash() {
    if (window.location.hash !== '#friends-feed') return;
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
    if (typeof navigateLibraryTab === 'function') navigateLibraryTab(TAB);
    else if (typeof switchTab === 'function') switchTab(TAB);
  }

  // Friends / Following switch at the top of the tab. Remembers the last choice.
  function showView(view, focus) {
    const root = document.querySelector('.social[data-social-view]');
    if (!root) return;
    const wanted = view === 'following' ? 'following' : 'friends';
    root.dataset.socialView = wanted;
    const panels = { friends: $('friendsFeedPanel'), following: $('followingFeed') };
    Object.entries(panels).forEach(([key, panel]) => { if (panel) panel.hidden = key !== wanted; });
    const filters = $('friendsFeedFilters');
    if (filters) filters.hidden = wanted !== 'friends';
    document.querySelectorAll('[data-social-tab]').forEach(tab => {
      const on = tab.dataset.socialTab === wanted;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      if (on && focus) tab.focus();
    });
    try { localStorage.setItem(VIEW_KEY, wanted); } catch (error) { /* storage off */ }
    if (wanted === 'following' && window.OmniFollowing && typeof window.OmniFollowing.load === 'function') window.OmniFollowing.load();
  }

  function initSwitch() {
    const tabs = [...document.querySelectorAll('[data-social-tab]')];
    if (!tabs.length) return;
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => showView(tab.dataset.socialTab));
      tab.addEventListener('keydown', event => {
        if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
        event.preventDefault();
        const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        showView(next.dataset.socialTab, true);
      });
    });
    let saved = 'friends';
    try { saved = localStorage.getItem(VIEW_KEY) || 'friends'; } catch (error) { /* storage off */ }
    showView(saved);
  }

  function init() {
    initSwitch();
    const filters = $('friendsFeedFilters');
    if (filters && !filters.childNodes.length) {
      FILTERS.forEach(([value, label]) => {
        const chip = button('ffeed-filter', label, () => { state.filter = value; render(); });
        chip.dataset.feedFilter = value;
        chip.setAttribute('aria-pressed', String(value === state.filter));
        filters.append(chip);
      });
    }
    $('friendsFeedMore')?.addEventListener('click', () => load(false));
    $('friendsFeedSharing')?.addEventListener('change', event => setSharing(event.target));
    $('friendsFeedAddFriend')?.addEventListener('click', () => {
      if (typeof window.openFriendRequestModal === 'function') window.openFriendRequestModal();
    });
    window.addEventListener('hashchange', openFromHash);
  }

  window.OmniFriendFeed = { load, refresh, reset };
  window.loadFriendFeed = load;
  window.refreshFriendFeed = refresh;
  window.resetFriendFeed = reset;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { action, ago, dayLabel, matches, parseTime, rating, safePath, spoilerParts };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
