// "Save before you sign up": a visitor's list of titles, kept only in this browser.
// Homepage tiles and title pages add to it; after sign-up the dashboard moves it
// into the new library (POST /api/guest-list/import) and clears it.
(function () {
  'use strict';

  const KEY = 'omnitrackr_guest_list';
  const MAX = 30;
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book', 'manga', 'podcast', 'audiobook']);
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const LOADERS = ['loadMovies', 'loadTVShows', 'loadAnime', 'loadVideoGames', 'loadMusic', 'loadBooks', 'loadManga', 'loadPodcasts', 'loadAudiobooks'];

  function valid(item) {
    return item && KINDS.has(item.kind) && SLUG.test(item.slug || '') && typeof item.title === 'string';
  }

  function read() {
    try {
      const list = JSON.parse(localStorage.getItem(KEY) || '[]');
      return Array.isArray(list) ? list.filter(valid).slice(0, MAX) : [];
    } catch (error) {
      return [];
    }
  }

  function write(list) {
    try {
      if (list.length) localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX)));
      else localStorage.removeItem(KEY);
      return true;
    } catch (error) {
      return false;
    }
  }

  function has(list, kind, slug) {
    return list.some(item => item.kind === kind && item.slug === slug);
  }

  function add(kind, slug, title) {
    const list = read();
    if (has(list, kind, slug)) return { list, added: false };
    if (list.length >= MAX) return { list, added: false, full: true };
    const item = { kind, slug, title: String(title || '').slice(0, 200) };
    if (!valid(item)) return { list, added: false };
    list.push(item);
    if (!write(list)) return { list: read(), added: false, storageError: true };
    report('guest_pick_added');
    return { list, added: true };
  }

  function remove(kind, slug) {
    const list = read().filter(item => !(item.kind === kind && item.slug === slug));
    return write(list) ? list : read();
  }

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') {
      window.reportFunnelEvent(event);
      return;
    }
    if (report.sent && report.sent.has(event)) return;
    report.sent = report.sent || new Set();
    report.sent.add(event);
    // Same once-per-visit rule as reportFunnelEvent in auth.js (title pages don't load it).
    try {
      const sent = JSON.parse(sessionStorage.getItem('omnitrackr_funnel_sent') || '[]');
      if (Array.isArray(sent) && sent.includes(event)) return;
      sessionStorage.setItem('omnitrackr_funnel_sent', JSON.stringify([...(Array.isArray(sent) ? sent : []), event].slice(-20)));
    } catch (error) { /* storage blocked: once per page instead */ }
    try {
        // A beacon never delays the page or navigation.
        if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
            navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
        }
    } catch (error) { /* analytics only */ }
  }

  function countText(count) {
    return count === 1 ? '1 title on your list' : `${count} titles on your list`;
  }

  // ------------------------------------------------------------ homepage tiles
  // Tiles are the "Start your list" picks and the hero search results (added later
  // by title-search.js), so clicks are delegated and every refresh re-reads the page.
  const TILE = '[data-guest-kind][data-guest-slug]:not([data-guest-save])';

  function refreshTiles() {
    const list = read();
    document.querySelectorAll(TILE).forEach(tile => {
      tile.setAttribute('aria-pressed', String(has(list, tile.dataset.guestKind, tile.dataset.guestSlug)));
    });
    document.querySelectorAll('[data-guest-bar]').forEach(bar => { bar.hidden = list.length === 0; });
    document.querySelectorAll('[data-guest-count]').forEach(counter => {
      counter.textContent = list.length ? `${countText(list.length)}.` : '';
      if (!list.length || typeof document.createElement !== 'function') return;
      // The second sentence is its own span so narrow save bars can drop it (the button says it).
      const ask = document.createElement('span');
      ask.className = 'guest-count__ask';
      ask.textContent = ` Sign up free to keep ${list.length === 1 ? 'it' : 'them'}.`;
      if (typeof counter.appendChild === 'function') counter.appendChild(ask);
      else counter.textContent += ask.textContent;
    });
  }

  function toggleTile(tile) {
    const { guestKind: kind, guestSlug: slug, guestTitle: title } = tile.dataset;
    const result = has(read(), kind, slug) ? { list: remove(kind, slug) } : add(kind, slug, title);
    refreshTiles();
    return result;
  }

  function setupTiles() {
    if (!document.querySelector('[data-guest-bar]')) return;
    document.addEventListener('click', event => {
      const tile = event.target && event.target.closest ? event.target.closest(TILE) : null;
      if (tile) toggleTile(tile);
    });
    refreshTiles();
  }

  // ------------------------------------------------------------ title pages (guests)
  function setupTitleButtons() {
    document.querySelectorAll('[data-guest-save]').forEach(button => {
      const { guestKind: kind, guestSlug: slug, guestTitle: title } = button.dataset;
      const status = document.querySelector('.title-hero__status');
      const show = saved => {
        button.textContent = saved ? 'Saved to your list ✓' : 'Save to my list';
        button.setAttribute('aria-pressed', String(saved));
        if (status) {
          status.textContent = saved
            ? `${countText(read().length)}. Create a free account to keep it — it moves into your library when you log in.`
            : '';
        }
      };
      button.addEventListener('click', () => {
        const saved = has(read(), kind, slug);
        const result = saved ? remove(kind, slug) : add(kind, slug, title);
        const persisted = has(read(), kind, slug);
        refreshTiles(); // A save bar on the page (Discover) shows the new count.
        show(persisted);
        if (status && !saved && !persisted) status.textContent = result.full
          ? 'Your list is full (30 titles). Remove a title before saving another.'
          : 'This browser could not save your list. Enable browser storage and try again.';
      });
      show(has(read(), kind, slug));
    });
  }

  // ------------------------------------------------------------ keep-your-list sheet
  // On guides, title pages and shelves (body[data-guest-sheet], see app/guest_signup.py),
  // a guest who has saved something and presses a sign-up link gets a small sheet on the
  // same page: what they saved, Continue with Google, Sign up with email. It never opens
  // by itself. The page they were on is remembered so the new library can link back.
  const RETURN_KEY = 'omnitrackr_guest_return';
  const RETURN_MAX_AGE = 3 * 24 * 60 * 60 * 1000;
  const KIND_LABELS = { movie: 'Movie', tv: 'TV show', anime: 'Anime', game: 'Game', album: 'Album', book: 'Book',
    manga: 'Manga', podcast: 'Podcast', audiobook: 'Audiobook' };
  const SHEET_SHOWN = 6;
  const GOOGLE_G = '<svg class="guest-sheet__g" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" focusable="false">'
    + '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>'
    + '<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>'
    + '<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"/>'
    + '<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>'
    + '</svg>';

  function sheetMode() {
    const body = document.body;
    return body && body.dataset ? body.dataset.guestSheet || '' : '';
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function pageName() {
    const heading = document.querySelector('h1');
    const text = (heading && heading.textContent ? heading.textContent : document.title || '').replace(/\s+/g, ' ').trim();
    return text.length > 80 ? `${text.slice(0, 79)}…` : text;
  }

  function rememberPage() {
    const path = window.location.pathname;
    if (!/^\/[A-Za-z0-9/_.-]{0,200}$/.test(path) || path === '/') return;
    try {
      localStorage.setItem(RETURN_KEY, JSON.stringify({ path, title: pageName(), at: Date.now() }));
    } catch (error) { /* storage blocked: no link back */ }
  }

  function readReturn() {
    try {
      const saved = JSON.parse(localStorage.getItem(RETURN_KEY) || 'null');
      if (!saved || typeof saved.path !== 'string' || typeof saved.title !== 'string') return null;
      if (!/^\/[A-Za-z0-9/_.-]{1,200}$/.test(saved.path) || saved.path.startsWith('//')) return null;
      if (!(Date.now() - Number(saved.at) < RETURN_MAX_AGE)) return null;
      return { path: saved.path, title: saved.title.slice(0, 80) };
    } catch (error) {
      return null;
    }
  }

  function forgetReturn() {
    try { localStorage.removeItem(RETURN_KEY); } catch (error) { /* nothing to forget */ }
  }

  function fillSheet(sheet) {
    const list = read();
    const lead = sheet.querySelector('[data-sheet-lead]');
    const titles = sheet.querySelector('[data-sheet-titles]');
    const more = sheet.querySelector('[data-sheet-more]');
    lead.textContent = list.length === 1
      ? 'The title you saved is kept in this browser only. Make a free account and it moves into your library, where you can mark it finished, rate it and see what to try next.'
      : `The ${list.length} titles you saved are kept in this browser only. Make a free account and they move into your library, where you can mark them finished, rate them and see what to try next.`;
    titles.replaceChildren(...list.slice(-SHEET_SHOWN).reverse().map(item => {
      const row = element('li');
      row.append(element('span', 'guest-sheet__kind', KIND_LABELS[item.kind] || ''), element('span', 'guest-sheet__name', item.title));
      return row;
    }));
    const hidden = list.length - Math.min(list.length, SHEET_SHOWN);
    more.textContent = hidden ? `and ${hidden} more` : '';
    more.hidden = !hidden;
  }

  function buildSheet() {
    const sheet = element('dialog', 'guest-sheet');
    sheet.setAttribute('aria-labelledby', 'guestSheetTitle');
    sheet.dataset.guestSheetDialog = '';
    const close = element('button', 'guest-sheet__close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', () => sheet.close());
    const title = element('h2', 'guest-sheet__title', 'Keep your list');
    title.id = 'guestSheetTitle';
    const lead = element('p', 'guest-sheet__lead');
    lead.dataset.sheetLead = '';
    const titles = element('ul', 'guest-sheet__titles');
    titles.dataset.sheetTitles = '';
    const more = element('p', 'guest-sheet__more');
    more.dataset.sheetMore = '';
    const actions = element('div', 'guest-sheet__actions');
    if (sheetMode() === 'google') {
      const google = element('a', 'guest-sheet__btn guest-sheet__btn--google');
      google.href = '/auth/google/start';
      google.rel = 'nofollow';
      google.innerHTML = GOOGLE_G; // A fixed logo, no visitor text.
      google.append(element('span', '', 'Continue with Google'));
      google.addEventListener('click', () => {
        rememberPage();
        report('guest_sheet_google');
        report('signup_form_opened');
        report('guest_list_signup');
      });
      actions.appendChild(google);
    }
    const email = element('a', `guest-sheet__btn ${sheetMode() === 'google' ? 'guest-sheet__btn--ghost' : 'guest-sheet__btn--primary'}`,
      sheetMode() === 'google' ? 'Sign up with email' : 'Create a free account');
    email.href = '/#signup';
    email.addEventListener('click', () => { rememberPage(); report('guest_sheet_email'); });
    actions.appendChild(email);
    const note = element('p', 'guest-sheet__note', 'Free, private unless you share it, no card needed. Already a member? ');
    const login = element('a', '', 'Log in');
    login.href = '/#login';
    login.addEventListener('click', () => { rememberPage(); report('guest_sheet_login'); });
    note.append(login, document.createTextNode(' and your list is added to your library.'));
    sheet.append(close, element('p', 'guest-sheet__kicker', 'Free account'), title, lead, titles, more, actions, note);
    // A press on the dimmed page around the sheet closes it.
    sheet.addEventListener('click', event => { if (event.target === sheet) sheet.close(); });
    document.body.appendChild(sheet);
    return sheet;
  }

  function openSheet() {
    let sheet = document.querySelector('[data-guest-sheet-dialog]');
    if (!sheet) sheet = buildSheet();
    if (typeof sheet.showModal !== 'function') return false;
    fillSheet(sheet);
    if (!sheet.open) sheet.showModal();
    rememberPage();
    report('guest_sheet_opened');
    return true;
  }

  function setupSheet() {
    if (!sheetMode() || typeof window.HTMLDialogElement !== 'function') return;
    document.addEventListener('click', event => {
      if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target && event.target.closest ? event.target.closest('a[href="/#signup"]') : null;
      if (!link || link.closest('[data-guest-sheet-dialog]') || !read().length) return;
      if (openSheet()) event.preventDefault();
    });
  }

  // ------------------------------------------------------------ dashboard import
  function signedInDashboard() {
    if (document.documentElement.dataset.publicShell === 'true') return false;
    // The start page (/start) is only ever served to a signed-in member.
    if (typeof document.getElementById === 'function' && document.getElementById('startFlow')) return true;
    try { return typeof getUser === 'function' && !!getUser(); } catch (error) { return false; }
  }

  function toast(message, back) {
    const node = document.createElement('div');
    node.className = 'guest-import-toast';
    node.setAttribute('role', 'status');
    node.textContent = message;
    if (back) {
      // Back to the guide or title page the list was saved from.
      const link = document.createElement('a');
      link.className = 'guest-import-toast__back';
      link.href = back.path;
      link.textContent = `Back to ${back.title || 'where you were'} →`;
      link.addEventListener('click', () => report('guest_return_clicked'));
      node.append(document.createElement('br'), link);
    }
    document.body.appendChild(node);
    setTimeout(() => node.remove(), back ? 15000 : 7000);
  }

  async function importList() {
    const list = read();
    if (!list.length || !signedInDashboard()) return null;
    const options = { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: list.map(({ kind, slug }) => ({ kind, slug })) }) };
    const base = typeof API_BASE === 'string' ? API_BASE : '';
    let response;
    try {
      response = await fetch(`${base}/api/guest-list/import`,
        typeof authFetchOptions === 'function' ? authFetchOptions(options) : { credentials: 'same-origin', ...options });
    } catch (error) {
      return null; // Try again next visit.
    }
    if (!response.ok) {
      if (response.status === 422 || response.status === 400) write([]);
      return null;
    }
    const result = await response.json().catch(() => null);
    if (!result || !Array.isArray(result.added) || !Array.isArray(result.existing)) return null;
    // Preserve titles saved in another tab while this request was running.
    write(read().filter(item => !has(list, item.kind, item.slug)));
    if (result) {
      const added = (result.added || []).length;
      if (added) {
        const back = readReturn();
        forgetReturn();
        toast(`Added ${added} title${added === 1 ? '' : 's'} from the list you saved before signing up.`, back);
        LOADERS.forEach(name => { if (typeof window[name] === 'function') { try { window[name](); } catch (error) { /* ignore */ } } });
        if (typeof window.refreshForYou === 'function') window.refreshForYou();
      }
    }
    return result;
  }

  function init() {
    setupTiles();
    setupTitleButtons();
    setupSheet();
    setTimeout(importList, 800);
  }

  const api = { read, write, add, remove, importList, refreshTiles, toggleTile, openSheet, readReturn, KEY, MAX };
  window.OmniGuestList = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
