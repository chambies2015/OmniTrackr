// /continue (app/continue_page.py): finish signing up in Safari or Chrome.
//
// Inside an app's built-in browser (body[data-continue="app"]) Google sign-in can't work,
// so this page builds a link that carries the visitor's saved titles (guest-list.js) and
// the page they were on, puts it in the address bar (the app's "Open in browser" menu
// opens whatever is there), on Android opens it straight in Chrome, and copies it on request.
//
// In a real browser (body[data-continue="browser"]) the carried titles are added to this
// browser's guest list, the link is cleaned off the address bar, and the page lists them
// above Continue with Google. Nothing is sent anywhere until the visitor signs up.
(function () {
  'use strict';

  const CARRY = 'ot-carry=';
  const MAX_CARRY = 12000;
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book', 'manga', 'podcast', 'audiobook']);
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const PATH = /^\/[A-Za-z0-9/_.-]{1,200}$/;
  const INVITE = /^[A-Za-z0-9_-]{16,32}$/;
  const IMAGE = /^https?:\/\/[^\s"'<>]{1,490}$/;
  const RETURN_KEY = 'omnitrackr_guest_return';
  const INVITE_KEY = 'omnitrackr_friend_invite';
  const KIND_LABELS = { movie: 'Movie', tv: 'TV show', anime: 'Anime', game: 'Game', album: 'Album', book: 'Book',
    manga: 'Manga', podcast: 'Podcast', audiobook: 'Audiobook' };
  const SHOWN = 6;

  const sent = new Set();
  function report(event) {
    if (sent.has(event)) return;
    sent.add(event);
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  // ------------------------------------------------------------ the carried data
  // {v: 1, l: [{k: kind, s: slug, t: title, i: cover}], r: {p: path, t: title}}, as base64url JSON.
  function toBase64Url(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    bytes.forEach(byte => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function fromBase64Url(text) {
    const padded = text.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((text.length + 3) % 4);
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return new TextDecoder().decode(bytes);
  }

  function cleanItem(item) {
    if (!item || !KINDS.has(item.k) || !SLUG.test(item.s || '') || typeof item.t !== 'string') return null;
    const clean = { kind: item.k, slug: item.s, title: item.t.slice(0, 200) };
    if (typeof item.i === 'string' && IMAGE.test(item.i)) clean.image = item.i;
    return clean;
  }

  function cleanReturn(back) {
    if (!back || typeof back.p !== 'string' || !PATH.test(back.p) || back.p.startsWith('//')) return null;
    return { path: back.p, title: typeof back.t === 'string' ? back.t.slice(0, 80) : '' };
  }

  function pack(list, back, { images = true, max = 30 } = {}) {
    const data = { v: 1, l: [] };
    list.slice(0, max).forEach(item => {
      const packed = { k: item.kind, s: item.slug, t: String(item.title || '').slice(0, 80) };
      if (images && typeof item.image === 'string' && IMAGE.test(item.image)) packed.i = item.image;
      data.l.push(packed);
    });
    if (back && PATH.test(back.path || '')) data.r = { p: back.path, t: String(back.title || '').slice(0, 80) };
    return toBase64Url(JSON.stringify(data));
  }

  function unpack(text) {
    if (typeof text !== 'string' || !text || text.length > MAX_CARRY || !/^[A-Za-z0-9_-]+$/.test(text)) return null;
    try {
      const data = JSON.parse(fromBase64Url(text));
      if (!data || data.v !== 1) return null;
      const items = Array.isArray(data.l) ? data.l.map(cleanItem).filter(Boolean).slice(0, 30) : [];
      return { items, back: cleanReturn(data.r) };
    } catch (error) {
      return null;
    }
  }

  // The carried text from "#ot-carry=..." (copied links, the app's menu) or "?carry=..." (Chrome on Android).
  function carriedText(location) {
    const hash = location.hash || '';
    if (hash.startsWith(`#${CARRY}`)) return hash.slice(CARRY.length + 1);
    try {
      return new URLSearchParams(location.search || '').get('carry');
    } catch (error) {
      return null;
    }
  }

  // ------------------------------------------------------------ helpers
  function guestList() {
    return typeof window !== 'undefined' ? window.OmniGuestList || null : null;
  }

  function invite() {
    const body = typeof document !== 'undefined' ? document.body : null;
    const value = body && body.dataset ? body.dataset.invite || '' : '';
    return INVITE.test(value) ? value : '';
  }

  // Where the visitor was: the page they last saved from (guest-list.js), else the page the button was on.
  function whereFrom(list) {
    const saved = list && typeof list.readReturn === 'function' ? list.readReturn() : null;
    if (saved) return saved;
    const path = document.body && document.body.dataset ? document.body.dataset.from || '' : '';
    return PATH.test(path) ? { path, title: '' } : null;
  }

  function continueQuery(extra) {
    const params = new URLSearchParams();
    params.set('via', 'app');
    if (invite()) params.set('invite', invite());
    Object.entries(extra || {}).forEach(([key, value]) => params.set(key, value));
    return params.toString();
  }

  function carryLink(origin, list, back) {
    return `${origin}/continue?${continueQuery()}#${CARRY}${pack(list, back)}`;
  }

  // Chrome on Android: an intent link, with the titles in the query string (the # belongs to the intent).
  function chromeLink(host, list, back, fallback) {
    const query = continueQuery({ carry: pack(list, back, { images: false }) });
    return `intent://${host}/continue?${query}#Intent;scheme=https;package=com.android.chrome;`
      + `S.browser_fallback_url=${encodeURIComponent(fallback)};end`;
  }

  function titlesNote(count) {
    return count === 1 ? 'The title you saved comes with you.' : `The ${count} titles you saved come with you.`;
  }

  // ------------------------------------------------------------ inside an app's browser
  function setupApp() {
    const list = guestList();
    const saved = list ? list.read() : [];
    const back = whereFrom(list);
    const origin = window.location.origin;
    const link = carryLink(origin, saved, back);
    // The app's "Open in browser" menu opens the address shown, so it carries the list too.
    try {
      window.history.replaceState(null, '', link.slice(origin.length));
    } catch (error) { /* the copy button still works */ }

    const note = document.querySelector('[data-carry-note]');
    if (note && saved.length) {
      note.textContent = titlesNote(saved.length);
      note.hidden = false;
    }

    const chrome = document.querySelector('[data-open-chrome]');
    if (chrome) {
      chrome.href = chromeLink(window.location.host, saved, back, link);
      chrome.addEventListener('click', () => report('inapp_chrome_opened'));
    }

    const copy = document.querySelector('[data-copy-link]');
    const field = document.querySelector('[data-copy-field]');
    const status = document.querySelector('[data-copy-status]');
    if (copy) {
      copy.addEventListener('click', async () => {
        report('inapp_link_copied');
        let copied = false;
        try {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            await navigator.clipboard.writeText(link);
            copied = true;
          }
        } catch (error) { /* some apps block the clipboard: show the link to copy by hand */ }
        if (copied) {
          if (status) status.textContent = 'Link copied. Open your browser, tap the address bar and paste.';
          return;
        }
        if (field) {
          field.value = link;
          field.hidden = false;
          field.focus();
          field.select();
        }
        if (status) status.textContent = 'Press and hold the link above, choose Copy, then paste it into your browser.';
      });
    }

    const email = document.querySelector('[data-continue-email]');
    if (email) email.addEventListener('click', () => report('inapp_email_chosen'));
  }

  // ------------------------------------------------------------ in Safari, Chrome and the rest
  function mergeCarried(list, carried) {
    const current = list.read();
    let added = 0;
    carried.items.forEach(item => {
      if (current.length >= list.MAX) return;
      if (current.some(saved => saved.kind === item.kind && saved.slug === item.slug)) return;
      current.push(item);
      added += 1;
    });
    // Written in one go: guest-list.js's add() would count each one as a new save.
    if (added) list.write(current);
    return added;
  }

  function rememberReturn(back) {
    if (!back) return;
    try {
      localStorage.setItem(RETURN_KEY, JSON.stringify({ path: back.path, title: back.title || 'where you were', at: Date.now() }));
    } catch (error) { /* no link back, that's all */ }
  }

  function showList(list) {
    const box = document.querySelector('[data-continue-list]');
    if (!box || !list) return;
    const saved = list.read();
    if (!saved.length) {
      box.hidden = true;
      return;
    }
    const head = box.querySelector('[data-continue-list-head]');
    const titles = box.querySelector('[data-continue-titles]');
    const more = box.querySelector('[data-continue-more]');
    if (head) head.textContent = saved.length === 1 ? 'On your list, waiting for your account' : `${saved.length} titles on your list, waiting for your account`;
    if (titles) {
      titles.replaceChildren(...saved.slice(-SHOWN).reverse().map(item => {
        const row = document.createElement('li');
        const kind = document.createElement('span');
        kind.className = 'continue-list__kind';
        kind.textContent = KIND_LABELS[item.kind] || '';
        const name = document.createElement('span');
        name.className = 'continue-list__name';
        name.textContent = item.title;
        row.append(kind, name);
        return row;
      }));
    }
    const hidden = saved.length - Math.min(saved.length, SHOWN);
    if (more) {
      more.textContent = hidden ? `and ${hidden} more` : '';
      more.hidden = !hidden;
    }
    box.hidden = false;
  }

  function showBack(back) {
    const line = document.querySelector('[data-continue-back]');
    if (!line || !back) return;
    const link = document.createElement('a');
    link.href = back.path;
    link.textContent = back.title ? `Back to ${back.title}` : 'Back to where you were';
    line.replaceChildren(document.createTextNode('Not ready yet? '), link);
    line.hidden = false;
  }

  function setupBrowser() {
    const list = guestList();
    const carried = unpack(carriedText(window.location));
    if (carriedText(window.location) !== null || /[?&]via=app\b/.test(window.location.search || '')) report('carry_arrived');
    if (carried && list) {
      if (mergeCarried(list, carried) || carried.items.length) report('carry_titles_moved');
      rememberReturn(carried.back);
    }
    // Keep the invite for the email form (auth.js reads it), then take the list off the address bar.
    if (invite()) {
      try { sessionStorage.setItem(INVITE_KEY, invite()); } catch (error) { /* Google keeps it in the link */ }
    }
    try {
      window.history.replaceState(null, '', invite() ? `/continue?invite=${encodeURIComponent(invite())}` : '/continue');
    } catch (error) { /* cosmetic */ }
    showList(list);
    showBack(carried && carried.back ? carried.back : (list && typeof list.readReturn === 'function' ? list.readReturn() : null));
    const google = document.querySelector('[data-continue-google]');
    if (google) google.addEventListener('click', () => report('continue_google'));
    const email = document.querySelector('[data-continue-email]');
    if (email) email.addEventListener('click', () => report('continue_email'));
  }

  function init() {
    const mode = document.body && document.body.dataset ? document.body.dataset.continue : '';
    if (mode === 'app') setupApp();
    else if (mode === 'browser') setupBrowser();
    else if (mode === 'member') {
      const list = guestList();
      const carried = unpack(carriedText(window.location));
      if (carried && list) mergeCarried(list, carried);
      try { window.history.replaceState(null, '', '/continue'); } catch (error) { /* cosmetic */ }
    }
  }

  const api = { pack, unpack, carriedText, carryLink, chromeLink, mergeCarried, cleanItem, titlesNote };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
