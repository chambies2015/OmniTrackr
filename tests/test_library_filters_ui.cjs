// Run with: node --test tests/test_library_filters_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const authSource = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const defaults = { completion: 'all', unrated: false, hasProgress: false };
const config = {
  movies: ['movieTable', 'movieSort', 'movieSearch', 'Movies'],
  'tv-shows': ['tvShowTable', 'tvSort', 'tvSearch', 'TVShows'],
  anime: ['animeTable', 'animeSort', 'animeSearch', 'Anime'],
  'video-games': ['videoGameTable', 'videoGameSort', 'videoGameSearch', 'VideoGames'],
  music: ['musicTable', 'musicSort', 'musicSearch', 'Music'],
  books: ['bookTable', 'bookSort', 'bookSearch', 'Books'],
};
const plain = value => JSON.parse(JSON.stringify(value));
const response = (items = [], total = items.length, offset = 0) => ({ ok: true, json: async () => ({ items, total, offset }) });
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }

function setup() {
  let context;
  const nodes = new Map(), requests = [], reloads = [], alerts = [], timers = [], rows = new Map();
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attributes = {};
      this.listeners = {}; this.value = ''; this.style = {}; this.hidden = false; this.disabled = false;
      this._text = ''; this.classes = new Set();
      this.classList = { add: name => this.classes.add(name), remove: name => this.classes.delete(name), contains: name => this.classes.has(name), toggle: (name, value) => value ? this.classes.add(name) : this.classes.delete(name) };
    }
    set id(value) { this._id = value; nodes.set(value, this); }
    get id() { return this._id; }
    get childElementCount() { return this.children.filter(child => typeof child !== 'string').length; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(child => typeof child === 'string' ? child : child.textContent).join(''); }
    append(...children) { this.children.push(...children); for (const child of children) if (typeof child !== 'string') child.parent = this; }
    appendChild(child) { this.append(child); return child; }
    replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    getAttribute(key) { return this.attributes[key] ?? null; }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(event, callback) { this.listeners[event] = callback; }
    dispatch(event) { return this.listeners[event]?.({ target: this, currentTarget: this, preventDefault() {} }); }
    focus() { context.document.activeElement = this; }
    scrollIntoView() { this.scrolled = true; }
    after(child) { this.afterElement = child; }
    contains(node) { return node === this || this.children.some(child => typeof child !== 'string' && child.contains(node)); }
    querySelectorAll(selector) {
      return this.children.flatMap(child => {
        if (typeof child === 'string') return [];
        const matches = selector === 'button' ? child.tagName === 'BUTTON'
          : selector === 'input' ? child.tagName === 'INPUT'
          : selector === '[data-completion]' ? child.dataset.completion !== undefined
          : selector === '[data-library-filter]' ? child.dataset.libraryFilter !== undefined
          : selector.startsWith('.') ? (child.className || '').split(' ').includes(selector.slice(1)) : false;
        return [...(matches ? [child] : []), ...child.querySelectorAll(selector)];
      });
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  const node = (id, tag = 'div') => { const element = new Element(tag); element.id = id; return element; };
  for (const [category, [table, sort, search]] of Object.entries(config)) {
    node(table); node(`${table}Filters`); node(sort, 'select').value = 'title-asc'; node(search, 'input'); node(`${category}-button`, 'button');
  }
  node('todaysPickReason'); node('todaysPickOpen', 'button');
  context = vm.createContext({
    URL, URLSearchParams, Date, console, isLocal: false, API_BASE: '', location: { origin: 'https://omnitrackr.test' },
    editingRowId: null, currentTab: 'movies', window: { addEventListener() {} },
    alert: message => alerts.push(message), setTimeout: callback => { timers.push(callback); return timers.length; },
    document: {
      getElementById: id => nodes.get(id) || null, createElement: tag => new Element(tag), activeElement: null,
      querySelectorAll: selector => selector === '.pick-focused' ? [...rows.values()].filter(row => row.classes.has('pick-focused')) : [],
      querySelector: selector => {
        const match = selector.match(/data-next-up-category="([a-z-]+)".*data-next-up-item-id="(\d+)"/);
        const row = match && rows.get(`${match[1]}:${match[2]}`);
        return row ? { closest: () => row } : null;
      },
    },
    getTabButton: category => nodes.get(`${category}-button`),
    authenticatedFetch: async url => { requests.push(new URL(url, 'https://omnitrackr.test')); return response([], 0, Number(requests.at(-1).searchParams.get('offset'))); },
    switchTab: async category => {
      context.currentTab = category;
      const [, sort, search] = config[category];
      const result = await context.fetchLibraryPage(`/${category}/?search=${encodeURIComponent(nodes.get(search).value)}&sort_by=title&order=asc`);
      if (result.ok) {
        const page = context.libraryPages.get(category);
        rows.set(`${category}:${page.focusId}`, new Element('tr'));
      }
    },
  });
  for (const [category, [, , , loader]] of Object.entries(config)) {
    context[`load${loader}`] = () => { reloads.push(category); };
    context[`isLoading${loader}`] = false;
  }
  vm.runInContext(source.slice(source.indexOf('const LIBRARY_SEARCH_SOURCES ='), source.indexOf('const posterFetchInProgress')), context);
  vm.runInContext('this.libraryPages = libraryPages; this.libraryFilters = libraryFilters;', context);
  vm.runInContext(source.slice(source.indexOf('async function openLibraryItem('), source.indexOf('function captureNextUpQueueFocus(')), context);
  return { context, nodes, requests, reloads, alerts, timers, rows, Element };
}

