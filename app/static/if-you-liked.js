// "If you liked" guides (/if-you-liked/<slug>). Members add a pick to their library
// through POST /api/pick/add; visitors save it to the browser-only guest list, which
// guest-list.js toggles on the same click. This script only counts saves and handles
// the member button.
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

  function setStatus(button, message, link) {
    const article = button.closest('article');
    const status = article && article.querySelector('[data-liked-status]');
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

  async function addToLibrary(button) {
    button.disabled = true;
    setStatus(button, 'Adding…');
    try {
      const response = await fetch('/api/pick/add', {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(),
        body: JSON.stringify({ id: button.dataset.likedAdd, source: 'if-you-liked' }),
      });
      if (response.status === 401) {
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json();
      button.textContent = result.state === 'created' ? 'Added ✓' : 'In your library ✓';
      setStatus(button, result.state === 'created' ? `Added “${result.title}” to your library.` : `“${result.title}” is already in your library.`,
        { label: 'Open it', href: safeUrl(result.library_url) || '/' });
    } catch (error) {
      button.disabled = false;
      setStatus(button, 'Could not add this pick. Try again in a moment.');
    }
  }

  function init() {
    document.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!target) return;
      if (target.dataset.likedAdd) addToLibrary(target);
      else if (target.dataset.guestKind) {
        // guest-list.js toggles the list on the same click; count only a save.
        setTimeout(() => { if (target.getAttribute('aria-pressed') === 'true') report('liked_saved'); }, 0);
      }
    });
  }

  const api = { safeUrl, addToLibrary };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
