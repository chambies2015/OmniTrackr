/* Browse shelves: one-tap adds for members, and a search box that filters the page. */
(() => {
  'use strict';

  const kind = document.body.dataset.browseKind;
  if (!kind) return;

  function authHeaders(extra = {}) {
    const headers = {...extra};
    // Legacy token sessions as well as the HttpOnly cookie.
    try { const token = localStorage.getItem('omnitrackr_token'); if (token) headers.Authorization = `Bearer ${token}`; } catch (_) {}
    return headers;
  }

  function signInUrl(key) {
    return `/?next=${encodeURIComponent(`${window.location.pathname}#${key}`)}#landing-auth`;
  }

  function statusFor(button) {
    return button.parentElement && button.parentElement.querySelector('.browse-card__status');
  }

  function markOwned(button, state) {
    button.dataset.state = state;
    button.textContent = state === 'added' ? 'Added ✓' : 'In your library ✓';
    button.disabled = true;
  }

  async function add(button) {
    if (button.disabled) return;
    const status = statusFor(button);
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    if (status) status.textContent = 'Adding…';
    try {
      const response = await fetch(`/api/browse/${encodeURIComponent(kind)}/add`, {
        method: 'POST', credentials: 'same-origin',
        headers: authHeaders({'Content-Type': 'application/json'}),
        body: JSON.stringify({key: button.dataset.browseKey}),
      });
      if (response.status === 401) {
        if (status) status.textContent = '';
        window.location.href = signInUrl(button.dataset.browseKey);
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error((data && typeof data.detail === 'string') ? data.detail : 'Could not add that just now. Try again in a moment.');
      }
      const result = await response.json();
      markOwned(button, result.state === 'created' ? 'added' : 'existing');
      if (status) {
        status.textContent = result.state === 'created' ? 'In your library, unfinished and unrated. ' : 'You already had this one. ';
        const link = document.createElement('a');
        link.href = '/';
        link.textContent = 'Open my library →';
        status.append(link);
      }
    } catch (error) {
      button.disabled = false;
      if (status) status.textContent = error.message;
    } finally {
      button.removeAttribute('aria-busy');
    }
  }

  // A member who already tracks something on this page should see that, not an Add button.
  async function markMine() {
    const buttons = document.querySelectorAll('[data-browse-add]');
    if (!buttons.length) return;
    try {
      const response = await fetch(`/api/browse/${encodeURIComponent(kind)}/mine`, {credentials: 'same-origin', headers: authHeaders()});
      if (!response.ok) return;
      const data = await response.json();
      const mine = new Set(Array.isArray(data.keys) ? data.keys : []);
      buttons.forEach(button => { if (mine.has(button.dataset.browseKey)) markOwned(button, 'existing'); });
    } catch (_) { /* The buttons still work without this. */ }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest && event.target.closest('[data-browse-add]');
    if (button) add(button);
  });

  // Search within the page. Shelves with nothing left are hidden along with their cards.
  function setupFilter() {
    const box = document.querySelector('.browse-filter');
    const input = document.getElementById('browse-search');
    const status = document.getElementById('browse-filter-status');
    if (!box || !input) return;
    const items = Array.from(document.querySelectorAll('[data-browse-item]'));
    const sections = Array.from(document.querySelectorAll('.browse-shelf, .browse-chart'));
    const normalize = value => value.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const apply = () => {
      const terms = normalize(input.value).trim().split(/\s+/).filter(Boolean);
      let shown = 0;
      for (const item of items) {
        const match = terms.every(term => (item.dataset.search || '').includes(term));
        item.hidden = !match;
        if (match) shown += 1;
      }
      for (const section of sections) {
        section.hidden = terms.length > 0 && !section.querySelector('[data-browse-item]:not([hidden])');
      }
      if (status) status.textContent = terms.length ? (shown ? `${shown} of ${items.length} match` : 'Nothing on this page matches. Try a shorter word.') : '';
    };
    input.addEventListener('input', apply);
    box.hidden = false;
  }

  function init() {
    setupFilter();
    markMine();
    // Back from sign-in: the hash names the card the visitor wanted.
    if (window.location.hash) {
      const card = document.getElementById(window.location.hash.slice(1));
      if (card && card.scrollIntoView) card.scrollIntoView({block: 'center'});
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