test('combined filters accompany server search and sort while pagination remains bounded', async () => {
  const s = setup();
  s.nodes.get('bookSearch').value = 'distant stars';
  s.context.applyLibraryFilters('books', { completion: 'finished', unrated: true, hasProgress: true });
  await s.context.fetchLibraryPage('/books/?search=distant+stars&sort_by=year&order=desc');
  const params = s.requests.at(-1).searchParams;
  assert.equal(params.get('search'), 'distant stars');
  assert.equal(params.get('sort_by'), 'year');
  assert.equal(params.get('order'), 'desc');
  assert.equal(params.get('completion'), 'finished');
  assert.equal(params.get('unrated'), 'true');
  assert.equal(params.get('has_progress'), 'true');
  assert.equal(params.get('limit'), '50');
  assert.equal(params.get('offset'), '0');
  s.context.libraryPages.get('books').offset = 50;
  await s.context.fetchLibraryPage('/books/?search=distant+stars&sort_by=year&order=desc');
  assert.equal(s.requests.at(-1).searchParams.get('offset'), '50');
  assert.equal(s.requests.at(-1).searchParams.get('has_progress'), 'true');
  assert.deepEqual(plain(s.context.getLibraryFilters('movies')), defaults);
});

test('changing a filter resets page and exact-item focus while retaining browse history', async () => {
  const s = setup();
  await s.context.fetchLibraryPage('/books/');
  const previousKey = s.context.libraryPages.get('books').loadedKey;
  Object.assign(s.context.libraryPages.get('books'), { offset: 100, focusId: 42 });
  assert.equal(s.context.applyLibraryFilters('books', { completion: 'unfinished' }), true);
  const page = s.context.libraryPages.get('books');
  assert.equal(page.offset, 0);
  assert.equal(page.focusId, undefined);
  assert.equal(page.loadedKey, previousKey);
  assert.deepEqual(s.reloads, ['books']);
  await s.context.fetchLibraryPage('/books/');
  assert.equal(s.requests.at(-1).searchParams.has('focus_id'), false);
  assert.equal(s.context.libraryPages.get('books').browseOnly, true);
});

test('clear search and filters preserves sorting and other category choices', () => {
  const s = setup();
  s.context.applyLibraryFilters('books', { completion: 'finished', unrated: true, hasProgress: true });
  s.context.applyLibraryFilters('movies', { completion: 'unfinished', unrated: true });
  s.nodes.get('bookSearch').value = 'hidden result';
  s.nodes.get('bookSort').value = 'rating-desc';
  s.context.applyLibraryFilters('books', defaults, { clearSearch: true });
  assert.equal(s.nodes.get('bookSearch').value, '');
  assert.equal(s.nodes.get('bookSort').value, 'rating-desc');
  assert.deepEqual(plain(s.context.getLibraryFilters('books')), defaults);
  assert.deepEqual(plain(s.context.getLibraryFilters('movies')), { completion: 'unfinished', unrated: true, hasProgress: false });
});

test('filter and reset attempts preserve an unsaved inline edit without issuing reads', () => {
  const s = setup();
  s.context.applyLibraryFilters('books', { completion: 'finished', unrated: true });
  s.nodes.get('bookSearch').value = 'my title';
  const page = s.context.libraryPages.get('books');
  const controls = s.nodes.get('bookTableFilters').children.slice();
  s.reloads.length = 0;
  s.context.editingRowId = 42;
  assert.equal(s.context.applyLibraryFilters('books', defaults, { clearSearch: true }), false);
  assert.deepEqual(plain(s.context.getLibraryFilters('books')), { completion: 'finished', unrated: true, hasProgress: false });
  assert.equal(s.context.libraryPages.get('books'), page);
  assert.deepEqual(s.nodes.get('bookTableFilters').children, controls);
  assert.equal(s.nodes.get('bookSearch').value, 'my title');
  assert.equal(s.reloads.length, 0);
  assert.equal(s.requests.length, 0);
  assert.match(s.alerts[0], /save or cancel/i);
});

