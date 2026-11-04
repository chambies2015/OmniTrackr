// Dashboard home card: "Share your reviews". Lists the member's private reviews that would
// show on a title page (from /api/review-inbox) and shares one only when they press Share.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const SHOWN = 2;
  const HIDE_DAYS = 30;
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const LIST_NAMES = {
    movie: 'Movies', tv_show: 'TV shows', anime: 'Anime', video_game: 'Games', music: 'Music',
    book: 'Books', manga: 'Manga', podcast: 'Podcasts', audiobook: 'Audiobooks',
  };
  const state = { data: null, expanded: false, answered: new Map(), request: 0 };

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

  function hideKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) {
      // Fall back to a shared key.
    }
    return `omnitrackr_review_inbox_hidden_${name}`;
  }

  function hiddenForNow() {
    try {
      const until = Number(localStorage.getItem(hideKey()) || 0);
      return until > Date.now();
    } catch (error) {
      return false;
    }
  }

  function key(item) {
    return `${item.category}:${item.id}`;
  }

  function plural(count, one, many) {
    return `${count} ${count === 1 ? one : many}`;
  }

  async function post(path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const text = typeof apiErrorText === 'function' ? apiErrorText(data, '') : (typeof data.detail === 'string' ? data.detail : '');
      throw new Error(text || 'That didn\'t save. Check your connection and try again.');
    }
    return data;
  }

  function refreshLibrary(item) {
    const name = LOADERS[item.library_category];
    const loader = name && (window[name] || (typeof globalThis[name] === 'function' ? globalThis[name] : null));
    try {
      if (typeof loader === 'function' && typeof currentTab === 'string' && currentTab === item.library_category) loader();
    } catch (error) {
      // The list refreshes on the next visit.
    }
  }

  // ---------------------------------------------------------------- render

  function summaryText(data) {
    const waiting = data.items.filter(item => !state.answered.has(key(item)));
    const firsts = waiting.filter(item => item.first).length;
    const total = Math.max(0, data.total - state.answered.size);
    if (!total) return 'That\'s all of them. Thanks for sharing.';
    let text = `You've written ${plural(total, 'review', 'reviews')} that only you can see.`;
    if (firsts) {
      text += firsts === 1
        ? ' One of them would be the first review on its title\'s page.'
        : ` ${firsts} of them would be the first review on their title's page.`;
    }
    return `${text} Nothing changes unless you press Share.`;
  }

  function heading(item) {
    const head = el('div', 'review-inbox__head');
    head.appendChild(el('span', 'review-inbox__format', item.label));
    // A private list's titles have no public page until something on it is shared.
    const answered = state.answered.get(key(item));
    const linked = !item.private_list || (answered && answered.choice === 'shared');
    const title = el(linked ? 'a' : 'span', 'review-inbox__title', item.year ? `${item.title} (${item.year})` : item.title);
    if (linked) title.href = item.path;
    head.appendChild(title);
    if (item.rating !== null && item.rating !== undefined) {
      head.appendChild(el('span', 'review-inbox__rating', `${Number(item.rating)}/10`));
    }
    return head;
  }

  function tags(item) {
    const list = el('p', 'review-inbox__tags');
    if (item.first) list.appendChild(el('span', 'review-inbox__tag review-inbox__tag--first', 'Would be the first review on its page'));
    if (item.standalone) list.appendChild(el('span', 'review-inbox__tag', 'Long enough for a page of its own'));
    list.appendChild(el('span', 'review-inbox__tag review-inbox__tag--quiet', plural(item.words, 'word', 'words')));
    return list;
  }

  function answeredRow(item, answer) {
    const row = el('div', 'review-inbox__done');
    const text = el('p', 'review-inbox__done-text');
    if (answer.choice === 'shared') {
      text.append('Shared. It\'s on ');
      const link = el('a', '', `the ${item.title} page`);
      link.href = `${answer.path || item.path}#community-title`;
      text.appendChild(link);
      if (answer.review_url) {
        text.append(' and has ');
        const own = el('a', '', 'a page of its own');
        own.href = answer.review_url;
        text.appendChild(own);
      }
      text.append('.');
    } else {
      text.textContent = 'Kept private. It won\'t be suggested again unless you rewrite it.';
    }
    const undo = el('button', 'review-inbox__undo', 'Undo');
    undo.type = 'button';
    undo.addEventListener('click', () => undoAnswer(item, undo));
    row.append(text, undo);
    return row;
  }

  function itemCard(item) {
    const card = el('li', 'review-inbox__item');
    card.dataset.key = key(item);
    card.appendChild(heading(item));
    const answer = state.answered.get(key(item));
    if (answer) {
      card.classList.add('is-answered');
      card.appendChild(answeredRow(item, answer));
      return card;
    }
    card.appendChild(tags(item));
    card.appendChild(el('blockquote', 'review-inbox__excerpt', item.excerpt));
    if (item.private_list) {
      card.appendChild(el('p', 'review-inbox__private',
        `Your ${LIST_NAMES[item.category] || 'list'} list is private. Sharing shows this one review and your rating, nothing else from the list.`));
    }
    const actions = el('div', 'review-inbox__actions');
    const spoilers = el('label', 'review-inbox__spoilers');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = Boolean(item.spoilers);
    spoilers.append(box, el('span', '', 'It has spoilers'));
    const share = el('button', 'action-btn review-inbox__share', 'Share it');
    share.type = 'button';
    share.addEventListener('click', () => shareItem(item, box.checked, card));
    const keep = el('button', 'review-inbox__keep', 'Keep private');
    keep.type = 'button';
    keep.addEventListener('click', () => keepItem(item, card));
    actions.append(spoilers, share, keep);
    card.appendChild(actions);
    return card;
  }

  function render() {
    const section = $('reviewInbox');
    const list = $('reviewInboxList');
    if (!section || !list) return;
    const data = state.data;
    if (!data || !data.items.length || (hiddenForNow() && !state.answered.size)) {
      section.hidden = true;
      return;
    }
    $('reviewInboxSummary').textContent = summaryText(data);
    const items = state.expanded ? data.items : data.items.slice(0, SHOWN);
    list.replaceChildren(...items.map(itemCard));
    const more = $('reviewInboxMore');
    const rest = data.items.length - SHOWN;
    more.hidden = rest <= 0;
    more.textContent = state.expanded ? 'Show fewer' : `Show ${plural(rest, 'more review', 'more reviews')}`;
    more.setAttribute('aria-expanded', state.expanded ? 'true' : 'false');
    section.hidden = false;
  }

  function busy(card, value) {
    card.querySelectorAll('button, input').forEach(control => { control.disabled = value; });
  }

  // ---------------------------------------------------------------- actions

  async function shareItem(item, spoilers, card) {
    busy(card, true);
    try {
      const result = await post('/api/review-inbox/share', {
        category: item.category, item_id: item.id, version: item.version, spoilers,
      });
      state.answered.set(key(item), { choice: 'shared', path: result.path, review_url: result.review_url });
      render();
      refreshLibrary(item);
      notify(`Your review of ${item.title} is public now.`, 'success');
    } catch (error) {
      busy(card, false);
      notify(error.message, 'error');
    }
  }

  async function keepItem(item, card) {
    busy(card, true);
    try {
      await post('/api/review-inbox/keep', { category: item.category, item_id: item.id, version: item.version });
      state.answered.set(key(item), { choice: 'kept' });
      render();
    } catch (error) {
      busy(card, false);
      notify(error.message, 'error');
    }
  }

  async function undoAnswer(item, button) {
    button.disabled = true;
    try {
      const answer = state.answered.get(key(item));
      await post('/api/review-inbox/undo', { category: item.category, item_id: item.id });
      state.answered.delete(key(item));
      render();
      if (answer && answer.choice === 'shared') {
        refreshLibrary(item);
        notify(`Your review of ${item.title} is private again.`, 'info');
      }
    } catch (error) {
      button.disabled = false;
      notify(error.message, 'error');
    }
  }

  async function refresh() {
    const request = ++state.request;
    if (!$('reviewInbox')) return;
    try {
      const response = await fetch(`${apiBase()}/api/review-inbox`, fetchOptions());
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      state.data = { total: Number(data.total || 0), items: Array.isArray(data.items) ? data.items : [] };
      state.answered = new Map();
      state.expanded = false;
      render();
    } catch (error) {
      // The card is optional; the dashboard works without it.
      if (request === state.request && $('reviewInbox')) $('reviewInbox').hidden = true;
    }
  }

  function init() {
    const hide = $('reviewInboxHide');
    if (hide) {
      hide.addEventListener('click', () => {
        try { localStorage.setItem(hideKey(), String(Date.now() + HIDE_DAYS * 86400000)); } catch (error) { /* session-only */ }
        state.answered = new Map();
        $('reviewInbox').hidden = true;
        notify(`Hidden for ${HIDE_DAYS} days. Every review keeps its Public switch in your library.`, 'info');
      });
    }
    const more = $('reviewInboxMore');
    if (more) {
      more.addEventListener('click', () => {
        state.expanded = !state.expanded;
        render();
      });
    }
  }

  window.refreshReviewInbox = refresh;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { state, render, refresh, summaryText, itemCard, shareItem, keepItem, undoAnswer, init };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
