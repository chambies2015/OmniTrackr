// "Yearbook" on the member home, from late November until two weeks after signing closes: start
// yours, what's new in it (notes waiting to be let in, new notes), friends' yearbooks to sign, and the
// closed book in January. The yearbook itself lives on /yearbook (yearbook.js, app/yearbook.py). Server
// text is only set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 60 * 1000;
  const state = { epoch: 0, request: null, loadedAt: 0 };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);

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

  function safePath(path) {
    return typeof path === 'string' && /^\/yearbook(?:\/[A-Za-z0-9_-]{16,40})?(?:#[a-z]+)?$/.test(path) ? path : '/yearbook';
  }

  function title(data) {
    if (data.stage === 'start') return `Your ${data.year} yearbook`;
    if (data.stage === 'closed') return `Class of ${data.year}`;
    return `Your ${data.year} yearbook`;
  }

  function render(data) {
    const section = $('yearbookHome');
    if (!section) return;
    if (!data || !data.show) {
      section.hidden = true;
      section.dataset.status = '';
      return;
    }
    $('yearbookHomeTitle').textContent = title(data);
    $('yearbookHomeLine').textContent = data.line || '';
    const counts = $('yearbookHomeCounts');
    counts.replaceChildren();
    if (data.stage === 'open') {
      counts.appendChild(el('li', null, `${data.notes} ${data.notes === 1 ? 'note' : 'notes'}`));
      if (data.waiting) counts.appendChild(el('li', 'yearbook-home__count--waiting', `${data.waiting} waiting`));
    }
    counts.hidden = !counts.children.length;
    const actions = $('yearbookHomeActions');
    actions.replaceChildren();
    if (data.action) {
      const go = el('a', `yearbook-home__go${data.waiting || data.new || data.stage === 'start' ? ' yearbook-home__go--urgent' : ''}`,
        data.action.label);
      go.href = safePath(data.action.path);
      actions.appendChild(go);
    }
    const friends = $('yearbookHomeFriends');
    friends.replaceChildren();
    const list = Array.isArray(data.friends) ? data.friends : [];
    if (list.length) {
      friends.appendChild(el('p', 'yearbook-home__friends-title', 'Friends\' yearbooks to sign'));
      const items = el('ul', 'yearbook-home__friends-list');
      for (const friend of list) {
        const item = el('li');
        const link = el('a', null, friend.name);
        link.href = `${safePath(friend.path)}#sign`;
        item.appendChild(link);
        items.appendChild(item);
      }
      if (data.friends_total > list.length) items.appendChild(el('li', 'yearbook-home__more-friends', `+${data.friends_total - list.length} more`));
      friends.appendChild(items);
    }
    friends.hidden = !list.length;
    section.dataset.status = data.status || '';
    section.dataset.stage = data.stage || '';
    section.hidden = false;
    if (window.OmniHomeLayout && typeof window.OmniHomeLayout.schedule === 'function') window.OmniHomeLayout.schedule();
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/yearbook/home`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.request = null;
    state.loadedAt = 0;
    const section = $('yearbookHome');
    if (section) { section.hidden = true; section.dataset.status = ''; }
    ['yearbookHomeCounts', 'yearbookHomeActions', 'yearbookHomeFriends'].forEach(id => $(id)?.replaceChildren());
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { safePath, title, state };
  }
  if (typeof document === 'undefined') return;

  // The dashboard's first batch of cards can run before this deferred script, so ask once here too.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => refresh(), { once: true });
  else refresh();

  window.OmniYearbookHome = { refresh, reset, render };
})();
