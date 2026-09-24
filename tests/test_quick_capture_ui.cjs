// Run with: node --test tests/test_quick_capture_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const categories = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books'];
const settle = () => new Promise(resolve => setImmediate(resolve));
const ok = payload => ({ ok: true, status: 200, json: async () => payload });
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

function provider(url) {
  if (url.includes('/omdb?')) return url.includes('type=series') ? 'tv-shows' : 'movies';
  return Object.entries({ anime: '/jikan?', 'video-games': '/rawg?', music: '/itunes?', books: '/openlibrary?' })
    .find(([, endpoint]) => url.includes(endpoint))?.[0];
}

function payload(category, title) {
  if (category === 'movies' || category === 'tv-shows') {
    return title ? { Response: 'True', Title: title, Year: '2024', Director: 'A Director', Poster: 'N/A' }
      : { Response: 'False', Error: 'Movie not found!' };
  }
  if (category === 'anime') return { data: title ? [{ title, year: 2024, episodes: 12 }] : [] };
  if (category === 'video-games') return { results: title ? [{ name: title, released: '2024-01-01' }] : [] };
  if (category === 'music') return { results: title ? [{ collectionName: title, artistName: 'An Artist', releaseDate: '2024-01-01' }] : [] };
  return { docs: title ? [{ title, author_name: ['An Author'], first_publish_year: 2024 }] : [] };
}

