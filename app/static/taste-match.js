// Taste Match: how a friend's library lines up with yours, shown at the top of
// their profile, plus a match chip beside each name in the friends list.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { friendId: null, request: 0, data: null };
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks', manga: 'loadManga',
    podcasts: 'loadPodcasts',
  };

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

  function rating(value) {
    return Number.isInteger(value) ? String(value) : Number(value).toFixed(1);
  }

  function plural(count, one, many) {
    return `${count} ${count === 1 ? one : many}`;
  }

  async function getJson(path) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions());
    if (!response.ok) throw new Error(`Taste Match unavailable (${response.status})`);
    return response.json();
  }

  // ------------------------------------------------------------ profile panel

  function panel() { return $('friendTasteMatch'); }

  function meta(item) {
    const parts = [item.label];
    if (item.year) parts.push(String(item.year));
    if (item.creator) parts.push(item.creator);
    return parts.join(' · ');
  }

  function itemRow(item, detail) {
    const row = el('li', 'taste-match__item');
    if (item.image) {
      const img = el('img', 'taste-match__art');
      img.src = item.image;
      img.alt = '';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.remove(), { once: true });
      row.appendChild(img);
    }
    const copy = el('div', 'taste-match__copy');
    copy.append(el('span', 'taste-match__title', item.title), el('span', 'taste-match__meta', meta(item)));
    row.appendChild(copy);
    if (detail) row.appendChild(el('span', 'taste-match__ratings', detail));
    return row;
  }

  function section(title, items, render) {
    if (!items || !items.length) return null;
    const wrap = el('div', 'taste-match__section');
    wrap.appendChild(el('h4', 'taste-match__heading', title));
    const list = el('ul', 'taste-match__list');
    items.forEach(item => list.appendChild(render(item)));
    wrap.appendChild(list);
    return wrap;
  }

  function addButton(item, friendId) {
    const button = el('button', 'taste-match__add', 'Add to my list');
    button.type = 'button';
    button.setAttribute('aria-label', `Add ${item.title} to my list`);
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Adding…';
      try {
        const response = await fetch(`${apiBase()}/api/taste-match/friends/${friendId}/add`, fetchOptions({
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category: item.category, title: item.title }),
        }));
        let data = {};
        try { data = await response.json(); } catch (error) { data = {}; }
        if (!response.ok) throw new Error(data.detail || 'Could not add that title');
        const done = el('a', 'taste-match__added', data.state === 'existing' ? 'Already in your library' : 'Added · open');
        done.href = data.library_url || '/';
        button.replaceWith(done);
        const loader = window[LOADERS[item.category]];
        if (data.state === 'created' && typeof loader === 'function') {
          try { loader(); } catch (error) { /* the list refreshes on the next visit */ }
        }
      } catch (error) {
        button.disabled = false;
        button.textContent = 'Try again';
        button.title = error.message;
      }
    });
    return button;
  }

  function summaryLine(data, name) {
    const shared = plural(data.shared_count, 'title', 'titles');
    if (data.score !== null && data.score !== undefined) {
      return `You share ${shared}, and ${plural(data.rated_count, 'is', 'are')} rated by both of you.`;
    }
    if (!data.shared_count) return `No titles in common with ${name} yet. Their favorites below are a good place to start.`;
    const more = data.needed_for_score;
    return `You share ${shared}. Rate ${plural(more, 'more title', 'more titles')} you both have to see your score.`;
  }

  function render(data) {
    const root = panel();
    if (!root) return;
    const name = data.friend.username;
    root.replaceChildren();

    const head = el('div', 'taste-match__head');
    const hasScore = data.score !== null && data.score !== undefined;
    const dial = el('div', `taste-match__score${hasScore ? '' : ' taste-match__score--empty'}`, hasScore ? `${data.score}%` : '?');
    dial.setAttribute('aria-hidden', 'true');
    if (hasScore) dial.style.setProperty('--taste-score', String(data.score));
    const intro = el('div', 'taste-match__intro');
    intro.appendChild(el('p', 'taste-match__eyebrow', 'Taste Match'));
    intro.appendChild(el('p', 'taste-match__tier', hasScore ? `${data.tier} · ${data.score}%` : 'Still getting to know each other'));
    intro.appendChild(el('p', 'taste-match__summary', summaryLine(data, name)));
    head.append(dial, intro);
    root.appendChild(head);

    const overlap = (data.categories || []).filter(category => category.shared > 0);
    if (overlap.length) {
      const chips = el('p', 'taste-match__chips');
      overlap.forEach(category => chips.appendChild(el('span', 'taste-match__chip', `${category.label} ${category.shared}`)));
      root.appendChild(chips);
    }

    const parts = [
      section('You both loved', data.both_loved, item => itemRow(item, `You ${rating(item.your_rating)} · ${name} ${rating(item.their_rating)}`)),
      section('Where you disagree', data.disagreements, item => itemRow(item, `You ${rating(item.your_rating)} · ${name} ${rating(item.their_rating)}`)),
      section(`${name}'s favorites you haven't tracked`, data.their_picks, item => {
        const row = itemRow(item, `${name} ${rating(item.their_rating)}`);
        row.appendChild(addButton(item, data.friend.id));
        return row;
      }),
      section(`Worth recommending to ${name}`, data.your_picks, item => itemRow(item, `You ${rating(item.your_rating)}`)),
    ].filter(Boolean);
    parts.forEach(part => root.appendChild(part));
    if (!parts.length && !data.shared_count) {
      root.appendChild(el('p', 'taste-match__note', 'Rate a few favorites in your library and the matches will fill in here.'));
    }
    if (data.private_categories && data.private_categories.length) {
      root.appendChild(el('p', 'taste-match__note', `${name} keeps ${data.private_categories.join(', ')} private, so those are left out.`));
    }
    root.hidden = false;
  }

  async function show(friendId) {
    const root = panel();
    if (!root) return;
    const request = ++state.request;
    state.friendId = friendId;
    root.replaceChildren(el('p', 'taste-match__loading', 'Working out your Taste Match…'));
    root.hidden = false;
    try {
      const data = await getJson(`/api/taste-match/friends/${encodeURIComponent(friendId)}`);
      if (request !== state.request || state.friendId !== friendId) return;
      state.data = data;
      render(data);
    } catch (error) {
      if (request !== state.request) return;
      root.hidden = true;
      root.replaceChildren();
    }
  }

  function clear() {
    state.request++;
    state.friendId = null;
    state.data = null;
    const root = panel();
    if (root) { root.hidden = true; root.replaceChildren(); }
  }

  // ------------------------------------------------------------ friends list

  let listRequest = 0;
  async function decorateFriends() {
    const list = $('friendsList');
    if (!list || !list.querySelector('.friend-item')) return;
    const request = ++listRequest;
    let data;
    try { data = await getJson('/api/taste-match/friends'); } catch (error) { return; }
    if (request !== listRequest) return;
    const best = (data.friends || []).find(row => row.score !== null && row.score !== undefined);
    (data.friends || []).forEach(row => {
      const item = list.querySelector(`.friend-item[data-friend-id="${Number(row.friend_id)}"] .friend-item-content`);
      if (!item || row.score === null || row.score === undefined) return;
      const old = item.querySelector('.taste-chip');
      if (old) old.remove();
      const chip = el('button', `taste-chip${best && best.friend_id === row.friend_id ? ' taste-chip--best' : ''}`, `${row.score}% match`);
      chip.type = 'button';
      chip.dataset.action = 'open-friend-profile';
      chip.dataset.friendId = String(row.friend_id);
      chip.title = best && best.friend_id === row.friend_id ? `Your closest Taste Match · ${row.tier}` : `Taste Match · ${row.tier}`;
      item.appendChild(chip);
    });
  }

  window.OmniTasteMatch = { show, clear, decorateFriends };
})();