test('a response for superseded filters cannot replace the new results', async () => {
  const s = setup(), pending = deferred();
  s.context.authenticatedFetch = () => pending.promise;
  const oldLoad = s.context.fetchLibraryPage('/books/');
  s.context.applyLibraryFilters('books', { unrated: true });
  pending.resolve(response([{ id: 1, rating: 9 }], 100));
  assert.equal((await oldLoad).ok, false);
  assert.equal(s.context.libraryPages.get('books').total, 0);
  s.timers.forEach(callback => callback());
  assert.ok(s.reloads.length >= 1);
});

test('pending library reads disable stale row actions and restore them after success or failure', async () => {
  for (const succeeds of [true, false]) {
    const s = setup(), pending = deferred();
    const table = s.nodes.get('bookTable');
    const row = new s.Element('tr');
    const edit = new s.Element('button'); edit.textContent = 'Edit';
    const remove = new s.Element('button'); remove.textContent = 'Delete';
    row.append(edit, remove); table.appendChild(row);
    s.context.authenticatedFetch = () => pending.promise;
    const loading = s.context.fetchLibraryPage('/books/');
    assert.equal(table.getAttribute('aria-busy'), 'true');
    assert.equal(edit.disabled, true);
    assert.equal(remove.disabled, true);
    pending.resolve(succeeds ? response([{ id: 42 }], 1) : { ok: false });
    assert.equal((await loading).ok, succeeds);
    assert.equal(table.getAttribute('aria-busy'), 'false');
    assert.equal(edit.disabled, false);
    assert.equal(remove.disabled, false);
    if (!succeeds) assert.match(s.nodes.get('bookTableFilterStatus').textContent, /Could not load/);
  }
});

test('pager updates do not unlock other rows while an inline edit remains active', () => {
  const s = setup(), table = s.nodes.get('bookTable');
  const save = new s.Element('button');
  const otherEdit = new s.Element('button'); otherEdit.disabled = true;
  table.append(save, otherEdit);
  s.context.editingRowId = 42;
  s.context.renderLibraryPager('books', { offset: 0, total: 2 });
  assert.equal(save.disabled, false);
  assert.equal(otherEdit.disabled, true);
});

test('rapidly returning to the same filter still rejects a response tied to an obsolete page', async () => {
  const s = setup(), pending = deferred();
  s.context.authenticatedFetch = () => pending.promise;
  const oldLoad = s.context.fetchLibraryPage('/books/');
  s.context.applyLibraryFilters('books', { unrated: true });
  s.context.applyLibraryFilters('books', { unrated: false });
  pending.resolve(response([{ id: 1 }], 91));
  assert.equal((await oldLoad).ok, false);
  assert.equal(s.context.libraryPages.get('books').total, 0);
});

test('opening an exact item clears only that category filters and keeps focus priority in the actual request', async () => {
  const s = setup();
  s.context.applyLibraryFilters('books', { completion: 'finished', unrated: true, hasProgress: true });
  s.context.applyLibraryFilters('movies', { completion: 'unfinished', unrated: true });
  assert.equal(await s.context.openLibraryItem({ category: 'books', id: 42, title: 'A saved title' }), true);
  assert.deepEqual(plain(s.context.getLibraryFilters('books')), defaults);
  assert.equal(s.context.getLibraryFilters('movies').unrated, true);
  const params = s.requests.at(-1).searchParams;
  assert.equal(params.get('focus_id'), '42');
  assert.equal(params.get('search'), 'A saved title');
  assert.ok(!params.has('unrated') || params.get('unrated') === 'false');
  assert.ok(!params.has('has_progress') || params.get('has_progress') === 'false');
  assert.ok(!params.has('completion') || params.get('completion') === 'all');
  assert.equal(s.rows.get('books:42').scrolled, true);
});

test('auth reset clears all session filters and rejects a pending response without restarting old reads', async () => {
  const s = setup(), pending = deferred();
  s.context.applyLibraryFilters('books', { hasProgress: true });
  s.context.applyLibraryFilters('movies', { unrated: true });
  s.context.authenticatedFetch = () => pending.promise;
  const oldLoad = s.context.fetchLibraryPage('/books/');
  s.context.resetLibraryBrowsing();
  assert.equal(s.context.libraryFilters.size, 0);
  assert.equal(s.context.libraryPages.size, 0);
  assert.deepEqual(plain(s.context.getLibraryFilters('books')), defaults);
  s.reloads.length = 0;
  pending.resolve(response([{ id: 42 }], 1));
  assert.equal((await oldLoad).ok, false);
  s.timers.forEach(callback => callback());
  assert.equal(s.reloads.length, 0);
});