function setup() {
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attributes = {};
      this.style = {}; this.value = ''; this.checked = false; this.hidden = false; this.disabled = false;
      this.type = ''; this._text = ''; this.className = '';
      this.classList = {
        contains: name => this.className.split(' ').includes(name),
        add: name => this.classList.toggle(name, true),
        remove: name => this.classList.toggle(name, false),
        toggle: (name, enabled) => {
          const names = new Set(this.className.split(' ').filter(Boolean));
          if (enabled) names.add(name); else names.delete(name);
          this.className = [...names].join(' ');
        },
      };
    }
    set textContent(value) { this.replaceChildren(); this._text = String(value); }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    replaceChildren(...children) {
      this.children.forEach(child => { child.parentElement = null; });
      this.children = []; this._text = ''; this.append(...children);
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return this.attributes[name] ?? null; }
    removeAttribute(name) { delete this.attributes[name]; }
    focus() { document.activeElement = this; this.focused = true; }
    select() { this.selected = true; }
    scrollIntoView() { this.scrolled = true; }
    contains(element) { return this === element || this.children.some(child => child.contains(element)); }
    querySelectorAll(selector) {
      const match = element => {
        if (selector === 'button[type="submit"]') return element.tagName === 'BUTTON' && element.type === 'submit';
        const data = selector.match(/^\[data-([a-z-]+)(?:="([^"]*)")?\]$/);
        if (data) {
          const key = data[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
          return Object.hasOwn(element.dataset, key) && (data[2] === undefined || element.dataset[key] === data[2]);
        }
        if (selector.startsWith('.')) return element.className.split(' ').includes(selector.slice(1));
        return element.tagName.toLowerCase() === selector;
      };
      return this.children.flatMap(child => [...(match(child) ? [child] : []), ...child.querySelectorAll(selector)]);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  const elements = new Map();
  const add = (id, tag = 'div') => { const element = new Element(tag); element.id = id; elements.set(id, element); return element; };
  const get = id => elements.get(id) || null;
  const document = {
    activeElement: new Element('button'), body: new Element('body'),
    getElementById: get, createElement: tag => new Element(tag),
    querySelectorAll: selector => document.body.querySelectorAll(selector),
    querySelector: selector => document.body.querySelector(selector),
  };
  const modal = add('quickCaptureModal'); modal.style.display = 'flex'; document.body.append(modal);
  const searchForm = add('quickCaptureSearchForm', 'form'); modal.append(searchForm);
  const query = add('quickCaptureQuery', 'input'); searchForm.append(query);
  const submit = add('quickCaptureSubmit', 'button'); submit.type = 'submit'; submit.textContent = 'Search'; searchForm.append(submit);
  const intent = add('quickCaptureIntent', 'select'); intent.value = 'saved'; searchForm.append(intent);
  for (const category of ['all', ...categories]) {
    const button = new Element('button'); button.dataset.quickCategory = category; searchForm.append(button);
  }
  modal.append(add('quickCaptureStatus'), add('quickCaptureResults'));
  const manual = add('quickCaptureManual', 'button'); modal.append(manual);
  const tabs = new Map(categories.map(category => [category, new Element('button')]));
  const forms = {
    movies: ['addMovieForm', 'movieForm', 'movieTitle', 'movieWatched', 'movieDirector', 'movieYear'],
    'tv-shows': ['addTVShowForm', 'tvForm', 'tvTitle', 'tvWatched', 'tvYear', 'tvSeasons'],
    anime: ['addAnimeForm', 'animeForm', 'animeTitle', 'animeWatched', 'animeYear', 'animeSeasons', 'animeEpisodes'],
    'video-games': ['addVideoGameForm', 'videoGameForm', 'videoGameTitle', 'videoGamePlayed', 'videoGameGenres'],
    music: ['addMusicForm', 'musicForm', 'musicTitle', 'musicListened', 'musicArtist', 'musicYear', 'musicGenre'],
    books: ['addBookForm', 'bookForm', 'bookTitle', 'bookRead', 'bookAuthor', 'bookYear', 'bookGenre'],
  };
  for (const [formId, contentPrefix, titleId, checkedId, ...fields] of Object.values(forms)) {
    const form = add(formId, 'form');
    form.elements = [titleId, checkedId, ...fields].map(id => add(id, 'input'));
    get(checkedId).type = 'checkbox';
    form.reset = () => { form.resets = (form.resets || 0) + 1; form.elements.forEach(field => { field.value = ''; field.checked = false; }); };
    const content = add(contentPrefix + 'Content');
    content.hidden = true;
    content.className = 'collapsible-content';
    add(contentPrefix + 'Icon');
    const toggle = add(contentPrefix + 'Toggle', 'button');
    toggle.dataset.toggleCollapsible = contentPrefix;
    toggle.setAttribute('aria-expanded', 'false');
    document.body.append(toggle);
  }
  const requests = [], timers = new Map(), opened = [], confirmations = [];
  let timerId = 0, now = 0, confirmResult = true;
  const setTimeout = (callback, delay = 0) => { const id = ++timerId; timers.set(id, { callback, at: now + delay }); return id; };
  const clearTimeout = id => timers.delete(id);
  const context = vm.createContext({
    document, HTMLElement: Element, AbortController, URLSearchParams, API_BASE: '',
    setTimeout, clearTimeout,
    window: {
      setTimeout, clearTimeout,
      confirm(message) { confirmations.push(message); return confirmResult; },
    },
    closeLibrarySearch() {}, getTabButton: category => tabs.get(category),
    switchTab: category => opened.push(category),
    fetch(url, options) {
      // Deliberately ignore abort: stale response guards must also handle a response
      // that arrives after cancellation or whose JSON decoding is already in flight.
      const pending = deferred(); requests.push({ url, options, category: provider(url), ...pending });
      return pending.promise;
    },
  });
  const toggleStart = source.indexOf('window.toggleCollapsible =');
  vm.runInContext(source.slice(toggleStart, source.indexOf('// Account Management Functions', toggleStart)), context);
  context.toggleCollapsible = context.window.toggleCollapsible;
  const addStart = source.indexOf('function openLaunchpadAddItem(');
  vm.runInContext(source.slice(addStart, source.indexOf('function openLaunchpadInsights(', addStart)), context);
  vm.runInContext(source.slice(source.indexOf('const QUICK_CAPTURE_CATEGORY_ORDER'), source.indexOf('function showImagePopup(')), context);
  return {
    context, get, document, requests, timers, opened, confirmations, submit, manual,
    search(value = 'Dune') {
      query.value = value;
      return context.searchQuickCapture({ preventDefault() {}, target: searchForm });
    },
    input(value) { query.value = value; context.handleQuickCaptureQueryInput(); },
    request(category, attempt = 0) { return requests.filter(request => request.category === category)[attempt]; },
    results() { return get('quickCaptureResults').querySelectorAll('[data-action="choose-quick-capture-result"]'); },
    retries() { return get('quickCaptureResults').querySelectorAll('[data-action="retry-quick-capture-source"]').filter(button => !button.hidden); },
    respond(category, title, attempt = 0) { this.request(category, attempt).resolve(ok(payload(category, title))); },
    confirm(value) { confirmResult = value; },
    advance(milliseconds) {
      now += milliseconds;
      const due = [...timers].filter(([, timer]) => timer.at <= now).sort((a, b) => a[1].at - b[1].at);
      for (const [id, timer] of due) if (timers.delete(id)) timer.callback();
    },
  };
}

for (const category of categories) {
  test(`Quick Capture opens the initially hidden ${category} form and focuses its selected title`, () => {
    const s = setup();
    const destination = s.context.prepareQuickCaptureDestination(category, 'My selected title');
    const content = s.get(destination.form + 'Content');
    assert.equal(content.hidden, false);
    assert.equal(content.classList.contains('expanded'), true);
    assert.equal(content.style.display, 'block');
    assert.equal(s.get(destination.form + 'Toggle').getAttribute('aria-expanded'), 'true');
    assert.deepEqual(s.opened, [category]);
    assert.equal(destination.titleInput.value, 'My selected title');
    s.advance(0);
    assert.equal(s.document.activeElement, destination.titleInput);
    assert.equal(s.requests.length, 0, 'handoff never saves a library item');
  });
}

test('Quick Capture keeps an already expanded form open during title handoff', () => {
  const s = setup();
  const content = s.get('bookFormContent');
  content.hidden = false;
  content.style.display = 'block';
  content.classList.add('expanded');
  s.get('bookFormToggle').setAttribute('aria-expanded', 'true');
  const destination = s.context.prepareQuickCaptureDestination('books', 'A selected book');
  assert.equal(content.hidden, false);
  assert.equal(content.classList.contains('expanded'), true);
  assert.equal(s.get('bookFormToggle').getAttribute('aria-expanded'), 'true');
  assert.deepEqual(s.opened, ['books']);
  s.advance(300);
  assert.equal(content.hidden, false);
  assert.equal(s.document.activeElement, destination.titleInput);
});

test('a fast source becomes usable while other sources are still loading', async () => {
  const s = setup();
  const search = s.search('Dune');
  assert.equal(s.requests.length, 6);
  assert.equal(s.submit.disabled, false, 'a different query can be submitted while sources are pending');
  assert.equal(s.manual.disabled, false);
  s.respond('books', 'Dune novel');
  await settle();
  assert.equal(s.results().length, 1);
  assert.match(s.results()[0].textContent, /Dune novel/);
  assert.match(s.get('quickCaptureStatus').textContent, /searching|loading|remaining/i);
  assert.equal(s.requests.every(request => !request.options.method || request.options.method === 'GET'), true);
  for (const category of categories.filter(category => category !== 'books')) s.respond(category, null);
  await search;
  assert.match(s.get('quickCaptureStatus').textContent, /1 match/);
  assert.equal(s.timers.size, 0, 'finished sources release their timeout timers');
});

test('later sources preserve the identity, focus, and action index of an already visible result', async () => {
  const s = setup();
  const search = s.search();
  s.respond('books', 'Dune novel');
  await settle();
  const bookButton = s.results()[0];
  const bookIndex = bookButton.dataset.quickResultIndex;
  bookButton.focus();
  s.respond('movies', 'Dune film');
  s.respond('anime', 'Dune animation');
  await settle();
  assert.ok(s.results().includes(bookButton));
  assert.equal(bookButton.dataset.quickResultIndex, bookIndex);
  assert.equal(s.document.activeElement, bookButton);
  s.get('quickCaptureIntent').value = 'completed';
  s.context.applyQuickCaptureResult(Number(bookIndex));
  assert.equal(s.get('bookTitle').value, 'Dune novel');
  assert.equal(s.get('bookAuthor').value, 'An Author');
  assert.equal(s.get('bookRead').checked, true);
  assert.deepEqual(s.opened, ['books']);
  assert.equal(s.get('quickCaptureModal').style.display, 'none');
  assert.equal(s.requests.length, 6, 'choosing a match only prefills the existing form');
  for (const category of ['tv-shows', 'video-games', 'music']) s.respond(category, null);
  await search;
});

test('per-source timeouts keep successful matches and retry only the chosen failed source', async () => {
  const s = setup();
  const search = s.search();
  s.respond('movies', 'Dune film');
  for (const category of ['tv-shows', 'anime', 'video-games', 'music']) s.respond(category, null);
  await settle();
  const movieButton = s.results()[0];
  s.advance(15000);
  await search;
  assert.equal(s.request('books').options.signal.aborted, true);
  assert.equal(s.results()[0], movieButton);
  assert.equal(s.retries().length, 1);
  assert.match(s.get('quickCaptureResults').textContent, /timed out|too long/i);
  const retry = s.context.retryQuickCaptureCategory('books');
  s.context.retryQuickCaptureCategory('books');
  assert.equal(s.requests.length, 7, 'repeated clicks cannot duplicate an in-flight retry');
  assert.equal(s.requests.at(-1).category, 'books');
  assert.equal(s.retries()[0].disabled, true);
  s.respond('books', 'Recovered book', 1);
  await retry;
  assert.ok(s.results().includes(movieButton));
  assert.equal(s.retries().length, 0);
  assert.equal(s.results().length, 2);
  s.respond('books', 'Late timed-out book', 0);
  await settle();
  assert.doesNotMatch(s.get('quickCaptureResults').textContent, /Late timed-out/);
});

test('the source deadline also covers a response body that never finishes decoding', async () => {
  const s = setup();
  s.context.selectQuickCaptureCategory('books');
  const search = s.search();
  const decoded = deferred();
  s.request('books').resolve({ ok: true, status: 200, json: () => decoded.promise });
  await settle();
  s.advance(15000);
  await search;
  assert.equal(s.retries().length, 1);
  assert.match(s.get('quickCaptureResults').textContent, /too long/i);
  decoded.resolve(payload('books', 'Late decoded result'));
  await settle();
  assert.equal(s.results().length, 0);
  assert.equal(s.retries().length, 1);
});

test('network, JSON, HTTP, and provider errors each offer a retry without erasing successes', async t => {
  const failures = {
    network: request => request.reject(new Error('Connection lost')),
    json: request => request.resolve({ ok: true, status: 200, json: async () => { throw new SyntaxError('Invalid JSON'); } }),
    http: request => request.resolve({ ok: false, status: 503, json: async () => ({ error: 'Unavailable' }) }),
    provider: request => request.resolve(ok({ Response: 'False', Error: 'Request limit reached!' })),
  };
  for (const [name, fail] of Object.entries(failures)) await t.test(name, async () => {
    const s = setup();
    const search = s.search();
    s.respond('books', 'Still available');
    for (const category of ['tv-shows', 'anime', 'video-games', 'music']) s.respond(category, null);
    fail(s.request('movies'));
    await search;
    assert.equal(s.results().length, 1);
    assert.match(s.results()[0].textContent, /Still available/);
    assert.equal(s.retries().length, 1);
    assert.match(s.get('quickCaptureStatus').textContent, /unavailable|retry|failed/i);
    assert.equal(s.submit.disabled, false);
  });
});

test('all-source failure leaves explicit recovery and manual entry available', async () => {
  const s = setup();
  const search = s.search();
  for (const request of s.requests) request.reject(new Error('Offline'));
  await search;
  assert.equal(s.retries().length, 6);
  assert.equal(s.results().length, 0);
  assert.equal(s.submit.disabled, false);
  assert.equal(s.manual.disabled, false);
  assert.match(s.get('quickCaptureStatus').textContent, /temporarily unavailable.*retry.*manual/i);
});

test('an OMDb not-found response is an empty search, not an unavailable source', async () => {
  const s = setup();
  s.context.selectQuickCaptureCategory('movies');
  const search = s.search('No known title');
  s.respond('movies', null);
  await search;
  assert.equal(s.results().length, 0);
  assert.equal(s.retries().length, 0);
  assert.match(s.get('quickCaptureStatus').textContent, /no (close )?matches/i);
});

test('duplicate submits share the pending search but a new query cancels and replaces it', async () => {
  const s = setup();
  s.context.selectQuickCaptureCategory('books');
  const older = s.search('Old query');
  s.search('Old query');
  assert.equal(s.requests.length, 1);
  const latest = s.search('New query');
  assert.equal(s.requests.length, 2);
  assert.equal(s.request('books', 0).options.signal.aborted, true);
  s.respond('books', 'New result', 1);
  await latest;
  s.respond('books', 'Old result', 0);
  await older;
  assert.equal(s.results().length, 1);
  assert.match(s.results()[0].textContent, /New result/);
  assert.doesNotMatch(s.get('quickCaptureStatus').textContent, /Old query/);
});

for (const action of ['input', 'category', 'close-and-reopen']) {
  test(`${action} invalidates a response whose JSON finishes after cancellation`, async () => {
    const s = setup();
    s.context.selectQuickCaptureCategory('books');
    const search = s.search('Old query');
    const decoded = deferred();
    s.request('books').resolve({ ok: true, status: 200, json: () => decoded.promise });
    await settle();
    if (action === 'input') s.input('Changed query');
    if (action === 'category') s.context.selectQuickCaptureCategory('movies');
    if (action === 'close-and-reopen') { s.context.closeQuickCapture(); s.context.openQuickCapture(); }
    const status = s.get('quickCaptureStatus').textContent;
    assert.equal(s.request('books').options.signal.aborted, true);
    decoded.resolve(payload('books', 'Stale decoded book'));
    await search;
    assert.equal(s.results().length, 0);
    assert.equal(s.get('quickCaptureStatus').textContent, status);
    assert.equal(s.submit.disabled, false);
    assert.equal([...s.timers.values()].some(timer => timer.at === 15000), false, 'cancelled requests release their source deadlines');
  });
}

test('editing the query removes actionable old results before the next search', async () => {
  const s = setup();
  const search = s.search();
  s.respond('movies', 'Old film');
  await settle();
  const oldIndex = Number(s.results()[0].dataset.quickResultIndex);
  s.input('A different query');
  assert.equal(s.results().length, 0);
  s.context.applyQuickCaptureResult(oldIndex);
  assert.equal(s.opened.length, 0, 'an old result index cannot populate a form after the query changes');
  for (const category of categories.filter(category => category !== 'movies')) s.respond(category, 'Stale result');
  await search;
  assert.equal(s.results().length, 0);
});

test('changing category cancels pending sources and the next search uses only the selected source', async () => {
  const s = setup();
  const search = s.search();
  s.context.selectQuickCaptureCategory('anime');
  assert.equal(s.requests.every(request => request.options.signal.aborted), true);
  const next = s.search('Frieren');
  assert.equal(s.requests.length, 7);
  assert.equal(s.requests.at(-1).category, 'anime');
  s.respond('anime', 'Frieren', 1);
  await next;
  for (const category of categories) s.respond(category, 'Old result');
  await search;
  assert.equal(s.results().length, 1);
  assert.match(s.results()[0].textContent, /Frieren/);
});

test('manual entry remains available during a search and requires consent to replace a draft', async () => {
  const s = setup();
  s.context.selectQuickCaptureCategory('books');
  const search = s.search('A manual title');
  s.get('bookTitle').value = 'My unsaved draft';
  s.get('bookAuthor').value = 'My author';
  s.confirm(false);
  s.context.openQuickCaptureManual();
  assert.equal(s.get('bookTitle').value, 'My unsaved draft');
  assert.equal(s.get('bookAuthor').value, 'My author');
  assert.equal(s.get('quickCaptureModal').style.display, 'flex');
  assert.equal(s.opened.length, 0);
  assert.equal(s.request('books').options.signal.aborted, false);
  s.confirm(true);
  s.context.openQuickCaptureManual();
  assert.equal(s.get('bookTitle').value, 'A manual title');
  assert.equal(s.get('bookAuthor').value, '');
  assert.equal(s.get('bookRead').checked, false);
  assert.deepEqual(s.opened, ['books']);
  assert.equal(s.request('books').options.signal.aborted, true);
  assert.equal(s.requests.length, 1, 'manual entry does not create a library item');
  assert.equal(s.confirmations.length, 2);
  s.respond('books', 'Late metadata');
  await search;
  assert.equal(s.get('bookTitle').value, 'A manual title');
});

test('all-media manual entry asks for a shelf without cancelling the active search', async () => {
  const s = setup();
  const search = s.search();
  s.context.openQuickCaptureManual();
  assert.match(s.get('quickCaptureStatus').textContent, /choose.*before|choose.*media|choose.*shelf/i);
  assert.equal(s.opened.length, 0);
  assert.equal(s.requests.some(request => request.options.signal.aborted), false);
  for (const category of categories) s.respond(category, null);
  await search;
  assert.match(s.get('quickCaptureStatus').textContent, /choose.*before/i, 'later source completions retain manual-entry guidance');
});

test('choosing a metadata result cannot silently replace an unsaved form', async () => {
  const s = setup();
  s.context.selectQuickCaptureCategory('movies');
  const search = s.search();
  s.respond('movies', 'Dune film');
  await search;
  s.get('movieTitle').value = 'Draft film';
  s.get('movieYear').value = '1999';
  s.confirm(false);
  s.context.applyQuickCaptureResult(Number(s.results()[0].dataset.quickResultIndex));
  assert.equal(s.get('movieTitle').value, 'Draft film');
  assert.equal(s.get('movieYear').value, '1999');
  assert.equal(s.get('quickCaptureModal').style.display, 'flex');
  assert.equal(s.opened.length, 0);
  assert.equal(s.requests.length, 1);
});

test('short, blank, and oversized queries do not start provider lookups', async () => {
  const s = setup();
  await s.search(' ');
  await s.search('a');
  await s.search('a'.repeat(201));
  assert.equal(s.requests.length, 0);
});
