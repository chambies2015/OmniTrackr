// "What's new" on the home screen: new episodes of the member's shows, releases they were
// told about, and their friends' latest finishes and ratings, counted since this device last
// showed the home screen. Data comes from GET /api/home/today (read only). Cheer and Save use
// the friends feed endpoints. Every piece of server text is set with textContent.
(function () {
  'use strict';

  const SEEN_KEY = 'omnitrackr_home_seen';
  const INVITE_HIDE_KEY = 'omnitrackr_home_invite_hidden';
  // A reload within this long keeps the same "since", so the counts don't vanish on refresh.
  const SAME_VISIT_MS = 30 * 60 * 1000;
  const STALE_MS = 5 * 60 * 1000;
  const DAY_MS = 24 * 60 * 60 * 1000;
  const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime', 'video-games': 'loadVideoGames',
    music: 'loadMusic', books: 'loadBooks', manga: 'loadManga', podcasts: 'loadPodcasts', audiobooks: 'loadAudiobooks',
  };
  const DONE_WORD = {
    movies: 'watched', 'tv-shows': 'finished', anime: 'finished', 'video-games': 'finished playing',
    music: 'listened to', books: 'read', manga: 'read', podcasts: 'listened to', audiobooks: 'listened to',
  };
  const state = { epoch: 0, request: null, data: null, loadedAt: 0, since: null };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  async function post(path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      throw new Error(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    }
    return data;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function plural(n, one, many) {
    return `${n} ${n === 1 ? one : many}`;
  }

  function accountKey() {
    try {
      const raw = localStorage.getItem('omnitrackr_user');
      const user = raw ? JSON.parse(raw) : null;
      return user && (user.id || user.username) ? String(user.id || user.username) : 'me';
    } catch (error) {
      return 'me';
    }
  }

  // When this device last showed the home screen, before this visit. Stored per account.
  function readSince(now = Date.now()) {
    let seen = {};
    try { seen = JSON.parse(localStorage.getItem(SEEN_KEY) || '{}') || {}; } catch (error) { seen = {}; }
    const mine = seen[accountKey()] || {};
    let { last, prev } = mine;
    if (!last || now - last > SAME_VISIT_MS) {
      prev = last || null;
    }
    last = now;
    seen[accountKey()] = { last, prev: prev || null };
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch (error) { /* storage off */ }
    return prev ? new Date(prev) : null;
  }

  function localDay(iso) {
    const [y, m, d] = String(iso).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
  }

  function dayDiff(iso, now = new Date()) {
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((localDay(iso) - today) / DAY_MS);
  }

  // Past days count back ("2 days ago"), coming days name the weekday ("on Friday"),
  // so an episode out last Friday and one due next Friday never read the same.
  function dayLabel(iso, now = new Date()) {
    const diff = dayDiff(iso, now);
    if (diff === 0) return 'today';
    if (diff === -1) return 'yesterday';
    if (diff === 1) return 'tomorrow';
    if (diff < -1 && diff > -7) return `${-diff} days ago`;
    if (diff > 1 && diff < 7) return `on ${WEEKDAYS[localDay(iso).getDay()]}`;
    return `on ${localDay(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
  }

  function ago(iso, now = Date.now()) {
    const at = Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
    if (!Number.isFinite(at)) return '';
    const minutes = Math.max(0, Math.round((now - at) / 60000));
    if (minutes < 60) return minutes <= 1 ? 'just now' : `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.round(hours / 24);
    return days === 1 ? 'yesterday' : `${days}d ago`;
  }

  function sinceLabel(since, now = new Date()) {
    if (!since) return 'This week';
    const days = Math.floor((now - since) / DAY_MS);
    if (days < 1) return 'Since earlier today';
    if (days === 1) return 'Since yesterday';
    if (days < 7) return `Since ${WEEKDAYS[since.getDay()]}`;
    return `Since ${since.toLocaleDateString(undefined, { month: 'long', day: 'numeric' })}`;
  }

  // One line for the welcome strip and the card heading, e.g. "2 new episodes and 3 updates from friends".
  function summaryParts(counts) {
    const parts = [];
    if (counts.episodes) parts.push(plural(counts.episodes, 'new episode', 'new episodes'));
    if (counts.releases) parts.push(plural(counts.releases, 'release', 'releases'));
    if (counts.friends) parts.push(plural(counts.friends, 'update from friends', 'updates from friends'));
    return parts;
  }

  function joinParts(parts) {
    if (parts.length < 2) return parts[0] || '';
    return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
  }

  function cover(src, label) {
    const wrap = el('span', 'home-news__cover');
    if (src) {
      const img = el('img');
      img.src = src;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => { img.remove(); wrap.textContent = label.slice(0, 1).toUpperCase(); }, { once: true });
      wrap.append(img);
    } else {
      wrap.textContent = (label || '?').slice(0, 1).toUpperCase();
    }
    return wrap;
  }

  function showRow(show, now) {
    const row = el('li', 'home-news__row');
    row.dataset.format = show.category;
    row.append(cover(show.image, show.title));
    const body = el('div', 'home-news__body');
    body.append(el('strong', 'home-news__title', show.title));
    const out = show.out;
    const line = el('p', 'home-news__line');
    if (out) {
      const badge = el('span', `home-news__pill${out.waiting ? ' home-news__pill--new' : ''}`,
        out.waiting ? 'Ready to watch' : out.waiting === false ? 'Caught up' : `Out ${dayLabel(out.date, now)}`);
      line.append(badge, document.createTextNode(` ${out.code}${out.name ? `: ${out.name}` : ''}`));
      if (out.waiting) line.append(document.createTextNode(` · out ${dayLabel(out.date, now)}`));
    } else if (show.next) {
      line.append(el('span', 'home-news__pill', `Next ${dayLabel(show.next.date, now)}`),
        document.createTextNode(` ${show.next.code}${show.next.name ? `: ${show.next.name}` : ''}`));
    }
    body.append(line);
    const meta = [];
    if (show.progress) meta.push(`You're on ${show.progress}`);
    if (out && show.next) meta.push(`next ${show.next.code} ${dayLabel(show.next.date, now)}`);
    if (show.network) meta.push(show.network);
    if (meta.length) body.append(el('p', 'home-news__meta', meta.join(' · ')));
    row.append(body);
    const open = el('button', 'home-news__btn', 'Open');
    open.type = 'button';
    open.setAttribute('aria-label', `Open ${show.library_title || show.title} in your library`);
    open.addEventListener('click', () => {
      if (typeof openLibraryItem === 'function') {
        openLibraryItem({ category: show.category, id: show.item_id, title: show.library_title || show.title },
          { button: open, reasonElement: $('homeNewsStatus') });
      }
    });
    row.append(open);
    return row;
  }

  function releaseRow(release, now) {
    const row = el('li', 'home-news__row home-news__row--release');
    row.dataset.format = release.category;
    row.append(cover(null, release.title));
    const body = el('div', 'home-news__body');
    body.append(el('strong', 'home-news__title', release.title));
    const line = el('p', 'home-news__line');
    line.append(el('span', `home-news__pill${release.new ? ' home-news__pill--new' : ''}`, 'Out now'),
      document.createTextNode(` ${release.category_label || ''} · released ${dayLabel(release.date, now)}`));
    body.append(line);
    row.append(body);
    const link = el('a', 'home-news__btn', 'Details');
    link.href = '/release-radar';
    row.append(link);
    return row;
  }

  function friendLine(item) {
    if (item.type === 'burst') return `added ${plural(item.count, 'title', 'titles')}`;
    if (item.kind === 'finished') return `${DONE_WORD[item.category] || 'finished'} ${item.title}`;
    if (item.kind === 'reviewed') return `reviewed ${item.title}`;
    if (item.kind === 'rated') return `rated ${item.title}`;
    return `added ${item.title}`;
  }

  function friendRow(item, now) {
    const row = el('li', 'home-news__row home-news__row--friend');
    const titles = item.type === 'burst' ? item.titles || [] : [item];
    row.append(cover(titles[0]?.image, titles[0]?.title || item.friend.username));
    const body = el('div', 'home-news__body');
    const who = el('p', 'home-news__who');
    who.append(el('strong', '', item.friend.username), document.createTextNode(` ${friendLine(item)}`));
    if (item.type === 'title' && item.rating !== null && item.rating !== undefined) {
      who.append(el('span', 'home-news__rating', ` ★ ${Number(item.rating).toFixed(Number.isInteger(item.rating) ? 0 : 1)}`));
    }
    body.append(who);
    const meta = [ago(item.at, now.getTime())];
    if (item.type === 'title') meta.unshift(item.category_label);
    if (item.type === 'burst') meta.unshift(titles.slice(0, 3).map(title => title.title).join(', '));
    if (item.type === 'title' && item.in_library) meta.push('in your library too');
    body.append(el('p', 'home-news__meta', meta.filter(Boolean).join(' · ')));
    row.append(body);
    if (item.type === 'title') {
      const actions = el('div', 'home-news__actions');
      const cheer = el('button', 'home-news__btn home-news__btn--cheer', item.cheered ? 'Cheered' : 'Cheer');
      cheer.type = 'button';
      cheer.disabled = Boolean(item.cheered);
      cheer.setAttribute('aria-pressed', String(Boolean(item.cheered)));
      cheer.setAttribute('aria-label', `Cheer ${item.friend.username} for ${item.title}`);
      cheer.addEventListener('click', async () => {
        cheer.disabled = true;
        try {
          await post('/api/friend-feed/cheer', { friend_id: item.friend.id, category: item.category, item_id: item.item_id });
          item.cheered = true;
          cheer.textContent = 'Cheered';
          cheer.setAttribute('aria-pressed', 'true');
          setStatus(`Cheered ${item.friend.username}. They'll get a note.`);
        } catch (error) {
          cheer.disabled = false;
          setStatus(error.message);
        }
      });
      actions.append(cheer);
      if (!item.in_library) {
        const save = el('button', 'home-news__btn', 'Save');
        save.type = 'button';
        save.setAttribute('aria-label', `Save ${item.title} to your library`);
        save.addEventListener('click', async () => {
          save.disabled = true;
          try {
            const data = await post('/api/friend-feed/save', {
              friend_id: item.friend.id, category: item.category, item_id: item.item_id, next_up: false,
            });
            item.in_library = true;
            save.remove();
            setStatus(data.created ? `${item.title} is in your library.` : `${item.title} was already in your library.`);
            const loader = window[LOADERS[data.category]];
            if (data.created && typeof loader === 'function') {
              try { loader(); } catch (error) { /* refreshes on the next visit */ }
            }
          } catch (error) {
            save.disabled = false;
            setStatus(error.message);
          }
        });
        actions.append(save);
      }
      row.append(actions);
    }
    return row;
  }

  function setStatus(text) {
    const status = $('homeNewsStatus');
    if (status) status.textContent = text || '';
  }

  function inviteHidden() {
    try { return localStorage.getItem(INVITE_HIDE_KEY) === '1'; } catch (error) { return false; }
  }

  async function copyInvite(button) {
    button.disabled = true;
    try {
      const data = await post('/api/friends/invite-link', {});
      if (navigator.share && window.matchMedia?.('(pointer: coarse)').matches) {
        try { await navigator.share({ text: data.text, url: data.url }); setStatus(''); return; } catch (error) { /* fall back to copying */ }
      }
      await navigator.clipboard.writeText(data.url);
      setStatus('Invite link copied. Anyone who joins with it becomes your friend straight away.');
    } catch (error) {
      setStatus('Could not make an invite link right now. You can find it in Friends.');
    } finally {
      button.disabled = false;
    }
  }

  function renderInvite(box) {
    const wrap = el('div', 'home-news__invite');
    wrap.append(el('p', 'home-news__empty', "When friends finish or rate something, it shows up here, and you can cheer them on. Nobody's here yet."));
    const actions = el('div', 'home-news__actions');
    const invite = el('button', 'home-news__btn home-news__btn--primary', 'Copy an invite link');
    invite.type = 'button';
    invite.addEventListener('click', () => copyInvite(invite));
    const hide = el('button', 'home-news__link', 'Hide');
    hide.type = 'button';
    hide.addEventListener('click', () => {
      try { localStorage.setItem(INVITE_HIDE_KEY, '1'); } catch (error) { /* storage off */ }
      if (state.data) render(state.data);
    });
    actions.append(invite, hide);
    wrap.append(actions);
    box.append(wrap);
  }

  function renderHeroLine(counts, since, now) {
    const line = $('homeHeroNews');
    if (!line) return;
    const parts = summaryParts(counts);
    line.replaceChildren();
    if (!parts.length) { line.hidden = true; return; }
    const link = el('a', 'home-hero__news-link');
    link.href = '#homeNews';
    link.append(el('span', 'home-hero__news-dot'), document.createTextNode(`${sinceLabel(since, now)}: ${joinParts(parts)}`));
    link.addEventListener('click', event => {
      const card = $('homeNews');
      if (!card || card.hidden) return;
      event.preventDefault();
      card.scrollIntoView({ behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    });
    line.append(link);
    line.hidden = false;
  }

  function render(data, now = new Date()) {
    const section = $('homeNews');
    if (!section || !data) return;
    state.data = data;
    state.loadedAt = Date.now();
    const shows = Array.isArray(data.shows) ? data.shows : [];
    const releases = Array.isArray(data.releases) ? data.releases : [];
    const friends = data.friends || {};
    const friendItems = Array.isArray(friends.items) ? friends.items : [];
    const counts = data.counts || {};

    const showBox = $('homeNewsShows');
    const showList = $('homeNewsShowList');
    if (showBox && showList) {
      showList.replaceChildren(...shows.map(show => showRow(show, now)), ...releases.map(release => releaseRow(release, now)));
      showBox.hidden = !(shows.length || releases.length);
    }

    const friendBox = $('homeNewsFriends');
    const friendList = $('homeNewsFriendList');
    const friendFoot = $('homeNewsFriendsMore');
    const noFriends = !Number(friends.friends);
    if (friendBox && friendList) {
      friendList.replaceChildren(...friendItems.map(item => friendRow(item, now)));
      friendBox.querySelector('.home-news__invite')?.remove();
      if (!friendItems.length && noFriends && !inviteHidden()) renderInvite(friendBox);
      if (!friendItems.length && !noFriends) {
        friendList.append(el('li', 'home-news__empty', 'Your friends have been quiet this month. Their next finish or rating lands here.'));
      }
      if (friendFoot) friendFoot.hidden = !friendItems.length;
      friendBox.hidden = !(friendItems.length || !noFriends || !inviteHidden());
    }

    const since = state.since;
    const parts = summaryParts(counts);
    const eyebrow = $('homeNewsEyebrow');
    if (eyebrow) eyebrow.textContent = sinceLabel(since, now);
    const summary = $('homeNewsSummary');
    if (summary) {
      summary.textContent = parts.length
        ? `${joinParts(parts)[0].toUpperCase()}${joinParts(parts).slice(1)}.`
        : shows.length ? 'Nothing new since you last looked. Here is what is on this week.' : '';
    }
    const anything = !(showBox?.hidden ?? true) || !(friendBox?.hidden ?? true);
    section.dataset.columns = String([showBox, friendBox].filter(box => box && !box.hidden).length);
    section.hidden = !anything;
    renderHeroLine(counts, since, now);
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < 60 * 1000) return state.request;
    const epoch = state.epoch;
    if (!state.data) state.since = readSince();
    const query = state.since ? `?since=${encodeURIComponent(state.since.toISOString())}` : '';
    const request = fetch(`${apiBase()}/api/home/today${query}`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch++;
    state.data = null;
    state.request = null;
    state.loadedAt = 0;
    state.since = null;
    const section = $('homeNews');
    if (section) section.hidden = true;
    const line = $('homeHeroNews');
    if (line) { line.hidden = true; line.replaceChildren(); }
    ['homeNewsShowList', 'homeNewsFriendList'].forEach(id => $(id)?.replaceChildren());
    setStatus('');
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state.data && Date.now() - state.loadedAt > STALE_MS) refresh(true);
  });

  window.OmniHomeToday = { refresh, reset, render };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { refresh, reset, render, readSince, dayLabel, sinceLabel, summaryParts, joinParts, friendLine, ago, state };
  }
})();
