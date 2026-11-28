// The Essential 100: titles a visitor ticked as finished before signing up are kept in this
// browser (essentials.js). Once they are signed in (the dashboard, /start or a list page),
// this moves them into the library as finished through POST /api/essentials/import and
// clears them. Titles already in the library are left exactly as they are.
(function () {
  'use strict';

  const KEY = 'omnitrackr_essentials';
  const ID = /^[a-z]{2,10}\/[a-z0-9-]{1,130}$/;
  const LOADERS = ['loadMovies', 'loadTVShows', 'loadAnime', 'loadVideoGames', 'loadMusic', 'loadBooks', 'loadManga', 'loadPodcasts', 'loadAudiobooks'];

  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      const seen = data && Array.isArray(data.seen) ? data.seen : [];
      return seen.filter(id => typeof id === 'string' && ID.test(id)).slice(0, 900);
    } catch (error) {
      return [];
    }
  }

  // The list the visitor last ticked on, for a link back once the ticks are in the library.
  const LIST_PATH = /^\/essentials\/(?:movies|tv|anime|games|books|music|manga|podcasts|audiobooks)$/;

  function readFrom() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      return data && typeof data.from === 'string' && LIST_PATH.test(data.from) ? data.from : null;
    } catch (error) {
      return null;
    }
  }

  function forget(sent) {
    // Keep anything ticked in another tab while the request was running.
    try {
      const left = read().filter(id => !sent.includes(id));
      const from = readFrom();
      if (left.length) localStorage.setItem(KEY, JSON.stringify(from ? { v: 1, seen: left, from } : { v: 1, seen: left }));
      else localStorage.removeItem(KEY);
    } catch (error) { /* nothing to clear */ }
  }

  function listPage() {
    return document.querySelector('[data-es-tracker][data-es-member="1"]');
  }

  function signedIn() {
    if (listPage()) return true;
    if (document.documentElement.dataset.publicShell === 'true') return false;
    if (document.getElementById('startFlow')) return true;
    try { return typeof getUser === 'function' && !!getUser(); } catch (error) { return false; }
  }

  function headers() {
    const result = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) result.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return result;
  }

  function toast(message, back) {
    const node = document.createElement('div');
    node.className = 'guest-import-toast';
    node.setAttribute('role', 'status');
    node.textContent = message;
    if (back) {
      const link = document.createElement('a');
      link.className = 'guest-import-toast__back';
      link.href = `${back}#your-count`;
      link.textContent = 'See your count on the list →';
      node.append(document.createElement('br'), link);
    }
    document.body.appendChild(node);
    setTimeout(() => node.remove(), back ? 15000 : 8000);
  }

  async function importTicks() {
    const ids = read();
    if (!ids.length || !signedIn()) return null;
    const back = readFrom();
    let response;
    try {
      response = await fetch('/api/essentials/import', { method: 'POST', credentials: 'same-origin', headers: headers(), body: JSON.stringify({ ids }) });
    } catch (error) {
      return null; // Try again next visit.
    }
    if (response.status === 401) return null;
    if (response.status === 422 || response.status === 400) { forget(ids); return null; }
    if (!response.ok) return null;
    const result = await response.json().catch(() => null);
    if (!result || typeof result.added !== 'number') return null;
    forget(ids);
    if (result.added) {
      if (listPage()) {
        try { sessionStorage.setItem('omnitrackr_essentials_imported', String(result.added)); } catch (error) { /* note only */ }
        window.location.reload();
        return result;
      }
      toast(`Added ${result.added} title${result.added === 1 ? '' : 's'} you ticked on the Essential 100 before signing up.`, back);
      LOADERS.forEach(name => { if (typeof window[name] === 'function') { try { window[name](); } catch (error) { /* ignore */ } } });
      if (typeof window.refreshForYou === 'function') window.refreshForYou();
    }
    return result;
  }

  const api = { read, readFrom, importTicks, KEY };
  window.OmniEssentialsImport = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    const start = () => setTimeout(importTicks, 900);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }
})();
