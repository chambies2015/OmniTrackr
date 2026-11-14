/* Header extras for public pages, kept apart from site.js so sandboxed pages
   (the demo) can leave them out: the member button swap and title search. */
/* Signed-in visitors see "My library" instead of "Log in" and "Start tracking".
   The session itself is an HttpOnly cookie, so this reads the same stored hint
   the dashboard uses; a stale hint only means the button leads to the homepage. */
(function () {
  let member = false;
  try {
    member = Boolean(window.localStorage.getItem('omnitrackr_user') || window.localStorage.getItem('omnitrackr_token'));
  } catch (_) { return; }
  if (!member) return;
  document.querySelectorAll('[data-guest-only]').forEach(function (el) { el.hidden = true; });
  document.querySelectorAll('.site-header').forEach(function (header) {
    header.classList.add('is-member');
    header.querySelectorAll('.site-nav__library, .site-menu__library').forEach(function (link) { link.hidden = false; });
  });
})();

/* Saving from search: members add a title straight to their library
   (POST /api/titles/<kind>/<slug>/add, the same call as the title page button);
   visitors put it on the browser-only guest list that guest-list.js moves into a
   new library at sign-up. Used by the header search and the /search page. */
(function () {
  const GUEST_KEY = 'omnitrackr_guest_list';
  const GUEST_MAX = 30;
  const KINDS = ['movie', 'tv', 'anime', 'game', 'album', 'book', 'manga', 'podcast', 'audiobook'];
  const SLUG = /^[a-z0-9-]{1,130}$/;

  function storedToken() {
    try { return window.localStorage.getItem('omnitrackr_token') || ''; } catch (_) { return ''; }
  }

  function member() {
    try {
      return Boolean(window.localStorage.getItem('omnitrackr_user') || window.localStorage.getItem('omnitrackr_token'));
    } catch (_) { return false; }
  }

  function guestList() {
    if (window.OmniGuestList) return window.OmniGuestList.read();
    try {
      const list = JSON.parse(window.localStorage.getItem(GUEST_KEY) || '[]');
      return Array.isArray(list) ? list : [];
    } catch (_) { return []; }
  }

  function guestHas(kind, slug) {
    return guestList().some(function (item) { return item && item.kind === kind && item.slug === slug; });
  }

  // { saved, full, failed, count }
  function guestToggle(kind, slug, title) {
    if (KINDS.indexOf(kind) < 0 || !SLUG.test(slug || '')) return { failed: true };
    const api = window.OmniGuestList;
    if (guestHas(kind, slug)) {
      if (api) api.remove(kind, slug);
      else {
        const left = guestList().filter(function (item) { return !(item.kind === kind && item.slug === slug); });
        try {
          if (left.length) window.localStorage.setItem(GUEST_KEY, JSON.stringify(left));
          else window.localStorage.removeItem(GUEST_KEY);
        } catch (_) { return { failed: true }; }
      }
      if (api) api.refreshTiles();
      return { saved: false, count: guestList().length };
    }
    if (api) {
      const result = api.add(kind, slug, title);
      api.refreshTiles();
      return { saved: result.added, full: result.full, failed: !result.added && !result.full, count: guestList().length };
    }
    const list = guestList();
    if (list.length >= GUEST_MAX) return { saved: false, full: true, count: list.length };
    list.push({ kind: kind, slug: slug, title: String(title || '').slice(0, 200) });
    try { window.localStorage.setItem(GUEST_KEY, JSON.stringify(list)); } catch (_) { return { failed: true }; }
    return { saved: true, count: list.length };
  }

  function addToLibrary(kind, slug) {
    const headers = { Accept: 'application/json' };
    const token = storedToken();
    if (token) headers.Authorization = 'Bearer ' + token;
    return fetch('/api/titles/' + encodeURIComponent(kind) + '/' + encodeURIComponent(slug) + '/add',
      { method: 'POST', credentials: 'same-origin', headers: headers })
      .then(function (response) {
        if (response.status === 401) return { signedOut: true };
        if (!response.ok) return Promise.reject(new Error(String(response.status)));
        return response.json().then(function (data) { return { added: true, existing: data && data.state === 'existing' }; });
      });
  }

  window.OmniSiteSave = { member: member, guestHas: guestHas, guestToggle: guestToggle, addToLibrary: addToLibrary };

  // Member "Add" buttons on the /search page.
  document.addEventListener('click', function (event) {
    const button = event.target && event.target.closest ? event.target.closest('[data-site-add]') : null;
    if (!button || button.disabled) return;
    button.disabled = true;
    addToLibrary(button.dataset.kind, button.dataset.slug).then(function (result) {
      if (result.signedOut) { window.location.href = '/#landing-auth'; return; }
      button.classList.add('is-done');
      const done = button.querySelector('.search-card__save-done');
      if (done && result.existing) done.textContent = '✓ In your library';
    }).catch(function () {
      button.disabled = false;
      const idle = button.querySelector('.search-card__save-idle');
      if (idle) idle.textContent = 'Try again';
    });
  });
})();

