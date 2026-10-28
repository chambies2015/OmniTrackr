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
    mangaTable: ['manga', '.edit-manga-btn', 'mangaTitle', 'mangaYear', 'manga_private'],
  };
  let privacy = null;
  let privacyRequest = null;

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
    // All six library tables ask on page load; they share one request.
    if (!privacyRequest) privacyRequest = fetchPrivacy().finally(() => { privacyRequest = null; });
    return privacyRequest;
  }

  async function fetchPrivacy() {
    try {
      const options = typeof authFetchOptions === 'function' ? authFetchOptions() : { credentials: 'same-origin' };
      const response = await fetch(`${typeof API_BASE === 'string' ? API_BASE : ''}/account/privacy`, options);
      privacy = response.ok ? await response.json() : {};
    } catch (error) {
      privacy = {};
    }
    return privacy;
  }

  // Where to watch (or play): a "More" menu entry that asks the server, so it works for private libraries too.
  const WHERE_KINDS = { movie: 'watch', tv: 'watch', anime: 'watch', game: 'play' };
  let whereDialog = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeUrl(url) {
    return typeof url === 'string' && /^https:\/\//.test(url) ? url : '';
  }

  function ensureWhereDialog() {
    if (whereDialog) return whereDialog;
    const dialog = el('dialog', 'progress-dialog where-dialog');
    dialog.setAttribute('aria-labelledby', 'whereDialogTitle');
    const header = el('div', 'progress-dialog__header');
    const heading = el('div');
    heading.append(el('p', 'progress-dialog__eyebrow', 'Where to watch'), el('h2'));
    heading.lastChild.id = 'whereDialogTitle';
    const close = el('button', 'progress-dialog__close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', () => dialog.close());
    header.append(heading, close);
    const body = el('div', 'where-dialog__body');
    body.setAttribute('aria-live', 'polite');
    dialog.append(header, body);
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    document.body.appendChild(dialog);
    whereDialog = dialog;
    return dialog;
  }

  function prettyDate(value) {
    const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return 'recently';
    const day = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
    return day.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  }

  function renderWhere(body, data, kind) {
    body.replaceChildren();
    const groups = Array.isArray(data.groups) ? data.groups : [];
    if (!groups.length) {
      body.appendChild(el('p', 'progress-dialog__hint',
        kind === 'game' ? 'We could not find stores for this game yet.' : 'We could not find streaming services for this title yet.'));
    }
    groups.forEach(group => {
      const section = el('div', 'where-dialog__group');
      section.appendChild(el('h3', '', group.label));
      const list = el('ul');
      (group.providers || []).forEach(provider => {
        const item = el('li');
        const url = safeUrl(provider.url);
        const chip = el(url ? 'a' : 'span', 'where-dialog__provider');
        if (url) { chip.href = url; chip.target = '_blank'; chip.rel = 'noopener nofollow'; }
        const logo = safeUrl(provider.logo);
        if (logo) {
          const img = el('img');
          img.src = logo; img.alt = ''; img.width = 28; img.height = 28;
          chip.appendChild(img);
        }
        chip.appendChild(el('span', '', provider.name));
        item.appendChild(chip);
        list.appendChild(item);
      });
      section.appendChild(list);
      body.appendChild(section);
    });
    const more = safeUrl(data.more);
    if (more) {
      const link = el('a', 'where-dialog__more', 'Compare every service ↗');
      link.href = more; link.target = '_blank'; link.rel = 'noopener nofollow';
      body.appendChild(link);
    }
    const notes = [];
    if (data.region && groups.length) notes.push(`Showing ${data.region} availability, checked ${prettyDate(data.fetched)}.`);
    const credits = (data.credits || []).map(credit => credit.name).filter(Boolean);
    if (credits.length) notes.push(`Data from ${credits.join(', ')}.`);
    if (data.tmdb_notice) notes.push('This product uses the TMDB API but is not endorsed or certified by TMDB.');
    if (notes.length) body.appendChild(el('p', 'progress-dialog__hint where-dialog__note', notes.join(' ')));
  }

  async function openWhere(kind, title, yearValue) {
    const dialog = ensureWhereDialog();
    dialog.querySelector('.progress-dialog__eyebrow').textContent = `Where to ${WHERE_KINDS[kind]}`;
    dialog.querySelector('#whereDialogTitle').textContent = title;
    const body = dialog.querySelector('.where-dialog__body');
    body.replaceChildren(el('p', 'progress-dialog__hint', 'Checking services…'));
    if (!dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    }
    const match = String(yearValue || '').match(/^(\d{4})/);
    const params = new URLSearchParams({ kind, title });
    if (match && Number(match[1]) > 0) params.set('year', match[1]);
    try {
      const options = typeof authFetchOptions === 'function' ? authFetchOptions() : { credentials: 'same-origin' };
      const response = await fetch(`${typeof API_BASE === 'string' ? API_BASE : ''}/api/where-to-watch?${params}`, options);
      if (!response.ok) throw new Error(String(response.status));
      if (dialog.querySelector('#whereDialogTitle').textContent !== title) return;
      renderWhere(body, await response.json(), kind);
    } catch (error) {
      body.replaceChildren(el('p', 'progress-dialog__hint', 'Could not check right now. Please try again in a minute.'));
    }
  }

  function addWhereButton(row, kind, title, yearValue) {
    const panel = row.querySelector('.row-menu__panel');
    if (!panel || panel.querySelector('.where-to-watch-btn')) return;
    const button = el('button', 'action-btn where-to-watch-btn', `Where to ${WHERE_KINDS[kind]}`);
    button.type = 'button';
    button.addEventListener('click', () => {
      const menu = button.closest('details');
      if (menu) menu.open = false;
      openWhere(kind, title, yearValue);
    });
    panel.insertBefore(button, panel.firstChild);
  }

  async function linkRows(tableId) {
    const [kind, buttonSelector, titleKey, yearKey, privateKey] = TABLES[tableId];
    const table = document.getElementById(tableId);
    if (!table) return;
    if (WHERE_KINDS[kind]) {
      table.querySelectorAll('tbody tr').forEach(row => {
        const button = row.querySelector(buttonSelector);
        const title = button && button.dataset[titleKey];
        if (title) addWhereButton(row, kind, title.trim(), button.dataset[yearKey]);
      });
    }
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

  if (typeof window !== 'undefined') window.OmniTitleLinks = { slugify, titlePath, openWhere };
  if (typeof module !== 'undefined' && module.exports) module.exports = { slugify, titlePath, renderWhere, safeUrl };
  if (typeof document !== 'undefined' && document.documentElement && document.documentElement.dataset.publicShell !== 'true') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watch);
    else watch();
  }
})();
