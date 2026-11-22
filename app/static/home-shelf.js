// Homepage "Start your library": the format chips over the picks, and the "Your library" panel
// beside them that fills as a visitor taps covers (guest_picks.shelf_html draws the empty panel).
// The list itself is guest-list.js's: kept in this browser, moved into the library at sign-up.
// Everything here is drawn with textContent and DOM nodes; no markup is ever parsed from a string.
(function () {
  'use strict';

  const SLOTS = 8;
  const ALSO_SHOWN = 4;
  const SEEDS_TRIED = 3;
  const KIND = /^(movie|tv|anime|game|album|book|manga|podcast|audiobook)$/;
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const NOUNS = {
    movie: ['movie', 'movies'], tv: ['TV show', 'TV shows'], anime: ['anime', 'anime'], game: ['game', 'games'],
    album: ['album', 'albums'], book: ['book', 'books'], manga: ['manga', 'manga'], podcast: ['podcast', 'podcasts'],
    audiobook: ['audiobook', 'audiobooks'],
  };
  const LABELS = { movie: 'Movie', tv: 'TV show', anime: 'Anime', game: 'Video game', album: 'Album', book: 'Book',
    manga: 'Manga', podcast: 'Podcast', audiobook: 'Audiobook' };
  const STREAMS = new Set(['movie', 'tv', 'anime']);
  const EPISODES = new Set(['tv', 'anime']);
  const READING = new Set(['book', 'manga', 'audiobook']);

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') window.reportFunnelEvent(event);
  }

  function guestList() {
    return window.OmniGuestList || null;
  }

  function readList() {
    const api = guestList();
    return api ? api.read() : [];
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function imageOf(value) {
    const api = guestList();
    if (api && typeof api.imageOf === 'function') return api.imageOf(value);
    return typeof value === 'string' && /^https?:\/\/[^\s"'<>]{1,490}$/.test(value) ? value : '';
  }

  function key(item) {
    return `${item.kind}:${item.slug}`;
  }

  // A cover, or the title's first letter on the format's colour when there is no cover.
  function cover(item) {
    const art = element('span', 'lp-shelf__cover');
    art.dataset.kind = item.kind;
    const source = imageOf(item.image);
    if (source) {
      const image = element('img');
      image.src = source;
      image.alt = '';
      image.width = 200;
      image.height = 300;
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      art.appendChild(image);
    } else {
      art.appendChild(element('span', 'lp-shelf__initial', (item.title || '?').trim().charAt(0).toUpperCase() || '?'));
    }
    return art;
  }

  function countLine(list) {
    if (!list.length) return 'Nothing on it yet';
    const counts = {};
    list.forEach(item => { counts[item.kind] = (counts[item.kind] || 0) + 1; });
    const parts = Object.keys(counts).sort((a, b) => counts[b] - counts[a])
      .map(kind => `${counts[kind]} ${(NOUNS[kind] || ['title', 'titles'])[counts[kind] === 1 ? 0 : 1]}`);
    if (parts.length === 1) return parts[0];
    return `${list.length} titles: ${parts.slice(0, 4).join(', ')}${parts.length > 4 ? ' and more' : ''}`;
  }

  // What keeping the list gets them, in terms of what they saved. Every line is a feature members have.
  function perks(list) {
    const lines = [`Rate ${list[0].title} and log the day you finish it`];
    if (list.some(item => STREAMS.has(item.kind))) {
      lines.push('See which of these are on your US streaming services, and get a note when one arrives');
    }
    const show = list.find(item => EPISODES.has(item.kind));
    if (show) lines.push(`Get a note when ${show.title} has a new episode out`);
    else if (list.some(item => READING.has(item.kind))) lines.push('Save the page or chapter you’re on');
    else lines.push('See everything you finish in your Year in Review');
    return lines.slice(0, 3);
  }

  // ------------------------------------------------------------ "Members who track X also track"
  const asked = new Map();

  function suggestionsFor(item) {
    const id = key(item);
    if (!asked.has(id)) {
      const url = `/api/guest-list/suggest?kind=${encodeURIComponent(item.kind)}&slug=${encodeURIComponent(item.slug)}`;
      asked.set(id, fetch(url, { credentials: 'same-origin' })
        .then(response => (response.ok ? response.json() : { results: [] }))
        .then(data => (Array.isArray(data.results) ? data.results : [])
          .filter(entry => entry && KIND.test(entry.kind) && SLUG.test(entry.slug || '') && typeof entry.title === 'string'))
        .catch(() => []));
    }
    return asked.get(id);
  }

  // Popular tiles on the page that aren't saved yet, for when nothing else fits.
  function popularOnPage(saved) {
    return Array.prototype.slice.call(document.querySelectorAll('[data-picks-top] [data-guest-slug]'))
      .map(tile => {
        const image = tile.querySelector('img');
        return { kind: tile.dataset.guestKind, slug: tile.dataset.guestSlug, title: tile.dataset.guestTitle,
          image: image ? image.getAttribute('src') : '' };
      })
      .filter(entry => KIND.test(entry.kind || '') && !saved.has(key(entry)));
  }

  function alsoButton(entry) {
    const button = element('button', 'lp-shelf__pick');
    button.type = 'button';
    // guest-list.js saves any button with these, cover included, and redraws the panel.
    button.dataset.guestKind = entry.kind;
    button.dataset.guestSlug = entry.slug;
    button.dataset.guestTitle = entry.title;
    if (imageOf(entry.image)) button.dataset.guestImage = entry.image;
    button.dataset.shelfPick = '';
    button.setAttribute('aria-pressed', 'false');
    const label = entry.label || LABELS[entry.kind] || '';
    button.setAttribute('aria-label', `Add ${entry.title}${label ? ` (${label}${entry.year ? `, ${entry.year}` : ''})` : ''}`);
    const art = cover(entry);
    art.appendChild(element('span', 'lp-shelf__pick-add', '+'));
    art.lastChild.setAttribute('aria-hidden', 'true');
    button.append(art, element('span', 'lp-shelf__pick-title', entry.title));
    return button;
  }

  let alsoRun = 0;

  async function drawAlso(shelf, list) {
    const run = ++alsoRun;
    const box = shelf.querySelector('[data-shelf-also]');
    const because = shelf.querySelector('[data-shelf-because]');
    const row = shelf.querySelector('[data-shelf-also-list]');
    if (!box || !because || !row) return;
    if (!list.length) {
      box.hidden = true;
      return;
    }
    const saved = new Set(list.map(key));
    let heading = '';
    let picks = [];
    for (const seed of list.slice(-SEEDS_TRIED).reverse()) {
      const results = (await suggestionsFor(seed)).filter(entry => !saved.has(key(entry)));
      if (run !== alsoRun) return; // The list changed while we waited.
      if (results.length >= 2) {
        heading = `Members who track ${seed.title} also track`;
        picks = results;
        break;
      }
    }
    if (!picks.length) {
      heading = 'More that members track';
      picks = popularOnPage(saved);
    }
    picks = picks.slice(0, ALSO_SHOWN);
    because.textContent = heading;
    row.replaceChildren(...picks.map(entry => {
      const item = element('li');
      item.appendChild(alsoButton(entry));
      return item;
    }));
    box.hidden = picks.length === 0;
  }

  // ------------------------------------------------------------ the panel
  let shown = new Set();

  function drawSlots(shelf, list) {
    const slots = shelf.querySelector('[data-shelf-slots]');
    if (!slots) return;
    const visible = list.length > SLOTS ? list.slice(-(SLOTS - 1)) : list;
    const hidden = list.length - visible.length;
    const nodes = [];
    if (hidden) {
      const more = element('li', 'lp-shelf__slot is-filled');
      more.appendChild(element('span', 'lp-shelf__more', `+${hidden}`));
      more.appendChild(element('span', 'sr-only', ' more saved'));
      nodes.push(more);
    }
    visible.forEach(item => {
      const slot = element('li', 'lp-shelf__slot is-filled');
      if (!shown.has(key(item))) slot.classList.add('is-new');
      slot.title = item.title;
      slot.appendChild(cover(item));
      slot.appendChild(element('span', 'sr-only', `${item.title}, ${LABELS[item.kind] || ''}`));
      const remove = element('button', 'lp-shelf__remove', '×');
      remove.type = 'button';
      remove.dataset.shelfRemove = '';
      remove.dataset.kind = item.kind;
      remove.dataset.slug = item.slug;
      remove.setAttribute('aria-label', `Take ${item.title} off your list`);
      slot.appendChild(remove);
      nodes.push(slot);
    });
    while (nodes.length < SLOTS) {
      const blank = element('li', 'lp-shelf__slot');
      blank.setAttribute('aria-hidden', 'true');
      nodes.push(blank);
    }
    slots.replaceChildren(...nodes);
    shown = new Set(list.map(key));
  }

  function drawKeep(shelf, list) {
    const keep = shelf.querySelector('[data-shelf-keep]');
    const lines = shelf.querySelector('[data-shelf-perks]');
    if (!keep || !lines) return;
    keep.hidden = !list.length;
    if (!list.length) return;
    lines.replaceChildren(...perks(list).map(text => element('li', '', text)));
  }

  function drawShelf(shelf, list) {
    shelf.classList.toggle('is-empty', !list.length);
    shelf.classList.toggle('is-short', list.length <= SLOTS / 2);
    const count = shelf.querySelector('[data-shelf-count]');
    if (count) count.textContent = countLine(list);
    const empty = shelf.querySelector('[data-shelf-empty]');
    if (empty) empty.hidden = list.length > 0;
    drawSlots(shelf, list);
    drawKeep(shelf, list);
    drawAlso(shelf, list);
  }

  // The save bar's little stack of covers, and the hero's "Saved to your list" card.
  function drawElsewhere(list, hasShelf) {
    document.querySelectorAll('[data-savebar-covers]').forEach(stack => {
      stack.hidden = !list.length || !hasShelf;
      stack.replaceChildren(...list.slice(-3).reverse().map(cover));
    });
    const card = document.querySelector('.lp-stage__card--saved strong');
    if (card && list.length) card.textContent = list[list.length - 1].title;
  }

  function setupShelf() {
    const shelf = document.querySelector('[data-guest-shelf]');
    const redraw = list => {
      if (shelf) drawShelf(shelf, list);
      drawElsewhere(list, !!shelf);
    };
    document.addEventListener('omni:guest-list', event => {
      redraw(event.detail && Array.isArray(event.detail.list) ? event.detail.list : readList());
    });
    // Another tab saved or signed up.
    window.addEventListener('storage', event => {
      const api = guestList();
      if (api && event.key === api.KEY) api.refreshTiles();
    });
    if (!shelf) {
      redraw(readList());
      return;
    }
    shown = new Set(readList().map(key)); // No pop-in for titles saved on an earlier visit.
    redraw(readList());
    shelf.addEventListener('click', event => {
      const remove = event.target.closest('[data-shelf-remove]');
      if (remove) {
        const api = guestList();
        if (!api) return;
        api.remove(remove.dataset.kind, remove.dataset.slug);
        api.refreshTiles();
        const title = document.getElementById('lp-shelf-title');
        if (title) {
          title.tabIndex = -1;
          title.focus({ preventScroll: true });
        }
        return;
      }
      const also = event.target.closest('[data-shelf-pick]');
      if (also) {
        report('home_shelf_suggestion_added');
        const index = Array.prototype.indexOf.call(shelf.querySelectorAll('[data-shelf-also-list] button'), also);
        // guest-list.js saves it and the row is drawn again without it: keep the keyboard nearby.
        setTimeout(() => {
          const buttons = shelf.querySelectorAll('[data-shelf-also-list] button');
          const next = buttons[Math.min(index, buttons.length - 1)] || shelf.querySelector('[data-shelf-count]');
          if (next && document.activeElement === document.body && typeof next.focus === 'function') next.focus({ preventScroll: true });
        }, 0);
        return;
      }
      if (event.target.closest('[data-shelf-signup]')) report('home_shelf_signup');
    });
  }

  // ------------------------------------------------------------ format chips
  function setupChips() {
    const chips = Array.prototype.slice.call(document.querySelectorAll('[data-picks-filter]'));
    const grid = document.querySelector('.lp-picks__grid');
    if (!chips.length || !grid) return;
    chips.forEach(chip => chip.addEventListener('click', () => {
      const which = chip.dataset.picksFilter;
      chips.forEach(other => other.setAttribute('aria-pressed', String(other === chip)));
      grid.querySelectorAll('li[data-picks-kind]').forEach(tile => {
        tile.hidden = which === 'top' ? !tile.hasAttribute('data-picks-top') : tile.dataset.picksKind !== which;
      });
      if (which !== 'top') report('home_picks_filtered');
    }));
  }

  // "Not here? Search for any title" goes back up to the hero search, ready to type.
  function setupSearchLink() {
    document.querySelectorAll('[data-picks-search]').forEach(link => link.addEventListener('click', event => {
      const input = document.getElementById('lpSearchInput');
      if (!input) return;
      event.preventDefault();
      const calm = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const form = input.closest('form') || input;
      form.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'center' });
      input.focus({ preventScroll: true });
    }));
  }

  function init() {
    setupChips();
    setupSearchLink();
    setupShelf();
  }

  const api = { countLine, perks, init };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener && typeof window !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
