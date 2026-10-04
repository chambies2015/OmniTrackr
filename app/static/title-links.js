// Links titles in the library tables to their public title pages (/titles/<kind>/<slug>),
// where members get trailers, details and reviews. Categories the member made private
// are left alone: their own entry doesn't create a public page.
(function () {
  'use strict';

  // table id -> [URL kind, edit-button selector, title attr, year attr, privacy key]
  const TABLES = {
    movieTable: ['movie', '.edit-movie-btn', 'movieTitle', 'movieYear', 'movies_private'],
    tvShowTable: ['tv', '.edit-tv-btn', 'tvTitle', 'tvYear', 'tv_shows_private'],
    animeTable: ['anime', '.edit-anime-btn', 'animeTitle', 'animeYear', 'anime_private'],
    videoGameTable: ['game', '.edit-video-game-btn', 'gameTitle', 'gameReleaseDate', 'video_games_private'],
    musicTable: ['album', '.edit-music-btn', 'musicTitle', 'musicYear', 'music_private'],
    bookTable: ['book', '.edit-book-btn', 'bookTitle', 'bookYear', 'books_private'],
  };
  let privacy = null;

  // Mirrors title_pages.slugify / title_slug on the server.
  function slugify(text) {
    const ascii = String(text || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^\x00-\x7f]/g, '');
    const slug = ascii.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120);
    return slug || 'title';
  }

  function titlePath(kind, title, yearValue) {
    const match = String(yearValue || '').match(/^(\d{4})/);
    const year = match && Number(match[1]) > 0 ? match[1] : '';
    const base = slugify(title);
    return `/titles/${kind}/${year ? `${base}-${year}` : base}`;
  }

  async function loadPrivacy() {
    if (privacy) return privacy;
    try {
      const options = typeof authFetchOptions === 'function' ? authFetchOptions() : { credentials: 'same-origin' };
      const response = await fetch(`${typeof API_BASE === 'string' ? API_BASE : ''}/account/privacy`, options);
      privacy = response.ok ? await response.json() : {};
    } catch (error) {
      privacy = {};
    }
    return privacy;
  }

  async function linkRows(tableId) {
    const [kind, buttonSelector, titleKey, yearKey, privateKey] = TABLES[tableId];
    const table = document.getElementById(tableId);
    if (!table) return;
    const settings = await loadPrivacy();
    if (settings[privateKey]) return;
    table.querySelectorAll('tbody tr').forEach(row => {
      const button = row.querySelector(buttonSelector);
      const cell = row.cells && row.cells[1];
      if (!button || !cell || cell.querySelector('a.title-page-link, input')) return;
      const title = button.dataset[titleKey];
      if (!title || cell.textContent.trim() !== title.trim()) return;
      const link = document.createElement('a');
      link.className = 'title-page-link';
      link.href = titlePath(kind, title, button.dataset[yearKey]);
      link.textContent = cell.textContent;
      link.title = 'Trailer, details and reviews';
      cell.replaceChildren(link);
    });
  }

  function watch() {
    Object.keys(TABLES).forEach(tableId => {
      const body = document.querySelector(`#${tableId} tbody`);
      if (!body || typeof MutationObserver !== 'function') return;
      let pending = false;
      new MutationObserver(() => {
        if (pending) return;
        pending = true;
        setTimeout(() => { pending = false; linkRows(tableId); }, 50);
      }).observe(body, { childList: true });
      linkRows(tableId);
    });
  }

  // Privacy changes take effect on the next table refresh.
  if (typeof document !== 'undefined') document.addEventListener('submit', event => {
    if (event.target && event.target.id === 'privacySettingsForm') privacy = null;
  }, true);

  if (typeof window !== 'undefined') window.OmniTitleLinks = { slugify, titlePath };
  if (typeof module !== 'undefined' && module.exports) module.exports = { slugify, titlePath };
  if (typeof document !== 'undefined' && document.documentElement && document.documentElement.dataset.publicShell !== 'true') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
    else watch();
  }
})();
