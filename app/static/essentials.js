// The Essential 100 (/essentials/<format>): the checklist on each list.
// Visitors tick what they have finished; the ticks stay in this browser (KEY) and move into
// a new library after sign-up (essentials-import.js). Members save straight to their library
// through POST /api/essentials/save and can take a save back for a few minutes.
// "Want to" for visitors is the site-wide guest list (guest-list.js handles those buttons).
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const KEY = 'omnitrackr_essentials';
  const ID = /^[a-z]{2,10}\/[a-z0-9-]{1,130}$/;
  const MAX = 900;

  // ------------------------------------------------------------ storage (visitors)
  function readTicks() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      const seen = data && Array.isArray(data.seen) ? data.seen : [];
      return seen.filter(id => typeof id === 'string' && ID.test(id)).slice(0, MAX);
    } catch (error) {
      return [];
    }
  }

  function writeTicks(ids) {
    try {
      if (ids.length) localStorage.setItem(KEY, JSON.stringify({ v: 1, seen: ids.slice(0, MAX) }));
      else localStorage.removeItem(KEY);
      return true;
    } catch (error) {
      return false;
    }
  }

  function report(event) {
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function reportOnce(event) {
    try {
      const sent = JSON.parse(sessionStorage.getItem('omnitrackr_funnel_sent') || '[]');
      if (Array.isArray(sent) && sent.includes(event)) return;
      sessionStorage.setItem('omnitrackr_funnel_sent', JSON.stringify([...(Array.isArray(sent) ? sent : []), event].slice(-20)));
    } catch (error) { /* storage blocked: report anyway */ }
    report(event);
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  async function post(url, body) {
    const response = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: authHeaders(), body: JSON.stringify(body) });
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    return { ok: response.ok, status: response.status, data };
  }

  function safeUrl(value) {
    return typeof value === 'string' && /^\/(?!\/)/.test(value) ? value : null;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  // ------------------------------------------------------------ the count
  function counter(tracker) {
    const total = Number(tracker.dataset.esTotal || 100);
    const noun = tracker.dataset.esNoun || 'titles';
    const word = tracker.dataset.esWord || 'finished';
    const member = tracker.dataset.esMember === '1';
    const format = tracker.dataset.esFormat || '';

    function lineFor(done) {
      if (member) return `You have ${word} ${done} of these ${total} ${noun}.`;
      if (!done) return `How many of these ${total} ${noun} have you ${word}?`;
      if (done === total) return `You have ${word} all ${total}. Not many people can say that.`;
      return `You have ${word} ${done} of these ${total} ${noun}.`;
    }

    function show(done) {
      const count = tracker.querySelector('[data-es-count]');
      const line = tracker.querySelector('[data-es-line]');
      const bar = tracker.querySelector('[data-es-bar]');
      if (count) count.textContent = String(done);
      if (line) line.textContent = lineFor(done);
      if (bar) bar.style.width = `${Math.round((100 * done) / total)}%`;
      tracker.dataset.esDone = String(done);
      const share = tracker.querySelector('[data-es-share]');
      if (share) {
        share.href = `/essentials/${format}/score/${done}`;
        if (!member) share.hidden = done === 0;
      }
      const signup = tracker.querySelector('[data-es-signup]');
      if (signup) signup.hidden = done === 0;
    }

    return { show, get done() { return Number(tracker.dataset.esDone || 0); }, member, format, total, noun, word };
  }

  // ------------------------------------------------------------ filters
  function setupFilters(root) {
    const group = root.querySelector('[data-es-filters]');
    if (!group) return;
    group.hidden = false;
    group.addEventListener('click', event => {
      const button = event.target.closest('[data-es-filter]');
      if (!button) return;
      group.querySelectorAll('[data-es-filter]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
      root.dataset.esFilter = button.dataset.esFilter;
      root.querySelectorAll('.es-section').forEach(section => {
        const shown = Array.from(section.querySelectorAll('.es-item')).some(item => visible(item, button.dataset.esFilter));
        section.classList.toggle('es-section--empty', !shown);
      });
    });
  }

  function visible(item, filter) {
    if (filter === 'starter') return item.dataset.esStarter === '1';
    if (filter === 'todo') return item.dataset.esState !== 'done';
    return true;
  }

  // ------------------------------------------------------------ visitors: ticks
  function setupTicks(root, count) {
    let ticks = new Set(readTicks());
    const items = Array.from(root.querySelectorAll('.es-item[data-es-id]'));
    function paint() {
      let done = 0;
      items.forEach(item => {
        const on = ticks.has(item.dataset.esId);
        if (on) done += 1;
        if (on) item.dataset.esState = 'done';
        else delete item.dataset.esState;
        const button = item.querySelector('[data-es-tick]');
        if (button) button.setAttribute('aria-pressed', String(on));
      });
      count.show(done);
    }
    root.addEventListener('click', event => {
      const button = event.target.closest('[data-es-tick]');
      if (!button) return;
      const item = button.closest('.es-item');
      const id = item && item.dataset.esId;
      if (!id) return;
      ticks = new Set(readTicks());
      if (ticks.has(id)) ticks.delete(id);
      else ticks.add(id);
      const saved = writeTicks(Array.from(ticks));
      paint();
      const status = item.querySelector('[data-es-status]');
      if (status) status.textContent = saved ? '' : 'This browser could not save your ticks. Enable browser storage to keep them.';
      if (ticks.has(id)) reportOnce('essentials_ticked');
    });
    const signup = root.querySelector('[data-es-signup]');
    if (signup) signup.addEventListener('click', () => reportOnce('essentials_signup_clicked'));
    // Another tab ticking titles keeps this one in step.
    window.addEventListener('storage', event => { if (event.key === KEY) { ticks = new Set(readTicks()); paint(); } });
    paint();
  }

  // ------------------------------------------------------------ members: saves
  function setupSaves(root, count) {
    root.addEventListener('click', async event => {
      const button = event.target.closest('[data-es-save]');
      if (!button) return;
      const item = button.closest('.es-item');
      const actions = item && item.querySelector('.es-item__actions');
      const status = item && item.querySelector('[data-es-status]');
      if (!actions) return;
      const answer = button.dataset.esSave;
      actions.querySelectorAll('button').forEach(other => { other.disabled = true; });
      if (status) status.textContent = 'Adding…';
      let result;
      try {
        result = await post('/api/essentials/save', { id: item.dataset.esId, answer });
      } catch (error) {
        result = { ok: false, status: 0 };
      }
      if (result.status === 401) {
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
        return;
      }
      if (!result.ok || !result.data) {
        actions.querySelectorAll('button').forEach(other => { other.disabled = false; });
        if (status) status.textContent = 'Could not add this one. Try again in a moment.';
        return;
      }
      showSaved(item, actions, status, result.data, answer, count);
    });
  }

  function showSaved(item, actions, status, data, answer, count) {
    const link = el('a', 'es-link', 'In your library');
    link.href = safeUrl(data.library_url) || '/';
    const created = data.state === 'created';
    const label = data.done ? `${count.word.charAt(0).toUpperCase()}${count.word.slice(1)} ✓` : (created ? 'On your list ✓' : 'In your library');
    const badge = el('span', `es-have${data.done ? ' es-have--done' : ''}`, label);
    const keep = Array.from(actions.querySelectorAll('a.es-link')).filter(anchor => anchor.textContent === 'Title page');
    const nodes = [badge, link];
    if (created) {
      const undo = el('button', 'es-btn es-btn--quiet', 'Undo');
      undo.type = 'button';
      undo.addEventListener('click', () => takeBack(item, actions, status, data, answer, count, undo));
      nodes.push(undo);
    }
    actions.replaceChildren(...nodes, ...keep);
    if (data.done) {
      item.dataset.esState = 'done';
      if (created) count.show(count.done + 1);
    } else {
      item.dataset.esState = 'tracked';
    }
    if (status) {
      status.textContent = created
        ? (data.done ? `Added "${data.title}" as ${count.word}.` : `Added "${data.title}" to your library for later.`)
        : `"${data.title}" was already in your library, so nothing changed.`;
    }
  }

  async function takeBack(item, actions, status, data, answer, count, undo) {
    undo.disabled = true;
    let result;
    try {
      result = await post('/api/essentials/undo', { category: data.category, item_id: data.item_id });
    } catch (error) {
      result = { ok: false };
    }
    if (!result.ok) {
      undo.disabled = false;
      if (status) status.textContent = (result.data && typeof result.data.detail === 'string') ? result.data.detail : 'Could not undo that. Try again.';
      return;
    }
    const seen = el('button', 'es-btn es-btn--seen', `${count.word.charAt(0).toUpperCase()}${count.word.slice(1)} it`);
    seen.type = 'button';
    seen.dataset.esSave = 'seen';
    const want = el('button', 'es-btn', 'Want to');
    want.type = 'button';
    want.dataset.esSave = 'want';
    const keep = Array.from(actions.querySelectorAll('a.es-link')).filter(anchor => anchor.textContent === 'Title page');
    actions.replaceChildren(seen, want, ...keep);
    if (item.dataset.esState === 'done') count.show(Math.max(0, count.done - 1));
    delete item.dataset.esState;
    if (status) status.textContent = `Took "${data.title}" back out of your library.`;
  }

  // ------------------------------------------------------------ sharing
  async function share(url, title) {
    const absolute = new URL(url, window.location.origin).toString();
    if (navigator.share) {
      try {
        await navigator.share({ title, url: absolute });
        return 'shared';
      } catch (error) {
        if (error && error.name === 'AbortError') return 'cancelled';
      }
    }
    try {
      await navigator.clipboard.writeText(absolute);
      return 'copied';
    } catch (error) {
      return 'failed';
    }
  }

  function setupShare(root) {
    root.addEventListener('click', async event => {
      const link = event.target.closest('[data-es-share]');
      if (!link) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button > 0) return;
      event.preventDefault();
      const outcome = await share(link.getAttribute('href'), document.title);
      if (outcome === 'failed') { window.location.href = link.getAttribute('href'); return; }
      if (outcome !== 'cancelled') report('essentials_shared');
      if (outcome === 'copied') {
        const before = link.textContent;
        link.textContent = 'Link copied ✓';
        setTimeout(() => { link.textContent = before; }, 2500);
      }
    });
    document.querySelectorAll('[data-es-share-page]').forEach(button => {
      button.hidden = false;
      button.addEventListener('click', async () => {
        const outcome = await share(window.location.pathname, document.title);
        if (outcome !== 'cancelled' && outcome !== 'failed') report('essentials_shared');
        if (outcome === 'copied') button.textContent = 'Link copied ✓';
      });
    });
  }

  // The count sticks under the header while you scroll the list; once it is stuck it drops
  // its note (and, on phones, the filters) so it covers as little of the list as it can.
  function setupStuck(tracker) {
    const sentinel = document.createElement('div');
    sentinel.className = 'es-tracker-sentinel';
    sentinel.setAttribute('aria-hidden', 'true');
    tracker.parentNode.insertBefore(sentinel, tracker);
    const header = document.querySelector('.site-header');
    let queued = false;
    // A scroll check rather than an IntersectionObserver: a fast fling can carry the marker from
    // below the screen to above it in one frame, and an observer never reports that.
    function check() {
      queued = false;
      const offset = (header ? header.getBoundingClientRect().height : 64) + 12;
      tracker.classList.toggle('es-tracker--stuck', sentinel.getBoundingClientRect().top < offset);
    }
    window.addEventListener('scroll', () => {
      if (!queued) { queued = true; window.requestAnimationFrame(check); }
    }, { passive: true });
    check();
  }

  function showImported(tracker) {
    let added = 0;
    try {
      added = Number(sessionStorage.getItem('omnitrackr_essentials_imported') || 0);
      sessionStorage.removeItem('omnitrackr_essentials_imported');
    } catch (error) { added = 0; }
    if (!added || !tracker) return;
    const note = tracker.querySelector('.es-tracker__note');
    if (note) note.textContent = `Added ${added} title${added === 1 ? '' : 's'} you ticked before signing in.`;
  }

  function init() {
    const root = document.querySelector('.es-guide');
    setupShare(document);
    if (!root) return;
    const tracker = root.querySelector('[data-es-tracker]');
    if (!tracker) return;
    const count = counter(tracker);
    setupFilters(root);
    setupStuck(tracker);
    if (count.member) {
      setupSaves(root, count);
      showImported(tracker);
    } else {
      setupTicks(root, count);
    }
  }

  const api = { readTicks, writeTicks, visible, KEY };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
