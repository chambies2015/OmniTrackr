// "In order" guides (/in-order/<slug>). Switches between the orders, shows a member's
// progress from their own library (GET /api/in-order/<slug>/progress) and adds entries
// (POST /api/in-order/<slug>/add). Visitors save entries to the browser-only guest list,
// which guest-list.js toggles on the same click; "Save all" adds the main entries at once.
(function () {
  'use strict';

  function report(event) {
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function safeUrl(value) {
    return typeof value === 'string' && /^\/(?!\/)/.test(value) ? value : null;
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  function progressText(progress) {
    if (!progress.total) return 'Your progress';
    if (progress.done >= progress.total) return `You've finished all ${progress.total}. Nicely done.`;
    if (!progress.done) return progress.tracked ? `${progress.tracked} of ${progress.total} on your list, none finished yet` : `Not started yet: 0 of ${progress.total}`;
    return `You've finished ${progress.done} of ${progress.total}`;
  }

  function addAllLabel(count) {
    return count === 1 ? 'Add the 1 you are missing to my library' : `Add the ${count} you are missing to my library`;
  }

  // ------------------------------------------------------------ orders as tabs
  function setupTabs() {
    const tabs = document.querySelector('[data-io-tabs]');
    if (!tabs) return;
    const buttons = Array.from(tabs.querySelectorAll('[data-io-tab]'));
    const select = (key, focus) => {
      buttons.forEach(button => {
        const on = button.dataset.ioTab === key;
        button.setAttribute('aria-selected', String(on));
        button.tabIndex = on ? 0 : -1;
        if (on && focus) button.focus();
      });
      document.querySelectorAll('[data-io-order]').forEach(panel => {
        panel.hidden = panel.dataset.ioOrder !== key;
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', `tab-${panel.dataset.ioOrder}`);
      });
    };
    tabs.addEventListener('click', event => {
      const button = event.target && event.target.closest ? event.target.closest('[data-io-tab]') : null;
      if (button) select(button.dataset.ioTab, false);
    });
    tabs.addEventListener('keydown', event => {
      const index = buttons.findIndex(button => button.getAttribute('aria-selected') === 'true');
      let next = null;
      if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + buttons.length) % buttons.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = buttons.length - 1;
      if (next === null) return;
      event.preventDefault();
      select(buttons[next].dataset.ioTab, true);
    });
    tabs.hidden = false;
    // Open on an order named in the link (#order-story), else on the recommended one.
    const wanted = (window.location.hash || '').replace(/^#order-/, '');
    select(buttons.some(button => button.dataset.ioTab === wanted) ? wanted : buttons[0].dataset.ioTab, false);
  }

  // ------------------------------------------------------------ members
  let state = { slug: null, progress: null };

  function render(progress) {
    state.progress = progress;
    const panel = document.querySelector('[data-io-progress]');
    if (!panel) return;
    const entries = progress.entries || {};
    document.querySelectorAll('[data-io-entry]').forEach(node => {
      const match = entries[node.dataset.ioEntry];
      node.classList.toggle('is-done', !!match && match.state === 'done');
      node.classList.toggle('is-tracked', !!match && match.state !== 'done');
      const label = node.querySelector('[data-io-state]');
      // An entry card's button already says "In your library", so it only adds "Finished".
      const tracked = node.classList.contains('io-entry') ? '' : 'On your list';
      if (label) label.textContent = match ? (match.state === 'done' ? 'Finished ✓' : tracked) : '';
      const button = node.querySelector('[data-io-add]');
      if (button && match) {
        button.textContent = 'In your library ✓';
        button.disabled = true;
      }
    });
    panel.querySelector('[data-io-progress-title]').textContent = progressText(progress);
    const meter = panel.querySelector('[data-io-meter]');
    meter.setAttribute('aria-valuenow', String(progress.done || 0));
    const percent = progress.total ? Math.round((100 * (progress.done || 0)) / progress.total) : 0;
    panel.querySelector('[data-io-meter-fill]').style.width = `${percent}%`;
    const next = panel.querySelector('[data-io-next]');
    next.textContent = '';
    if (progress.next && typeof progress.next.title === 'string' && /^[a-z0-9-]{1,80}$/.test(progress.next.id || '')) {
      next.appendChild(document.createTextNode('Next up: '));
      const link = document.createElement('a');
      link.href = `#entry-${progress.next.id}`;
      link.textContent = progress.next.title;
      next.appendChild(link);
    }
    const addAll = panel.querySelector('[data-io-add-all]');
    const missing = Array.isArray(progress.missing) ? progress.missing : [];
    addAll.hidden = missing.length === 0;
    if (addAll.parentElement) addAll.parentElement.hidden = addAll.hidden;
    addAll.textContent = addAllLabel(missing.length);
    panel.hidden = false;
  }

  function setStatus(node, message, link) {
    if (!node) return;
    node.textContent = message;
    const href = link && safeUrl(link.href);
    if (href) {
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.textContent = link.label;
      node.appendChild(document.createTextNode(' '));
      node.appendChild(anchor);
    }
  }

  async function loadProgress(slug) {
    state.slug = slug;
    try {
      const response = await fetch(`/api/in-order/${encodeURIComponent(slug)}/progress`, { credentials: 'same-origin', headers: authHeaders() });
      if (!response.ok) return null; // A stale session keeps the page as it is.
      const progress = await response.json();
      render(progress);
      return progress;
    } catch (error) {
      return null;
    }
  }

  async function addEntries(ids, button, status) {
    if (!state.slug || !ids.length) return null;
    button.disabled = true;
    setStatus(status, 'Adding…');
    try {
      const response = await fetch(`/api/in-order/${encodeURIComponent(state.slug)}/add`, {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(), body: JSON.stringify({ ids }),
      });
      if (response.status === 401) {
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
        return null;
      }
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json();
      if (result.progress) render(result.progress);
      const added = Array.isArray(result.added) ? result.added.length : 0;
      const message = added === 0 ? 'Already in your library.'
        : added === 1 ? `Added “${result.added[0].title}” to your library.` : `Added ${added} titles to your library.`;
      setStatus(status, message, added ? { label: 'Open your library', href: '/' } : null);
      if (!button.hasAttribute('data-io-add')) button.disabled = false;
      return result;
    } catch (error) {
      button.disabled = false;
      setStatus(status, 'Could not add right now. Try again in a moment.');
      return null;
    }
  }

  // ------------------------------------------------------------ visitors
  function saveAllForGuest(button) {
    const list = window.OmniGuestList;
    const status = document.querySelector('[data-io-status]');
    if (!list) return 0;
    let saved = 0;
    let full = false;
    document.querySelectorAll('.io-entry:not(.is-optional) [data-guest-kind]').forEach(tile => {
      const { guestKind: kind, guestSlug: slug, guestTitle: title } = tile.dataset;
      const result = list.add(kind, slug, title);
      if (result.added) saved += 1;
      if (result.full) full = true;
    });
    list.refreshTiles();
    if (saved) report('order_saved');
    const message = full ? `Saved ${saved}. Your list is full (${list.MAX} titles); create a free account to keep going.`
      : saved ? `Saved ${saved} to your list. Create a free account to keep it and track your progress.`
        : 'They are already on your list.';
    setStatus(status, message, { label: 'Create a free account', href: '/#signup' });
    if (button) button.textContent = 'Saved to your list ✓';
    return saved;
  }

  function init() {
    setupTabs();
    const panel = document.querySelector('[data-io-progress]');
    if (panel && /^[a-z0-9-]{1,80}$/.test(panel.dataset.ioProgress || '')) loadProgress(panel.dataset.ioProgress);
    document.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!target) return;
      if (target.dataset.ioAdd) {
        const article = target.closest('article');
        addEntries([target.dataset.ioAdd], target, article && article.querySelector('[data-io-entry-status]'));
      } else if (target.hasAttribute('data-io-add-all')) {
        addEntries((state.progress && state.progress.missing) || [], target, document.querySelector('[data-io-status]'));
      } else if (target.hasAttribute('data-io-guest-all')) {
        saveAllForGuest(target);
      } else if (target.dataset.guestKind) {
        // guest-list.js toggles the list on the same click; count only a save.
        setTimeout(() => { if (target.getAttribute('aria-pressed') === 'true') report('order_saved'); }, 0);
      }
    });
  }

  const api = { safeUrl, progressText, addAllLabel, render, loadProgress, addEntries, saveAllForGuest, _state: () => state };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
