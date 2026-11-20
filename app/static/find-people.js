// Find people: the third view on the friends feed tab, the "People you might follow" rail card,
// and the /#find-people link the new-follower notice opens. Data comes from /api/people/*
// (app/people_to_follow.py). Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const state = { loaded: false, loading: false, request: 0, rail: 0, undoTimer: null };
  const HASH = '#find-people';

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
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

  // Same-site paths only: everything the server sends starts with "/" and never "//".
  function safePath(path) {
    return typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') ? path : null;
  }

  function safeImage(url) {
    if (safePath(url)) return url;
    return typeof url === 'string' && url.startsWith('https://') ? url : null;
  }

  function link(className, text, path) {
    const href = safePath(path);
    const node = el(href ? 'a' : 'span', className, text);
    if (href) node.href = href;
    return node;
  }

  function button(className, text, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  // Eight colour buckets from the name, so initials don't all look alike.
  function hue(name) {
    let total = 0;
    for (const ch of String(name || '')) total = (total * 31 + ch.charCodeAt(0)) % 9973;
    return total % 8;
  }

  function avatar(person, size = '') {
    const src = safePath(person.avatar);
    if (src) {
      const img = el('img', `people-avatar${size}`);
      img.src = src;
      img.alt = '';
      img.loading = 'lazy';
      img.dataset.fallbackSrc = '/static/default-avatar.svg';
      return img;
    }
    const initial = el('span', `people-avatar${size} people-avatar--h${hue(person.username)}`,
      (person.username || '?').trim().charAt(0).toUpperCase() || '?');
    initial.setAttribute('aria-hidden', 'true');
    return initial;
  }

  function count(name) {
    api('/api/people/event', { json: { name } }).catch(() => {});
  }

  function say(text) {
    const status = $('peopleStatus');
    if (status) status.textContent = text || '';
  }

  // ---------------------------------------------------------------- buttons

  function followButton(person, source, onChange) {
    const node = button('action-btn people-follow', person.source === 'back' ? 'Follow back' : 'Follow');
    node.setAttribute('aria-pressed', 'false');
    node.setAttribute('aria-label', `${person.source === 'back' ? 'Follow back' : 'Follow'} ${person.username}`);
    node.addEventListener('click', async () => {
      const following = node.getAttribute('aria-pressed') === 'true';
      node.disabled = true;
      try {
        if (following) {
          await api(`/api/follows/${encodeURIComponent(person.id)}`, { method: 'DELETE' });
          node.textContent = person.source === 'back' ? 'Follow back' : 'Follow';
          node.setAttribute('aria-pressed', 'false');
          node.classList?.remove('people-follow--on');
        } else {
          await api(`/api/follows/${encodeURIComponent(person.id)}?source=${encodeURIComponent(source)}`, { method: 'POST' });
          node.textContent = 'Following';
          node.setAttribute('aria-pressed', 'true');
          node.classList?.add('people-follow--on');
        }
        node.setAttribute('aria-label', `${node.textContent} ${person.username}`);
        // The Following view fetches again (now if it's on screen, else when it next opens).
        window.OmniFollowing?.stale?.();
        onChange?.(!following);
      } catch (error) {
        say(error.message);
      } finally {
        node.disabled = false;
      }
    });
    return node;
  }

  function friendButton(person) {
    const node = button('action-btn secondary people-follow', person.friend_pending ? 'Request sent' : 'Add as friend');
    if (person.friend_pending) {
      node.disabled = true;
      return node;
    }
    node.setAttribute('aria-label', `Send ${person.username} a friend request`);
    node.addEventListener('click', async () => {
      node.disabled = true;
      try {
        await api('/friends/request', { json: { receiver_username: person.username } });
        node.textContent = 'Request sent';
        count('friend_back');
      } catch (error) {
        node.disabled = false;
        say(error.message);
      }
    });
    return node;
  }

  function showUndo(person, restore) {
    const box = $('peopleUndo');
    if (!box) return;
    clearTimeout(state.undoTimer);
    const undo = button('people-undo__btn', 'Undo', async () => {
      box.hidden = true;
      try {
        await api(`/api/people/dismiss/${encodeURIComponent(person.id)}`, { method: 'DELETE' });
        restore();
      } catch (error) {
        say(error.message);
      }
    });
    box.replaceChildren(el('span', '', `You won't see ${person.username} here again.`), undo);
    box.hidden = false;
    state.undoTimer = setTimeout(() => { box.hidden = true; }, 8000);
  }

  function dismissButton(person, card) {
    const node = button('people-card__dismiss', '×');
    node.setAttribute('aria-label', `Not for me: hide ${person.username}`);
    node.title = 'Not for me';
    node.addEventListener('click', async () => {
      node.disabled = true;
      try {
        await api(`/api/people/dismiss/${encodeURIComponent(person.id)}`, { method: 'POST' });
        card.hidden = true;
        showUndo(person, () => { card.hidden = false; node.disabled = false; });
      } catch (error) {
        node.disabled = false;
        say(error.message);
      }
    });
    return node;
  }

  // ---------------------------------------------------------------- cards

  function posters(titles) {
    const list = el('ul', 'people-card__titles');
    list.setAttribute('aria-label', 'Titles you have in common');
    (titles || []).slice(0, 3).forEach(title => {
      const item = el('li', 'people-title');
      const holder = link('people-title__link', '', title.url);
      const art = el('span', 'people-title__art');
      const image = safeImage(title.image);
      if (image) {
        const img = el('img');
        img.src = image;
        img.alt = '';
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener?.('error', () => img.remove(), { once: true });
        art.append(img);
      } else {
        art.textContent = (title.title || '?').trim().charAt(0).toUpperCase();
      }
      holder.append(art, el('span', 'people-title__name', title.title));
      item.append(holder);
      list.append(item);
    });
    return list;
  }

  function card(person, source) {
    const node = el('li', `people-card people-card--${person.source || source}`);
    node.dataset.personId = String(person.id);
    const head = el('div', 'people-card__head');
    head.append(avatar(person));
    const who = el('div', 'people-card__who');
    who.append(link('people-card__name', person.username, person.profile_url));
    head.append(who, dismissButton(person, node));
    node.append(head);
    if (person.reason) node.append(el('p', 'people-card__reason', person.reason));
    if (person.bio) node.append(el('p', 'people-card__bio', person.bio));
    if (person.titles && person.titles.length) node.append(posters(person.titles));
    const actions = el('div', 'people-card__actions');
    actions.append(followButton(person, person.source || source));
    if (safePath(person.profile_url)) actions.append(link('people-card__link', 'See profile', person.profile_url));
    if (safePath(person.compare_url)) actions.append(link('people-card__link', 'Compare tastes', person.compare_url));
    node.append(actions);
    return node;
  }

  function backRow(person) {
    const row = el('li', 'people-back__item');
    row.append(avatar(person, ' people-avatar--sm'));
    const who = el('div', 'people-back__who');
    who.append(person.profile_url ? link('people-card__name', person.username, person.profile_url)
      : el('span', 'people-card__name', person.username));
    who.append(el('span', 'people-back__when', person.reason));
    row.append(who);
    if (person.can_follow) row.append(followButton(person, 'back'));
    else if (person.can_friend || person.friend_pending) row.append(friendButton(person));
    return row;
  }

  function youBox(you) {
    const box = $('peopleYou');
    if (!box) return;
    box.replaceChildren();
    box.hidden = true;
    if (!you) return;
    if (!you.profile_enabled) {
      box.append(el('h4', 'people-you__title', 'Let people find you too'),
        el('p', 'people-you__text', 'Only members with a public profile can be followed or suggested. Yours is off, so nobody can follow you back yet. You choose what it shows, and private categories never appear.'),
        button('action-btn people-you__btn', 'Turn on my public profile', () => {
          count('profile_prompt');
          window.location.hash = '#public-profile';
        }));
      box.hidden = false;
    } else if (you.allow_followers === false || you.suggest_me === false) {
      const text = you.allow_followers === false
        ? 'Your profile is public, but followers are switched off, so nobody can follow you back.'
        : "Your profile isn't suggested to other members. You can still follow people, and they can follow you from your profile.";
      box.append(el('p', 'people-you__text', text), button('people-you__link', 'Change in Settings', () => {
        window.location.hash = '#followers';
      }));
      box.hidden = false;
    }
    const hint = $('peopleTasteHint');
    if (hint) {
      const needed = you.needs_titles || 0;
      hint.hidden = !needed;
      hint.textContent = needed
        ? `Add ${needed} more title${needed === 1 ? '' : 's'} to your library and we can match you with people by taste.`
        : '';
    }
  }

  function render(data) {
    const back = $('peopleBack');
    const backList = $('peopleBackList');
    const groupsHost = $('peopleGroups');
    if (!groupsHost) return;
    const followBack = data.follow_back || [];
    if (back && backList) {
      backList.replaceChildren(...followBack.map(backRow));
      back.hidden = !followBack.length;
    }
    const groups = (data.groups || []).filter(group => group.people && group.people.length);
    groupsHost.replaceChildren(...groups.map(group => {
      const section = el('section', `people-group people-group--${group.key}`);
      const heading = el('h4', 'people-group__title', group.title);
      heading.id = `peopleGroup-${group.key}`;
      section.setAttribute('aria-labelledby', heading.id);
      section.append(heading);
      if (group.note) section.append(el('p', 'people-group__note', group.note));
      const list = el('ul', 'people-grid');
      list.append(...group.people.map(person => card(person, group.key)));
      section.append(list);
      return section;
    }));
    youBox(data.you);
    if (groups.length || followBack.length) say('');
    else if (data.you && data.you.library < 5) say('Nobody to suggest yet. Rate a few more titles and check back: suggestions start from what you track.');
    else say('Nobody new to suggest right now. As more members switch their public profile on, people with your taste show up here.');
  }

  async function load(force = false) {
    if (!$('peoplePanel') || state.loading || (state.loaded && !force)) return;
    state.loading = true;
    const request = ++state.request;
    if (!state.loaded) say('Looking for people…');
    try {
      const data = await api('/api/people/suggestions');
      if (request !== state.request) return;
      render(data);
      state.loaded = true;
    } catch (error) {
      if (request === state.request) say(error.message);
    } finally {
      if (request === state.request) state.loading = false;
    }
  }

  function refresh() {
    state.loaded = false;
    state.loading = false;
    return load(true);
  }

  // ---------------------------------------------------------------- rail

  function railRow(person) {
    const row = el('li', 'follow-person people-rail__item');
    row.append(avatar(person, ' people-avatar--sm'));
    const who = el('div', 'people-rail__who');
    who.append(link('follow-person__name', person.username, person.profile_url));
    if (person.reason) who.append(el('span', 'follow-person__why', person.reason));
    row.append(who, followButton(person, person.source === 'back' ? 'back' : 'rail'));
    return row;
  }

  function renderRail(data) {
    const host = $('followSuggestions');
    const list = $('followSuggestionsList');
    if (!host || !list) return;
    const people = (data && data.people) || [];
    list.replaceChildren(...people.map(railRow));
    host.hidden = !people.length;
  }

  async function loadRail() {
    if (!$('followSuggestions')) return;
    const request = ++state.rail;
    try {
      const data = await api('/api/people/rail');
      if (request === state.rail) renderRail(data);
    } catch (error) { /* the rail card just stays hidden */ }
  }

  // Opening the friends feed tab loads the rail, and the people view when it's the one showing.
  function open() {
    loadRail();
    const root = document.querySelector?.('.social[data-social-view]');
    if (root && root.dataset.socialView === 'people') load();
  }

  function reset() {
    state.request++;
    state.rail++;
    state.loaded = false;
    state.loading = false;
    $('peopleGroups')?.replaceChildren();
    $('peopleBackList')?.replaceChildren();
    $('followSuggestionsList')?.replaceChildren();
    const host = $('followSuggestions');
    if (host) host.hidden = true;
  }

  function showPeople(focus = true) {
    const feed = window.OmniFriendFeed;
    if (feed && typeof feed.showView === 'function') feed.showView('people', focus);
    else load();
  }

  function openFromHash(attempt = 0) {
    if (window.location.hash !== HASH) return;
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn) {
      if (attempt < 10) setTimeout(() => openFromHash(attempt + 1), 500);
      return;
    }
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
    if (typeof navigateLibraryTab === 'function') navigateLibraryTab('friends-feed');
    else if (typeof switchTab === 'function') switchTab('friends-feed');
    showPeople(false);
  }

  // Signing out resets the friends feed (auth.js); clear these lists along with it.
  function wrapFeedReset() {
    const original = window.resetFriendFeed;
    if (original && original.__peopleWrapped) return;
    const wrapped = function () {
      if (typeof original === 'function') original.apply(this, arguments);
      reset();
    };
    wrapped.__peopleWrapped = true;
    wrapped.__followsWrapped = original?.__followsWrapped;
    window.resetFriendFeed = wrapped;
  }

  function init() {
    wrapFeedReset();
    $('peopleRefresh')?.addEventListener('click', () => refresh());
    document.querySelectorAll('[data-open-people]').forEach(node => node.addEventListener('click', () => showPeople(true)));
    setTimeout(openFromHash, 700);
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.OmniPeople = { load, refresh, open, loadRail, renderRail, render, reset, showPeople };
  if (typeof module !== 'undefined' && module.exports) module.exports = { ...window.OmniPeople, hue, safePath, safeImage, card, backRow };
  if (typeof document === 'undefined' || !document.addEventListener) return;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
