// People you follow: the Following section on the friends feed tab, suggestions, and the
// follower settings under Settings → Public profile. Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const state = { loaded: false, loading: false, request: 0, settings: null };

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  async function api(path, options = {}) {
    const init = { ...options, headers: { Accept: 'application/json', ...(options.headers || {}) } };
    if (options.json !== undefined) {
      init.method = init.method || 'PUT';
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

  function link(className, text, path) {
    const href = safePath(path);
    const node = el(href ? 'a' : 'span', className, text);
    if (href) node.href = href;
    return node;
  }

  function day(iso) {
    const date = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function rating(value) {
    return typeof value === 'number' ? `${Number.isInteger(value) ? value : value.toFixed(1)}/10` : '';
  }

  function verb(item) {
    if (item.kind === 'review') return 'reviewed';
    if (item.kind === 'collection') return 'published a collection';
    return item.repeat ? 'revisited' : 'finished';
  }

  // ---------------------------------------------------------------- Following feed

  function cover(item) {
    const holder = el('span', 'ffollow__cover');
    const image = safePath(item.image) || (typeof item.image === 'string' && item.image.startsWith('https://') ? item.image : null);
    if (image) {
      const img = el('img');
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.remove(), { once: true });
      holder.append(img);
    } else {
      holder.textContent = item.kind === 'collection' ? '✦' : (item.title || '?').trim().charAt(0).toUpperCase();
    }
    return holder;
  }

  function entry(item) {
    const row = el('li', `ffollow__item ffollow__item--${item.kind}`);
    row.append(cover(item));
    const body = el('div', 'ffollow__body');
    const head = el('p', 'ffollow__line');
    head.append(link('ffollow__who', item.username, item.profile_url), document.createTextNode(` ${verb(item)} `),
      link('ffollow__title', item.title, item.url));
    body.append(head);
    const meta = el('p', 'ffollow__meta');
    const bits = [item.label, rating(item.rating), item.kind === 'collection' && item.count ? `${item.count} picks` : '',
      day(item.date)].filter(Boolean);
    meta.textContent = bits.join(' · ');
    body.append(meta);
    if (item.spoilers) body.append(el('p', 'ffollow__excerpt ffollow__excerpt--spoiler', 'Contains spoilers. Open the review to read it.'));
    else if (item.excerpt) body.append(el('p', 'ffollow__excerpt', item.excerpt));
    row.append(body);
    return row;
  }

  function renderFeed(data) {
    const list = $('followingList');
    const status = $('followingStatus');
    if (!list || !status) return;
    list.replaceChildren(...(data.items || []).map(entry));
    if (data.items && data.items.length) status.textContent = '';
    else if (data.following) status.textContent = 'Nothing new from the people you follow in the last two months.';
    else status.textContent = 'Follow members from their public profile to see their new reviews, collections and diary here.';
  }

  function person(personData, action) {
    const row = el('li', 'follow-person');
    row.append(link('follow-person__name', personData.username, personData.profile_url));
    if (personData.reason) row.append(el('span', 'follow-person__why', personData.reason));
    if (action) row.append(action);
    return row;
  }

  function followButton(personData, onDone) {
    const button = el('button', 'action-btn follow-person__btn', 'Follow');
    button.type = 'button';
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await api(`/api/follows/${encodeURIComponent(personData.id)}`, { method: 'POST' });
        button.textContent = 'Following';
        onDone?.();
      } catch (error) {
        button.disabled = false;
        const status = $('followingStatus');
        if (status) status.textContent = error.message;
      }
    });
    return button;
  }

  function renderSuggestions(people) {
    const host = $('followSuggestions');
    const list = $('followSuggestionsList');
    if (!host || !list) return;
    list.replaceChildren(...people.map(entryData => person(entryData, followButton(entryData, () => refresh()))));
    host.hidden = !people.length;
  }

  async function load(force = false) {
    if (!$('followingFeed') || state.loading || (state.loaded && !force)) return;
    state.loading = true;
    const request = ++state.request;
    const status = $('followingStatus');
    if (status && !state.loaded) status.textContent = 'Loading…';
    try {
      const [feedData, suggestData] = await Promise.all([
        api('/api/follows/feed'),
        api('/api/follows/suggestions').catch(() => ({ people: [] })),
      ]);
      if (request !== state.request) return;
      renderFeed(feedData);
      renderSuggestions(suggestData.people || []);
      state.loaded = true;
    } catch (error) {
      if (request === state.request && status) status.textContent = error.message;
    } finally {
      if (request === state.request) state.loading = false;
    }
  }

  function refresh() {
    state.loaded = false;
    state.loading = false;
    return load(true);
  }

  function reset() {
    state.request++;
    state.loaded = false;
    state.loading = false;
    state.settings = null;
    $('followingList')?.replaceChildren();
    $('followSuggestionsList')?.replaceChildren();
    const host = $('followSuggestions');
    if (host) host.hidden = true;
  }

  // ---------------------------------------------------------------- settings

  function message(id, text) {
    const node = $(id);
    if (!node) return;
    node.textContent = text || '';
    node.style.display = text ? 'block' : 'none';
  }

  function settingsButton(text, onClick) {
    const button = el('button', 'follow-person__btn follow-person__btn--quiet', text);
    button.type = 'button';
    button.addEventListener('click', async () => {
      button.disabled = true;
      message('followError', '');
      try {
        applySettings(await onClick());
      } catch (error) {
        button.disabled = false;
        message('followError', error.message);
      }
    });
    return button;
  }

  function fillList(id, people, makeButton, empty) {
    const list = $(id);
    if (!list) return;
    if (!people.length) {
      list.replaceChildren(el('li', 'follow-person follow-person--empty', empty));
      return;
    }
    list.replaceChildren(...people.map(entryData => person(entryData, makeButton(entryData))));
  }

  function applySettings(data) {
    state.settings = data;
    const allow = $('followAllow');
    const email = $('followEmail');
    if (allow) allow.checked = data.allow_followers !== false;
    if (email) email.checked = data.email_following !== false;
    const counts = $('followCounts');
    if (counts) {
      const followers = data.counts?.followers || 0;
      const following = data.counts?.following || 0;
      counts.textContent = `${followers} follower${followers === 1 ? '' : 's'} · following ${following}`
        + (data.profile_enabled ? '' : '. Switch your public profile on so people can follow you.');
    }
    fillList('followFollowers', data.followers || [], entryData => settingsButton('Remove', () =>
      api(`/api/follows/followers/${encodeURIComponent(entryData.id)}`, { method: 'DELETE' })), 'Nobody follows you yet.');
    fillList('followFollowing', data.following || [], entryData => settingsButton('Unfollow', async () => {
      await api(`/api/follows/${encodeURIComponent(entryData.id)}`, { method: 'DELETE' });
      state.loaded = false;
      return api('/api/follows/settings');
    }), "You don't follow anyone yet.");
    const removed = data.removed || [];
    const wrap = $('followRemovedWrap');
    if (wrap) wrap.hidden = !removed.length;
    fillList('followRemoved', removed, entryData => settingsButton('Allow again', () =>
      api(`/api/follows/removed/${encodeURIComponent(entryData.id)}`, { method: 'DELETE' })), '');
  }

  async function loadSettings() {
    if (!$('followSettings')) return;
    try {
      applySettings(await api('/api/follows/settings'));
    } catch (error) {
      message('followError', error.message);
    }
  }

  async function saveSwitch(input, field) {
    const wanted = input.checked;
    if (field === 'allow_followers' && !wanted && (state.settings?.counts?.followers || 0) > 0
        && typeof window.confirm === 'function'
        && !window.confirm('Turning this off removes everyone who follows you now. Continue?')) {
      input.checked = true;
      return;
    }
    input.disabled = true;
    message('followError', '');
    message('followSuccess', '');
    try {
      applySettings(await api('/api/follows/settings', { json: { [field]: wanted } }));
      message('followSuccess', field === 'allow_followers'
        ? (wanted ? 'People can follow your profile.' : 'Nobody can follow your profile now.')
        : (wanted ? 'Your weekly email includes people you follow.' : 'Your weekly email leaves out people you follow.'));
    } catch (error) {
      input.checked = !wanted;
      message('followError', error.message);
    } finally {
      input.disabled = false;
    }
  }

  function wrapAccountLoader() {
    const original = window.loadAccountInfo;
    if (typeof original !== 'function' || original.__followsWrapped) return;
    const wrapped = async function () {
      const result = await original.apply(this, arguments);
      loadSettings();
      return result;
    };
    wrapped.__followsWrapped = true;
    wrapped.__publicProfileWrapped = original.__publicProfileWrapped;
    window.loadAccountInfo = wrapped;
  }

  async function openFromHash(attempt = 0) {
    if (window.location.hash !== '#followers') return;
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn || typeof window.openAccountModal !== 'function') {
      if (attempt < 10) setTimeout(() => openFromHash(attempt + 1), 500);
      return;
    }
    await window.openAccountModal();
    const section = $('followSettings');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
    if (section && typeof section.focus === 'function') section.focus({ preventScroll: true });
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  // Signing out resets the friends feed (auth.js); clear this section along with it.
  function wrapFeedReset() {
    const original = window.resetFriendFeed;
    if (original && original.__followsWrapped) return;
    const wrapped = function () {
      if (typeof original === 'function') original.apply(this, arguments);
      reset();
    };
    wrapped.__followsWrapped = true;
    window.resetFriendFeed = wrapped;
  }

  function init() {
    wrapFeedReset();
    $('followAllow')?.addEventListener('change', event => saveSwitch(event.target, 'allow_followers'));
    $('followEmail')?.addEventListener('change', event => saveSwitch(event.target, 'email_following'));
    $('followingRefresh')?.addEventListener('click', () => refresh());
    wrapAccountLoader();
    setTimeout(openFromHash, 600);
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.OmniFollowing = { load, refresh, reset, loadSettings, applySettings, renderFeed };
  if (typeof module !== 'undefined' && module.exports) module.exports = { ...window.OmniFollowing, verb, safePath, rating };
  if (typeof document === 'undefined') return;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