/* The header search: a dialog over the page (a full-height sheet on phones)
   that looks up titles, guides, pages and people as you type (GET /api/search).
   Format chips narrow it to one kind of title, an empty box shows recent
   searches and popular titles, and every title can be saved in one tap.
   Results are drawn with textContent only. "/" or Ctrl/Cmd+K opens it from
   anywhere outside a text field; links marked data-site-search-open (the
   not-found page) open it too, filled in with their data-search-hint. */
(function () {
  const trigger = document.querySelector('.site-search[data-site-search]');
  if (!trigger || typeof window.HTMLDialogElement !== 'function') return;

  const RECENT_KEY = 'omnitrackr_recent_searches';
  const RECENT_MAX = 6;
  const FORMATS = [['', 'All'], ['movie', 'Movies'], ['tv', 'TV'], ['anime', 'Anime'], ['game', 'Games'],
    ['album', 'Music'], ['book', 'Books'], ['manga', 'Manga'], ['podcast', 'Podcasts'], ['audiobook', 'Audiobooks']];
  const STARTERS = [
    ['Best of 2026', '/best-of', 'The year so far, picked and explained'],
    ['Franchises in order', '/in-order', 'Watch and play the big series the right way'],
    ['How long does it take?', '/binge-calculator', 'Hours to finish a show, anime or series'],
    ['Popular titles', '/titles', 'Everything members are tracking'],
  ];
  const SECTION_MARK = { 'In order': '⇢', 'How long it takes': '⏱', 'If you liked': '♥', 'Best of': '★',
    'Release guide': '◷', 'Switch trackers': '⇄', 'Discover': '✦', Page: '→' };
  const pageForm = document.querySelector('form[data-search-page]');
  let dialog = null;
  let input = null;
  let body = null;
  let status = null;
  let chips = null;
  let kind = '';
  let timer = null;
  let request = 0;
  let selected = -1;
  let opener = trigger;
  const popular = {};

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // ---------- recent searches (this browser only)
  function recent() {
    try {
      const list = JSON.parse(window.localStorage.getItem(RECENT_KEY) || '[]');
      return Array.isArray(list) ? list.filter(function (q) { return typeof q === 'string' && q.length >= 2; }).slice(0, RECENT_MAX) : [];
    } catch (_) { return []; }
  }

  function remember(text) {
    const q = String(text || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    if (q.length < 2) return;
    const list = [q].concat(recent().filter(function (item) { return item.toLowerCase() !== q.toLowerCase(); })).slice(0, RECENT_MAX);
    try { window.localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch (_) { /* private mode */ }
  }

  function forget(text) {
    const list = recent().filter(function (item) { return item !== text; });
    try {
      if (list.length) window.localStorage.setItem(RECENT_KEY, JSON.stringify(list));
      else window.localStorage.removeItem(RECENT_KEY);
    } catch (_) { /* private mode */ }
  }

  // ---------- options and keyboard selection
  function options() {
    return Array.from(body.querySelectorAll('[role="option"]'));
  }

  function select(index) {
    const all = options();
    all.forEach(function (link) { link.setAttribute('aria-selected', 'false'); });
    if (!all.length) { selected = -1; input.removeAttribute('aria-activedescendant'); return; }
    selected = (index + all.length) % all.length;
    all[selected].setAttribute('aria-selected', 'true');
    all[selected].scrollIntoView({ block: 'nearest' });
    input.setAttribute('aria-activedescendant', all[selected].id);
  }

  function searchUrl(text) {
    const params = new URLSearchParams();
    if (text) params.set('q', text);
    if (kind) params.set('kind', kind);
    const query = params.toString();
    return '/search' + (query ? '?' + query : '');
  }

  let optionCount = 0;
  function option(href, art, title, meta, className) {
    const link = el('a', 'site-finder__row' + (className ? ' ' + className : ''));
    link.href = href;
    link.id = 'site-finder-option-' + (optionCount++);
    link.setAttribute('role', 'option');
    link.setAttribute('aria-selected', 'false');
    const text = el('span', 'site-finder__text');
    text.appendChild(el('strong', '', title));
    if (meta) text.appendChild(el('span', '', meta));
    link.append(art, text);
    return link;
  }

  function poster(item) {
    const art = el('span', 'site-finder__art');
    if (item.image && /^https?:\/\//.test(item.image)) {
      const img = el('img');
      img.src = item.image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', function () { img.remove(); });
      art.appendChild(img);
    } else {
      art.textContent = String(item.title || '?').charAt(0).toUpperCase();
    }
    return art;
  }

  function mark(symbol, className) {
    const art = el('span', 'site-finder__mark' + (className ? ' ' + className : ''), symbol);
    art.setAttribute('aria-hidden', 'true');
    return art;
  }

  function group(label, rows, extra) {
    const section = el('div', 'site-finder__group');
    const head = label ? el('div', 'site-finder__head') : null;
    if (head) head.appendChild(el('p', 'site-finder__label', label));
    if (head && extra) head.appendChild(extra);
    const list = el('ul', 'site-finder__list');
    list.setAttribute('role', 'group');
    list.setAttribute('aria-label', label);
    rows.forEach(function (row) {
      const li = el('li');
      li.setAttribute('role', 'none');
      row.forEach(function (node) { li.appendChild(node); });
      list.appendChild(li);
    });
    if (head) section.appendChild(head);
    section.appendChild(list);
    return section;
  }

  function saveButton(item) {
    const save = window.OmniSiteSave;
    const button = el('button', 'site-finder__save');
    button.type = 'button';
    let isMember = Boolean(save && save.member());
    const saved = !isMember && save && save.guestHas(item.kind, item.slug);
    function show(state) {
      const done = state === 'saved' || state === 'added' || state === 'existing';
      button.setAttribute('aria-pressed', String(done));
      button.textContent = state === 'added' ? '✓ Added' : state === 'existing' ? '✓ In library'
        : state === 'saved' ? '✓ Saved' : state === 'busy' ? '…' : isMember ? '＋ Add' : '＋ Save';
      button.setAttribute('aria-label', (done ? (isMember ? 'In your library: ' : 'Saved: ') : (isMember ? 'Add to your library: ' : 'Save to your list: ')) + item.title);
    }
    show(saved ? 'saved' : 'idle');
    button.addEventListener('click', function () {
      if (!save) return;
      function guest() {
        const result = save.guestToggle(item.kind, item.slug, item.title);
        show(result.saved ? 'saved' : 'idle');
        if (result.full) note('Your list is full (30 titles). Sign up to keep them and save more.', true);
        else if (result.failed) note('This browser could not save your list. Turn on site storage and try again.');
        else if (result.count) note(result.count + (result.count === 1 ? ' title' : ' titles') + ' on your list. Sign up free and they move into your library.', true);
        else note('');
      }
      if (!isMember) { guest(); return; }
      if (button.getAttribute('aria-pressed') === 'true') return;
      show('busy');
      save.addToLibrary(item.kind, item.slug).then(function (result) {
        // The stored sign-in hint was stale: keep it on the guest list instead.
        if (result.signedOut) { isMember = false; guest(); return; }
        show(result.existing ? 'existing' : 'added');
        note(result.existing ? item.title + ' is already in your library.' : 'Added ' + item.title + ' to your library.');
      }).catch(function () { show('idle'); note('Could not add it right now. Try again in a moment.'); });
    });
    return button;
  }

  function note(message, withSignup) {
    status.replaceChildren();
    status.hidden = !message;
    if (!message) return;
    status.appendChild(el('span', '', message));
    if (withSignup) {
      const link = el('a', '', 'Sign up free');
      link.href = '/#signup';
      status.appendChild(link);
    }
  }

  function titleRows(items) {
    return items.map(function (item) {
      const meta = [item.label, item.year, item.members ? item.members + ' members' : ''].filter(Boolean).join(' · ');
      const link = option(item.url, poster(item), item.title, meta);
      return [link, saveButton(item)];
    });
  }

  function seeAll(text, label) {
    const link = option(searchUrl(text), mark('⌕', 'site-finder__mark--all'), label, '', 'site-finder__row--all');
    return group('', [[link]]);
  }

  function render(parts) {
    optionCount = 0;
    body.replaceChildren.apply(body, parts.filter(Boolean));
    selected = -1;
    input.removeAttribute('aria-activedescendant');
  }

  function message(text, extra) {
    const p = el('p', 'site-finder__note', text);
    if (extra) { p.append(' '); p.appendChild(extra); }
    return p;
  }

  // ---------- empty box: recent searches, popular titles, places to start
  function home() {
    request++;
    const parts = [];
    const past = recent();
    if (past.length) {
      const clear = el('button', 'site-finder__clear', 'Clear');
      clear.type = 'button';
      clear.addEventListener('click', function () {
        try { window.localStorage.removeItem(RECENT_KEY); } catch (_) { /* ignore */ }
        home();
        input.focus();
      });
      parts.push(group('Recent', past.map(function (q) {
        const link = option(searchUrl(q), mark('↺'), q, '');
        link.addEventListener('click', function (event) {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button === 1) return;
          event.preventDefault();
          input.value = q;
          run();
          input.focus();
        });
        const remove = el('button', 'site-finder__forget', '×');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Remove ' + q + ' from recent searches');
        remove.addEventListener('click', function () { forget(q); home(); input.focus(); });
        return [link, remove];
      }), clear));
    }
    const cached = popular[kind];
    if (cached && cached.length) {
      const label = kind ? 'Popular ' + FORMATS.find(function (f) { return f[0] === kind; })[1].toLowerCase() : 'Popular with members';
      parts.push(group(label, titleRows(cached)));
    }
    if (!kind) {
      parts.push(group('Good places to start', STARTERS.map(function (row) {
        return [option(row[1], mark('→'), row[0], row[2])];
      })));
    }
    render(parts);
    if (cached === undefined) {
      const id = request;
      popular[kind] = null;
      const wanted = kind;
      fetch('/api/search?' + new URLSearchParams(kind ? { kind: kind } : {}).toString(), { headers: { Accept: 'application/json' } })
        .then(function (response) { return response.ok ? response.json() : Promise.reject(response.status); })
        .then(function (data) {
          popular[wanted] = (data && data.popular) || [];
          if (id === request && wanted === kind && !input.value.trim()) home();
        })
        .catch(function () { delete popular[wanted]; });
    }
  }

  // ---------- results
  function show(text, data) {
    const parts = [];
    const titles = data.titles || [];
    const guides = data.guides || [];
    const people = data.people || [];
    if (data.suggestion) {
      const fix = el('button', 'site-finder__suggest', data.suggestion);
      fix.type = 'button';
      fix.addEventListener('click', function () { input.value = data.suggestion; run(); input.focus(); });
      parts.push(message('Did you mean', fix));
    }
    if (titles.length) parts.push(group(kind ? FORMATS.find(function (f) { return f[0] === kind; })[1] : 'Titles', titleRows(titles)));
    if (guides.length) {
      parts.push(group('Guides and pages', guides.map(function (guide) {
        return [option(guide.url, mark(SECTION_MARK[guide.section] || '→', 'site-finder__mark--guide'), guide.title,
          guide.section === 'Page' ? guide.detail : guide.section)];
      })));
    }
    if (people.length) {
      parts.push(group('People and studios', people.map(function (person) {
        return [option(person.url, mark(person.name.charAt(0).toUpperCase(), 'site-finder__mark--person'), person.name,
          person.role + ' · ' + person.titles + ' titles')];
      })));
    }
    if (!titles.length && !guides.length && !people.length) {
      const where = kind ? ' among ' + FORMATS.find(function (f) { return f[0] === kind; })[1].toLowerCase() : '';
      const signedIn = Boolean(window.OmniSiteSave && window.OmniSiteSave.member());
      const link = el('a', '', signedIn ? 'Look it up in Add anything' : 'Start a free library');
      link.href = signedIn ? '/?' + new URLSearchParams({ find: text }).toString() : '/#signup';
      parts.push(message('No tracked title matches “' + text + '”' + where + ' yet. '
        + (signedIn ? 'Add anything can find it anywhere.' : 'Your own library can look up and add any title.'), link));
    } else {
      parts.push(seeAll(text, data.more ? 'See all ' + (data.total || '') + ' results for “' + text + '”' : 'Open the results page for “' + text + '”'));
    }
    render(parts);
  }

  function run() {
    clearTimeout(timer);
    const text = input.value.replace(/\s+/g, ' ').trim();
    if (text.replace(/[^\p{L}\p{N}]/gu, '').length < 2) { home(); return; }
    const id = ++request;
    const params = new URLSearchParams({ q: text.slice(0, 80) });
    if (kind) params.set('kind', kind);
    fetch('/api/search?' + params.toString(), { headers: { Accept: 'application/json' } })
      .then(function (response) { return response.ok ? response.json() : Promise.reject(response.status); })
      .then(function (data) { if (id === request) show(text, data || {}); })
      .catch(function () {
        if (id !== request) return;
        const link = el('a', '', 'Browse popular titles');
        link.href = '/titles';
        render([message('Search is not available right now.', link)]);
      });
  }

  function setKind(value) {
    kind = value;
    chips.querySelectorAll('button').forEach(function (chip) {
      chip.setAttribute('aria-pressed', String(chip.dataset.kind === kind));
    });
    run();
    input.focus();
  }

  function build() {
    dialog = el('dialog', 'site-finder');
    dialog.setAttribute('aria-label', 'Search OmniTrackr');
    const box = el('div', 'site-finder__box');
    const field = el('div', 'site-finder__field');
    const icon = trigger.querySelector('svg');
    if (icon) field.appendChild(icon.cloneNode(true));
    input = el('input');
    input.type = 'search';
    input.placeholder = 'Search titles, guides and people…';
    input.maxLength = 200;
    input.autocomplete = 'off';
    input.enterKeyHint = 'search';
    input.setAttribute('aria-label', 'Search OmniTrackr');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-controls', 'site-finder-body');
    input.setAttribute('aria-autocomplete', 'list');
    const close = el('button', 'site-finder__close');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close search');
    close.append(el('span', 'site-finder__close-key', 'Esc'), el('span', 'site-finder__close-word', 'Cancel'));
    close.addEventListener('click', function () { dialog.close(); });
    field.append(input, close);
    chips = el('div', 'site-finder__chips');
    chips.setAttribute('role', 'group');
    chips.setAttribute('aria-label', 'Search in');
    FORMATS.forEach(function (format) {
      const chip = el('button', 'site-finder__chip', format[1]);
      chip.type = 'button';
      chip.dataset.kind = format[0];
      chip.setAttribute('aria-pressed', String(format[0] === kind));
      chip.addEventListener('click', function () { setKind(format[0]); });
      chips.appendChild(chip);
    });
    body = el('div', 'site-finder__body');
    body.id = 'site-finder-body';
    body.setAttribute('role', 'listbox');
    body.setAttribute('aria-label', 'Search results');
    status = el('p', 'site-finder__status');
    status.setAttribute('role', 'status');
    status.hidden = true;
    const foot = el('div', 'site-finder__foot');
    foot.setAttribute('aria-hidden', 'true');
    [['↑↓', 'move'], ['Enter', 'open'], ['Esc', 'close']].forEach(function (pair) {
      const hint = el('span');
      hint.append(el('kbd', '', pair[0]), ' ' + pair[1]);
      foot.appendChild(hint);
    });
    box.append(field, chips, body, status, foot);
    dialog.appendChild(box);
    document.body.appendChild(dialog);

    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(run, 180);
    });
    input.addEventListener('keydown', function (event) {
      // A search field clears itself on Escape; close the dialog in one press instead.
      if (event.key === 'Escape') { event.preventDefault(); dialog.close(); }
      else if (event.key === 'ArrowDown') { event.preventDefault(); select(selected + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); select(selected - 1); }
      else if (event.key === 'Enter') {
        event.preventDefault();
        const text = input.value.trim();
        const target = options()[selected];
        if (target) { target.click(); return; }
        if (text.length >= 2) { remember(text); window.location.assign(searchUrl(text)); }
      }
    });
    body.addEventListener('click', function (event) {
      const link = event.target.closest && event.target.closest('a[role="option"]');
      if (link && input.value.trim().length >= 2) remember(input.value.trim());
    });
    body.addEventListener('mousemove', function (event) {
      const link = event.target.closest && event.target.closest('a[role="option"]');
      if (!link) return;
      const index = options().indexOf(link);
      if (index !== selected) {
        options().forEach(function (other) { other.setAttribute('aria-selected', 'false'); });
        link.setAttribute('aria-selected', 'true');
        selected = index;
        input.setAttribute('aria-activedescendant', link.id);
      }
    });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () {
      document.documentElement.classList.remove('site-finder-open');
      if (opener && opener.focus) opener.focus();
    });
  }

  function open(from, hint) {
    if (!dialog) build();
    if (dialog.open) return;
    opener = from || trigger;
    const text = (hint || '').trim();
    input.value = text;
    note('');
    if (text.length >= 2) run(); else home();
    document.documentElement.classList.add('site-finder-open');
    dialog.showModal();
    input.focus();
  }

  function bindOpener(link) {
    link.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button === 1) return;
      event.preventDefault();
      open(link, link.dataset.searchHint);
    });
  }

  bindOpener(trigger);
  document.querySelectorAll('[data-site-search-open]').forEach(bindOpener);
  document.addEventListener('keydown', function (event) {
    const shortcut = (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey)
      || ((event.metaKey || event.ctrlKey) && !event.altKey && String(event.key).toLowerCase() === 'k');
    if (!shortcut) return;
    const active = document.activeElement;
    const typing = active && (active.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName));
    if (typing && event.key === '/') return;
    if (dialog && dialog.open) { event.preventDefault(); input.focus(); input.select(); return; }
    event.preventDefault();
    // The /search page has its own box; jump to it instead of opening a second one.
    const pageInput = pageForm && pageForm.querySelector('input[name="q"]');
    if (pageInput) { pageInput.focus(); pageInput.select(); return; }
    open();
  });

  // The /search page: remember what was searched, so it shows up under Recent.
  if (pageForm) {
    const searched = new URLSearchParams(window.location.search).get('q');
    if (searched) remember(searched);
  }
})();
