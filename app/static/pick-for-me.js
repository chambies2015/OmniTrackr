// Pick for me (/pick): one curated suggestion at a time.
// The pool is embedded in the page (#pickPool), so picking needs no request.
// Visitors save picks to the guest list (guest-list.js handles the button);
// members add them to their library through POST /api/pick/add.
(function () {
  'use strict';

  const RECENT_KEY = 'omnitrackr_pick_recent';
  const RECENT_MAX = 12;
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book']);

  function readRecent() {
    try {
      const list = JSON.parse(sessionStorage.getItem(RECENT_KEY) || '[]');
      return Array.isArray(list) ? list.filter(id => typeof id === 'string').slice(-RECENT_MAX) : [];
    } catch (error) {
      return [];
    }
  }

  function remember(id) {
    const list = readRecent().filter(item => item !== id);
    list.push(id);
    try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(-RECENT_MAX))); } catch (error) { /* optional */ }
  }

  // A random pick in the format, skipping recent ones until nothing else is left.
  function choose(pool, kind, recent, random = Math.random) {
    const options = pool.filter(entry => !kind || entry.kind === kind);
    const seen = new Set(recent || []);
    const fresh = options.filter(entry => !seen.has(entry.id));
    const from = fresh.length ? fresh : options;
    return from.length ? from[Math.floor(random() * from.length)] : null;
  }

  function safeUrl(value, { external = false } = {}) {
    if (typeof value !== 'string') return null;
    if (/^\/(?!\/)/.test(value)) return value;
    return external && /^https?:\/\//i.test(value) ? value : null;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function metaLine(entry) {
    return [entry.label, entry.year, entry.creator].filter(Boolean).join(' · ');
  }

  // Same markup as card() in app/routers/pick.py.
  function buildCard(entry, signedIn) {
    const body = el('div', 'pf-card__body');
    const image = safeUrl(entry.image, { external: true });
    if (image) {
      const art = el('img', 'pf-card__art');
      art.src = image;
      art.alt = '';
      art.width = 120;
      art.height = 180;
      art.loading = 'lazy';
      art.referrerPolicy = 'no-referrer';
      body.appendChild(art);
    }
    const text = el('div', 'pf-card__text');
    text.appendChild(el('p', 'eyebrow pf-card__meta', metaLine(entry)));
    const title = el('h2', 'pf-card__title', entry.title);
    title.id = 'pfCardTitle';
    text.appendChild(title);
    text.appendChild(el('p', 'pf-card__why', entry.why));
    if (entry.caveat) text.appendChild(el('p', 'caveat pf-card__caveat', entry.caveat));
    const source = el('p', 'pf-card__source muted', 'From ');
    const sourceUrl = safeUrl(entry.sourceUrl);
    if (sourceUrl) {
      const link = el('a', '', entry.source);
      link.href = sourceUrl;
      source.appendChild(link);
    } else {
      source.textContent = `From ${entry.source}`;
    }
    text.appendChild(source);
    body.appendChild(text);

    const actions = el('div', 'pf-card__actions');
    const save = el('button', 'button pf-card__save');
    save.type = 'button';
    if (signedIn) {
      save.textContent = 'Add to my library';
      save.dataset.pickAdd = entry.id;
    } else {
      save.dataset.guestKind = entry.kind;
      save.dataset.guestSlug = entry.slug;
      save.dataset.guestTitle = entry.title;
      save.setAttribute('aria-pressed', 'false');
      save.appendChild(el('span', 'pf-when-off', 'Save to my list'));
      save.appendChild(el('span', 'pf-when-on', 'Saved to your list ✓'));
    }
    actions.appendChild(save);
    const again = el('button', 'pf-card__again', 'Pick again');
    again.type = 'button';
    again.dataset.pickAgain = '';
    actions.appendChild(again);
    const share = el('button', 'pf-card__share', 'Share this pick');
    share.type = 'button';
    share.dataset.pickShare = '';
    actions.appendChild(share);
    const titleUrl = safeUrl(entry.url);
    if (titleUrl) {
      const link = el('a', 'pf-card__link', 'See the title page');
      link.href = titleUrl;
      actions.appendChild(link);
    }
    const status = el('p', 'pf-card__status');
    status.dataset.pickStatus = '';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    return [body, actions, status];
  }

  function report(event) {
    report.sent = report.sent || new Set();
    if (report.sent.has(event)) return;
    report.sent.add(event);
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

  function setStatus(card, message, link) {
    const status = card.querySelector('[data-pick-status]');
    if (!status) return;
    status.textContent = message;
    if (link) {
      status.appendChild(document.createTextNode(' '));
      const anchor = el('a', '', link.label);
      anchor.href = link.href;
      status.appendChild(anchor);
    }
  }

  async function addToLibrary(card, button) {
    button.disabled = true;
    setStatus(card, 'Adding…');
    try {
      const response = await fetch('/api/pick/add', {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(),
        body: JSON.stringify({ id: button.dataset.pickAdd }),
      });
      if (response.status === 401) {
        window.location.href = `/?next=${encodeURIComponent('/pick')}#landing-auth`;
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json();
      const href = safeUrl(result.library_url) || '/';
      button.textContent = result.state === 'created' ? 'Added ✓' : 'In your library ✓';
      setStatus(card, result.state === 'created' ? `Added “${result.title}” to your library.` : `“${result.title}” is already in your library.`,
        { label: 'Open it', href });
    } catch (error) {
      button.disabled = false;
      setStatus(card, 'Could not add this pick. Try again in a moment.');
    }
  }

  async function sharePick(card, entry) {
    const url = `${window.location.origin}/pick?pick=${encodeURIComponent(entry.id)}`;
    const text = `OmniTrackr picked “${entry.title}” for me. What does it pick for you?`;
    try {
      if (navigator.share) {
        await navigator.share({ title: 'Pick for me', text, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setStatus(card, 'Link copied. Anyone who opens it sees this pick first.');
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      setStatus(card, `Copy this link to share it: ${url}`);
    }
  }

  function init() {
    const tool = document.getElementById('pick-tool');
    const card = document.getElementById('pickCard');
    const data = document.getElementById('pickPool');
    if (!tool || !card || !data) return;
    let pool = [];
    try {
      pool = JSON.parse(data.textContent || '[]').filter(entry => entry && KINDS.has(entry.kind) && typeof entry.id === 'string');
    } catch (error) {
      return; // The server-rendered pick and the plain form keep working.
    }
    if (!pool.length) return;
    const signedIn = tool.dataset.signedIn === 'true';
    const form = tool.querySelector('[data-pick-form]');
    let current = pool.find(entry => entry.id === card.dataset.pickId) || null;
    if (current) remember(current.id);

    const reveal = () => card.querySelectorAll('[data-pick-again], [data-pick-share]').forEach(node => { node.hidden = false; });
    const show = (entry, { focus = false } = {}) => {
      current = entry;
      card.dataset.pickId = entry.id;
      card.replaceChildren(...buildCard(entry, signedIn));
      reveal();
      remember(entry.id);
      if (window.OmniGuestList && typeof window.OmniGuestList.refreshTiles === 'function') window.OmniGuestList.refreshTiles();
      if (focus) {
        const heading = card.querySelector('.pf-card__title');
        if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
        if (typeof card.scrollIntoView === 'function') card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    };
    const pickNew = () => {
      const checked = form && form.querySelector('input[name="format"]:checked');
      const kind = checked && KINDS.has(checked.value) ? checked.value : '';
      const recent = readRecent();
      const entry = choose(pool, kind, current ? recent.concat(current.id) : recent);
      if (!entry) return;
      report('pick_used');
      show(entry, { focus: true });
    };

    reveal();
    document.querySelectorAll('[data-pick-show]').forEach(node => { node.hidden = false; });
    if (form) {
      form.addEventListener('submit', event => { event.preventDefault(); pickNew(); });
      form.addEventListener('change', pickNew);
    }
    card.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!target || !current) return;
      if (target.hasAttribute('data-pick-again')) pickNew();
      else if (target.hasAttribute('data-pick-share')) sharePick(card, current);
      else if (target.dataset.pickAdd) addToLibrary(card, target);
      else if (target.dataset.guestKind) {
        // guest-list.js toggles the list on the same click; report only a save.
        setTimeout(() => { if (target.getAttribute('aria-pressed') === 'true') report('pick_saved'); }, 0);
      }
    });
    document.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('[data-pick-show]') : null;
      if (!target) return;
      const entry = pool.find(item => item.id === target.dataset.pickShow);
      if (entry) show(entry, { focus: true });
    });
  }

  const api = { choose, buildCard, metaLine, safeUrl };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