test('completion controls expose their selected state and only supported categories offer saved progress', () => {
  const s = setup();
  for (const [category, [table]] of Object.entries(config)) {
    s.context.renderLibraryFilters(category);
    const host = s.nodes.get(`${table}Filters`);
    const buttons = host.querySelectorAll('[data-completion]');
    assert.equal(buttons.length, 3, category);
    assert.equal(buttons.filter(button => button.getAttribute('aria-pressed') === 'true').length, 1);
    assert.equal(buttons.find(button => button.dataset.completion === 'all').getAttribute('aria-pressed'), 'true');
    const progress = host.querySelectorAll('[data-library-filter]').find(input => input.dataset.libraryFilter === 'hasProgress');
    assert.equal(!!progress, ['tv-shows', 'anime', 'books'].includes(category), category);
    buttons.find(button => button.dataset.completion === 'finished').dispatch('click');
    assert.equal(s.context.getLibraryFilters(category).completion, 'finished');
    assert.equal(buttons.find(button => button.dataset.completion === 'finished').getAttribute('aria-pressed'), 'true');
    assert.equal(buttons.find(button => button.dataset.completion === 'all').getAttribute('aria-pressed'), 'false');
    assert.equal(host.querySelectorAll('[data-completion]').length, 3, 'rerender does not duplicate controls');
  }
});

test('a checkbox change during an inline edit is restored to its saved filter state', () => {
  const s = setup();
  s.context.renderLibraryFilters('books');
  const unrated = s.nodes.get('bookTableFilters').querySelectorAll('[data-library-filter]').find(input => input.dataset.libraryFilter === 'unrated');
  s.context.editingRowId = 42;
  unrated.checked = true;
  unrated.dispatch('change');
  assert.equal(unrated.checked, false);
  assert.equal(s.context.getLibraryFilters('books').unrated, false);
  assert.equal(s.reloads.length, 0);
  assert.match(s.alerts[0], /save or cancel/i);
});

test('result feedback distinguishes matched totals, empty filters, an empty library, and failed reads', async () => {
  const s = setup();
  s.context.applyLibraryFilters('books', { unrated: true });
  s.context.authenticatedFetch = async () => response([{ id: 42 }], 75);
  await s.context.fetchLibraryPage('/books/');
  assert.match(s.nodes.get('bookTableFilterStatus').textContent, /75 titles match/);
  assert.match(s.nodes.get('bookTablePager').textContent, /1–50 of 75/);
  s.context.authenticatedFetch = async () => response();
  await s.context.fetchLibraryPage('/books/');
  assert.match(s.nodes.get('bookTableFilterStatus').textContent, /No titles match.*clear your filters/);
  s.context.applyLibraryFilters('books', defaults, { clearSearch: true });
  await s.context.fetchLibraryPage('/books/');
  assert.match(s.nodes.get('bookTableFilterStatus').textContent, /first title.*Add anything/);
  s.context.authenticatedFetch = async () => ({ ok: false });
  await s.context.fetchLibraryPage('/books/');
  assert.match(s.nodes.get('bookTableFilterStatus').textContent, /Could not load titles/);
  assert.doesNotMatch(s.nodes.get('bookTableFilterStatus').textContent, /first title/);
});

test('the actual clearAuth path clears private browsing state without storage events', () => {
  const s = setup(), removed = [];
  s.context.applyLibraryFilters('books', { completion: 'finished', hasProgress: true });
  s.nodes.get('bookSearch').value = 'private search';
  Object.assign(s.context, {
    TOKEN_KEY: 'omnitrackr_token', USER_KEY: 'omnitrackr_user', RETURN_PROMPT_KEY: 'return-prompt',
    localStorage: { removeItem: key => removed.push(key) }, sessionStorage: { removeItem() {} },
    clearDiscoverAuthReturn() {}, clearDemoStartIntent() {},
  });
  vm.runInContext(authSource.slice(authSource.indexOf('function clearAuth('), authSource.indexOf('function isAuthenticated(')), s.context);
  s.context.clearAuth();
  assert.deepEqual(removed, ['omnitrackr_token', 'omnitrackr_user']);
  assert.equal(s.context.libraryFilters.size, 0);
  assert.equal(s.context.libraryPages.size, 0);
  assert.equal(s.nodes.get('bookSearch').value, '');
  assert.equal(s.nodes.get('bookSort').value, '');
  assert.equal(s.nodes.get('bookTableFilters').querySelectorAll('[data-library-filter]').every(input => !input.checked), true);
});
