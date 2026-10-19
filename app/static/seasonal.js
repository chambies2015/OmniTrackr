// Seasonal hubs (/halloween). Members add one pick or a whole shelf through
// POST /api/seasonal/<slug>/add and see which picks they already have; visitors
// save picks to the browser-only guest list, which guest-list.js toggles on the
// same click. Server text is only ever set as textContent.
(function () {
  'use strict';

  function report(event) {
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  function safeUrl(value) {
    return typeof value === 'string' && /^\/(?!\/)/.test(value) ? value : null;
  }

  function progressText(progress) {
    const total = progress.total || 0;
    const tracked = progress.tracked || 0;
    const done = progress.done || 0;
    if (!tracked) return `None of the ${total} picks are in your library yet. Add a shelf to start your Halloween list.`;
    const finished = done ? ` You've finished ${done}.` : ' Mark one finished when you get to it.';
    if (tracked === total) return `All ${total} picks are in your library.${finished}`;
    return `${tracked} of ${total} picks are in your library.${finished}`;
  }

  function percent(progress) {
    const total = progress.total || 0;
    return total ? Math.round(((progress.done || 0) / total) * 100) : 0;
  }

  const state = { slug: null, progress: null };

  function markPicks(progress) {
    const entries = progress.entries || {};
    document.querySelectorAll('[data-season-pick]').forEach(article => {
      const match = entries[article.dataset.seasonPick];
      const owned = article.querySelector('[data-season-owned]');
      const button = article.querySelector('[data-season-add]');
      article.classList.toggle('sn-pick--done', Boolean(match && match.state === 'done'));
      if (!owned) return;
      owned.hidden = !match;
      owned.textContent = match ? (match.state === 'done' ? 'Finished ✓' : 'In your library ✓') : '';
      if (button) button.hidden = Boolean(match);
    });
    document.querySelectorAll('[data-season-add-shelf]').forEach(button => {
      const ids = button.dataset.seasonAddShelf.split(' ').filter(Boolean);
      const missing = ids.filter(id => !entries[id]);
      button.hidden = !missing.length;
      button.textContent = missing.length === ids.length ? `Add all ${ids.length} to my library` : `Add the other ${missing.length} to my library`;
    });
  }

  function renderProgress(progress) {
    state.progress = progress;
    const panel = document.querySelector('[data-season-progress]');
    if (panel) {
      panel.hidden = false;
      const meter = panel.querySelector('[data-season-meter]');
      if (meter) meter.setAttribute('aria-valuenow', String(progress.done || 0));
      const fill = panel.querySelector('[data-season-meter-fill]');
      if (fill) fill.style.width = `${percent(progress)}%`;
      const text = panel.querySelector('[data-season-progress-text]');
      if (text) text.textContent = progressText(progress);
    }
    markPicks(progress);
  }

  async function loadProgress() {
    const panel = document.querySelector('[data-season-progress]');
    if (!panel) return;
    state.slug = panel.dataset.seasonProgress;
    try {
      const response = await fetch(`/api/seasonal/${encodeURIComponent(state.slug)}/progress`,
        { credentials: 'same-origin', headers: authHeaders() });
      if (!response.ok) return;
      renderProgress(await response.json());
    } catch (error) { /* the page still works without progress */ }
  }

  function statusFor(button) {
    const box = button.closest('[data-season-pick]') || button.closest('.sn-shelf__head');
    return box && box.querySelector('[data-season-status], [data-season-shelf-status]');
  }

  function setStatus(button, message, link) {
    const status = statusFor(button);
    if (!status) return;
    status.textContent = message;
    if (link) {
      const anchor = document.createElement('a');
      anchor.href = link.href;
      anchor.textContent = link.label;
      status.appendChild(document.createTextNode(' '));
      status.appendChild(anchor);
    }
  }

  function addedText(result) {
    const added = result.added || [];
    const existing = result.existing || [];
    if (added.length === 1 && !existing.length) return `Added “${added[0].title}” to your library.`;
    if (!added.length && existing.length === 1) return `“${existing[0].title}” is already in your library.`;
    if (!added.length) return 'All of these are already in your library.';
    const already = existing.length ? ` ${existing.length} ${existing.length === 1 ? 'was' : 'were'} already there.` : '';
    return `Added ${added.length} ${added.length === 1 ? 'pick' : 'picks'} to your library.${already}`;
  }

  async function addPicks(button, ids) {
    const slug = state.slug || (document.querySelector('[data-season-progress]') || {}).dataset?.seasonProgress || 'halloween';
    button.disabled = true;
    setStatus(button, 'Adding…');
    try {
      const response = await fetch(`/api/seasonal/${encodeURIComponent(slug)}/add`, {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(), body: JSON.stringify({ ids }),
      });
      if (response.status === 401) {
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json();
      button.disabled = false;
      if (result.progress) renderProgress(result.progress);
      setStatus(button, addedText(result), { label: 'Open my library', href: safeUrl('/') });
    } catch (error) {
      button.disabled = false;
      setStatus(button, 'Could not add right now. Try again in a moment.');
    }
  }

  function init() {
    loadProgress();
    document.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!target) return;
      if (target.dataset.seasonAdd) addPicks(target, [target.dataset.seasonAdd]);
      else if (target.dataset.seasonAddShelf) addPicks(target, target.dataset.seasonAddShelf.split(' ').filter(Boolean));
      else if (target.dataset.guestKind && target.closest('.sn-hub')) {
        // guest-list.js toggles the list on the same click; count only a save.
        setTimeout(() => { if (target.getAttribute('aria-pressed') === 'true') report('seasonal_saved'); }, 0);
      }
    });
  }

  const api = { progressText, percent, addedText, safeUrl };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
