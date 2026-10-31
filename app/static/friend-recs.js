// Recommend to a friend: a small dialog that sends a title (with a note) to friends or makes a
// share link, plus the "Recommended by friends" inbox on the dashboard. Loaded on the dashboard
// and on title pages for signed-in members. Server text is only ever set as textContent.
(function () {
  'use strict';

  const PENDING_KEY = 'omnitrackr_pending_recs';
  const NOTE_MAX = 280;
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const state = { source: null, friends: null, request: 0, items: [], expanded: false };

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
      const error = new Error(typeof detail === 'string' ? detail.replace(/^Value error, /, '') : 'Something went wrong. Please try again.');
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

  // ------------------------------------------------------------ the dialog

  function dialog() {
    let node = $('friendRecDialog');
    if (node) return node;
    node = el('dialog', 'frec-dialog');
    node.id = 'friendRecDialog';
    node.setAttribute('aria-labelledby', 'friendRecDialogTitle');
    const form = el('form', 'frec-form');
    form.method = 'dialog';
    form.noValidate = true;

    const head = el('header', 'frec-head');
    const heading = el('div');
    heading.append(el('p', 'frec-eyebrow', 'Recommend to a friend'), el('h2', 'frec-title'));
    heading.lastChild.id = 'friendRecDialogTitle';
    const close = button('frec-close', '✕', () => node.close());
    close.setAttribute('aria-label', 'Close');
    head.append(heading, close);

    const friends = el('fieldset', 'frec-friends');
    friends.appendChild(el('legend', '', 'Send to'));
    const search = el('input', 'frec-search');
    search.type = 'search';
    search.placeholder = 'Find a friend';
    search.setAttribute('aria-label', 'Find a friend');
    search.hidden = true;
    search.addEventListener('input', () => filterFriends(search.value));
    const list = el('div', 'frec-friend-list');
    list.id = 'friendRecFriends';
    list.addEventListener('change', updateSend);
    friends.append(search, list);

    const noteLabel = el('label', 'frec-note');
    const noteText = el('span', 'frec-note__label', 'Add a note');
    noteText.appendChild(el('small', '', ' optional'));
    const note = el('textarea');
    note.id = 'friendRecNote';
    note.rows = 3;
    note.maxLength = NOTE_MAX;
    note.placeholder = 'Why they\'ll love it. No spoilers!';
    const counter = el('span', 'frec-note__count', `0/${NOTE_MAX}`);
    note.addEventListener('input', () => { counter.textContent = `${note.value.length}/${NOTE_MAX}`; });
    noteLabel.append(noteText, note, counter);

    const actions = el('div', 'frec-actions');
    const send = el('button', 'frec-send', 'Send');
    send.type = 'submit';
    send.id = 'friendRecSend';
    send.disabled = true;
    actions.appendChild(send);

    const link = el('div', 'frec-link');
    link.append(el('p', '', 'Not on OmniTrackr yet? Send a link. When they join from it, you become friends.'),
      button('frec-link__button', 'Share a link instead', shareLink));
    link.lastChild.id = 'friendRecLink';

    const status = el('p', 'frec-status');
    status.id = 'friendRecStatus';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');

    form.append(head, friends, noteLabel, actions, link, status);
    form.addEventListener('submit', event => { event.preventDefault(); sendToFriends(); });
    node.appendChild(form);
    node.addEventListener('click', event => { if (event.target === node) node.close(); });
    document.body.appendChild(node);
    return node;
  }

  function setStatus(text, tone) {
    const status = $('friendRecStatus');
    if (!status) return;
    status.textContent = text || '';
    status.dataset.tone = tone || '';
  }

  function chosenFriends() {
    return Array.from(document.querySelectorAll('#friendRecFriends input:checked')).map(input => Number(input.value));
  }

  function updateSend() {
    const send = $('friendRecSend');
    if (!send) return;
    const count = chosenFriends().length;
    send.disabled = count === 0;
    send.textContent = count > 1 ? `Send to ${count} friends` : 'Send';
  }

  function filterFriends(query) {
    const needle = query.trim().toLowerCase();
    document.querySelectorAll('#friendRecFriends .frec-friend').forEach(label => {
      label.hidden = needle !== '' && !label.dataset.name.includes(needle);
    });
  }

  async function loadFriends() {
    if (state.friends) return state.friends;
    const data = await api('/friends');
    state.friends = (Array.isArray(data) ? data : []).map(entry => entry.friend).filter(Boolean)
      .sort((a, b) => a.username.localeCompare(b.username));
    return state.friends;
  }

  function renderFriends(friends) {
    const list = $('friendRecFriends');
    if (!list) return;
    list.replaceChildren();
    const search = list.previousElementSibling;
    if (search) search.hidden = friends.length <= 6;
    if (!friends.length) {
      const empty = el('p', 'frec-empty', 'No friends here yet. Share a link below, or add friends from the Friends panel.');
      list.appendChild(empty);
      return;
    }
    friends.forEach(friend => {
      const label = el('label', 'frec-friend');
      label.dataset.name = friend.username.toLowerCase();
      const input = el('input');
      input.type = 'checkbox';
      input.value = String(friend.id);
      const initial = el('span', 'frec-friend__initial', friend.username.slice(0, 1).toUpperCase());
      initial.setAttribute('aria-hidden', 'true');
      label.append(input, initial, el('span', 'frec-friend__name', friend.username));
      list.appendChild(label);
    });
  }

  function sourceFrom(trigger) {
    const data = trigger.dataset;
    if (data.recKind && data.recSlug) return { kind: data.recKind, slug: data.recSlug, title: data.recTitle || 'this title' };
    const itemId = Number(data.recItemId);
    if (data.recCategory && Number.isInteger(itemId) && itemId > 0) {
      return { category: data.recCategory, item_id: itemId, title: data.recTitle || 'this title' };
    }
    return null;
  }

  function payload(extra = {}) {
    const { title, ...source } = state.source || {};
    const note = ($('friendRecNote')?.value || '').trim();
    return { ...source, ...(note ? { note } : {}), ...extra };
  }

  async function open(source) {
    if (!source) return;
    state.source = source;
    const node = dialog();
    node.querySelector('.frec-title').textContent = source.title;
    $('friendRecNote').value = '';
    node.querySelector('.frec-note__count').textContent = `0/${NOTE_MAX}`;
    const search = node.querySelector('.frec-search');
    search.value = '';
    setStatus('');
    $('friendRecFriends').replaceChildren(el('p', 'frec-empty', 'Loading your friends…'));
    updateSend();
    if (typeof node.showModal === 'function') node.showModal(); else node.setAttribute('open', '');
    try {
      renderFriends(await loadFriends());
    } catch (error) {
      $('friendRecFriends').replaceChildren(el('p', 'frec-empty', 'Could not load your friends. You can still share a link.'));
    }
    updateSend();
  }

  async function sendToFriends() {
    const friendIds = chosenFriends();
    if (!friendIds.length || !state.source) return;
    const send = $('friendRecSend');
    send.disabled = true;
    setStatus('Sending…');
    try {
      const data = await api('/api/friend-recs', { json: payload({ friend_ids: friendIds }) });
      const names = data.friends || [];
      const who = names.length === 1 ? names[0] : `${names.length} friends`;
      setStatus(data.sent ? `Sent to ${who}. They'll find it on their dashboard.` : `Already in ${who}'s inbox. We updated your note.`, 'ok');
      document.querySelectorAll('#friendRecFriends input:checked').forEach(input => { input.checked = false; });
    } catch (error) {
      setStatus(error.message, 'error');
    } finally {
      updateSend();
    }
  }

  async function shareLink() {
    if (!state.source) return;
    const trigger = $('friendRecLink');
    if (trigger) trigger.disabled = true;
    setStatus('Making your link…');
    try {
      const data = await api('/api/friend-recs/link', { json: payload() });
      if (navigator.share) {
        try {
          await navigator.share({ title: data.title, text: data.text, url: data.url });
          setStatus('Shared. When they join from your link, you\'ll be friends.', 'ok');
          return;
        } catch (error) {
          if (error && error.name === 'AbortError') { setStatus(''); return; }
        }
      }
      try {
        await navigator.clipboard.writeText(`${data.text} ${data.url}`);
        setStatus('Link copied. Paste it into a message to your friend.', 'ok');
      } catch (error) {
        setStatus(`Copy this link: ${data.url}`, 'ok');
      }
    } catch (error) {
      setStatus(error.message, 'error');
    } finally {
      if (trigger) trigger.disabled = false;
    }
  }

  // Library rows get a "Recommend" action beside "Next up" (it tucks into the row's More menu).
  function decorate(cell, row) {
    if (!cell || cell.querySelector('[data-friend-rec-open]')) return;
    const nextUp = cell.querySelector('[data-action="add-next-up"]');
    if (!nextUp) return;
    const titleCell = row && row.cells && row.cells[1];
    const title = titleCell ? titleCell.textContent.trim() : '';
    const recommend = el('button', 'action-btn', 'Recommend');
    recommend.type = 'button';
    recommend.dataset.friendRecOpen = '';
    recommend.dataset.recCategory = nextUp.dataset.nextUpCategory;
    recommend.dataset.recItemId = nextUp.dataset.nextUpItemId;
    if (title) {
      recommend.dataset.recTitle = title;
      recommend.setAttribute('aria-label', `Recommend ${title} to a friend`);
    }
    nextUp.after(recommend);
  }

  // ------------------------------------------------------------ the inbox (dashboard)

  function readPending() {
    try {
      const list = JSON.parse(localStorage.getItem(PENDING_KEY) || '[]');
      return Array.isArray(list) ? list.filter(token => typeof token === 'string' && /^[A-Za-z0-9_-]{16,48}$/.test(token)) : [];
    } catch (error) {
      return [];
    }
  }

  function writePending(list) {
    try {
      if (list.length) localStorage.setItem(PENDING_KEY, JSON.stringify(list));
      else localStorage.removeItem(PENDING_KEY);
    } catch (error) { /* storage off */ }
  }

  // Links opened before signing in (or signing up) land in the inbox the first time the dashboard loads.
  async function claimPending() {
    const pending = readPending();
    if (!pending.length) return;
    const left = [];
    for (const token of pending) {
      try {
        await api(`/api/friend-recs/claim/${encodeURIComponent(token)}`, { method: 'POST' });
      } catch (error) {
        if (!error.status || error.status >= 500 || error.status === 429 || error.status === 401) left.push(token);
      }
    }
    writePending(left);
  }

  function metaLine(item) {
    return [item.category_label, item.year, item.creator].filter(Boolean).join(' · ');
  }

  function card(item) {
    const row = el('li', 'frec-item');
    row.dataset.recId = String(item.id);
    if (item.image) {
      const img = el('img', 'frec-item__cover');
      img.src = item.image;
      img.alt = '';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.replaceWith(el('span', 'frec-item__cover frec-item__cover--empty', item.title.slice(0, 1).toUpperCase())), { once: true });
      row.appendChild(img);
    } else {
      row.appendChild(el('span', 'frec-item__cover frec-item__cover--empty', item.title.slice(0, 1).toUpperCase()));
    }
    const copy = el('div', 'frec-item__copy');
    copy.appendChild(el('p', 'frec-item__from', `${item.sender} recommends`));
    const title = el(item.title_path ? 'a' : 'span', 'frec-item__title', item.title);
    if (item.title_path && /^\/titles\/[a-z]+\/[a-z0-9-]+$/.test(item.title_path)) title.href = item.title_path;
    copy.appendChild(title);
    const meta = metaLine(item);
    if (meta) copy.appendChild(el('p', 'frec-item__meta', meta));
    if (item.note) copy.appendChild(el('blockquote', 'frec-item__note', item.note));
    if (item.in_library) copy.appendChild(el('p', 'frec-item__owned', 'Already in your library'));
    const actions = el('div', 'frec-item__actions');
    actions.append(
      button('action-btn frec-item__queue', 'Add to Next Up', () => answer(item, row, 'next-up')),
      button('action-btn secondary', item.in_library ? 'Got it, thanks' : 'Add to library', () => answer(item, row, 'library')),
      button('frec-item__dismiss', 'Not for me', () => answer(item, row, 'dismiss')),
    );
    copy.appendChild(actions);
    row.appendChild(copy);
    return row;
  }

  function render(data) {
    const section = $('friendRecs');
    const list = $('friendRecsItems');
    if (!section || !list) return;
    state.items = data.items || [];
    const count = data.count || 0;
    if (!count) {
      section.hidden = true;
      list.replaceChildren();
      return;
    }
    $('friendRecsSummary').textContent = count === 1
      ? 'A friend picked this out for you. Add it in one tap.'
      : `${count} picks from friends, waiting for a yes or no.`;
    const shown = state.expanded ? state.items : state.items.slice(0, 3);
    list.replaceChildren(...shown.map(card));
    const more = $('friendRecsMore');
    if (more) {
      more.hidden = state.items.length <= 3;
      more.textContent = state.expanded ? 'Show fewer' : `Show all ${state.items.length}`;
      more.setAttribute('aria-expanded', String(state.expanded));
    }
    section.hidden = false;
    openFromHash();
  }

  async function refresh() {
    const section = $('friendRecs');
    if (!section) return;
    const request = ++state.request;
    try {
      await claimPending();
      const data = await api('/api/friend-recs/inbox');
      if (request === state.request) render(data);
    } catch (error) {
      // The inbox is optional; the dashboard works without it.
    }
  }

  function reset() {
    state.request += 1;
    state.friends = null;
    state.items = [];
    state.expanded = false;
    const section = $('friendRecs');
    if (section) section.hidden = true;
    $('friendRecsItems')?.replaceChildren();
  }

  async function answer(item, row, action) {
    row.querySelectorAll('button').forEach(node => { node.disabled = true; });
    const actions = row.querySelector('.frec-item__actions');
    try {
      let message = 'Removed. Your friend isn\'t told.';
      if (action === 'dismiss') {
        await api(`/api/friend-recs/${item.id}/dismiss`, { method: 'POST' });
      } else {
        const data = await api(`/api/friend-recs/${item.id}/add`, { json: { next_up: action === 'next-up' } });
        message = data.status === 'queued' ? `Added to your Next Up. ${item.sender} will know you took the tip.`
          : data.created ? 'Added to your library.' : 'It was already in your library. Thanks sent.';
        const loader = window[LOADERS[data.category]];
        if (data.created && typeof loader === 'function') {
          try { loader(); } catch (error) { /* the list refreshes on the next visit */ }
        }
        if (typeof refreshNextUpQueue === 'function') refreshNextUpQueue();
      }
      const done = el('p', 'frec-item__done', message);
      done.setAttribute('role', 'status');
      actions.replaceWith(done);
      row.classList.add('frec-item--answered');
      window.setTimeout(refresh, 2600);
    } catch (error) {
      row.querySelectorAll('button').forEach(node => { node.disabled = false; });
      const failed = row.querySelector('.frec-item__error') || el('p', 'frec-item__error');
      failed.textContent = error.status === 409 ? 'You already answered this one.' : error.message;
      actions.after(failed);
      if (error.status === 409) window.setTimeout(refresh, 1500);
    }
  }

  function openFromHash() {
    if (window.location.hash !== '#friend-recs') return;
    const section = $('friendRecs');
    if (!section || section.hidden) return;
    // Cards above can still be loading; settle on the inbox once they have.
    const scroll = () => { if (section.scrollIntoView) section.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
    scroll();
    window.setTimeout(scroll, 700);
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  function init() {
    document.addEventListener('click', event => {
      const trigger = event.target.closest && event.target.closest('[data-friend-rec-open]');
      if (trigger) {
        event.preventDefault();
        open(sourceFrom(trigger));
        return;
      }
      if (event.target.closest && event.target.closest('#friendRecsMore')) {
        state.expanded = !state.expanded;
        render({ count: state.items.length, items: state.items });
      }
    });
    window.addEventListener('hashchange', openFromHash);
  }

  window.OmniFriendRecs = { open, decorate, refresh, reset };
  window.refreshFriendRecs = refresh;
  window.resetFriendRecs = reset;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { metaLine, readPending, sourceFrom };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
