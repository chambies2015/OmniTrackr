// Run with: node --test tests/test_review_navigation_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function setup(url = 'https://omnitrackr.xyz/?library_category=books&library_item=42', options = {}) {
  const elements = new Map();
  const listeners = new Map();
  const windowListeners = new Map();
  const requests = [];
  const rows = new Map();
  const tabs = new Map();
  const loads = [];
  const alerts = [];
  function element(id) {
    const classes = new Set();
    const el = {
      id, style: {}, value: '', hidden: false, textContent: '',
      classList: { add: value => classes.add(value), remove: value => classes.delete(value), contains: value => classes.has(value) },
      focus() { this.focused = true; },
      scrollIntoView() { this.scrollCount = (this.scrollCount || 0) + 1; },
    };
    elements.set(id, el);
    return el;
  }
  const status = element('libraryNavigationStatus'); status.hidden = true;
  element('todaysPickOpen'); element('todaysPickReason');
  const config = {
    movies: ['movieTable', 'movieSort', 'movieSearch'],
    'tv-shows': ['tvShowTable', 'tvSort', 'tvSearch'],
    anime: ['animeTable', 'animeSort', 'animeSearch'],
    'video-games': ['videoGameTable', 'videoGameSort', 'videoGameSearch'],
    music: ['musicTable', 'musicSort', 'musicSearch'],
    books: ['bookTable', 'bookSort', 'bookSearch'],
  };
  for (const [tab, [table, sort, search]] of Object.entries(config)) {
    element(table); element(sort).value = 'title-asc'; element(search).value = 'existing filter';
    tabs.set(tab, element(`${tab}-tab`));
    if (options.hiddenCategory === tab) tabs.get(tab).style.display = 'none';
  }
  const history = {
    state: { preserve: 'state' }, replacements: [],
    replaceState(state, unused, value) {
      this.replacements.push({ state, value });
      context.window.location.href = new URL(value, context.window.location.href).href;
    },
  };
  const context = vm.createContext({
    URL, URLSearchParams, API_BASE: '', Date, setTimeout,
    currentTab: 'movies', editingRowId: options.editingRowId ?? null,
    isLoadingMovies: false, isLoadingTVShows: false, isLoadingAnime: false,
    isLoadingVideoGames: false, isLoadingMusic: false, isLoadingBooks: false,
    libraryPages: new Map(),
    dashboardStartupLayoutReady: options.layoutReady || Promise.resolve(),
    dashboardTabVisibilityReady: options.visibilityReady || Promise.resolve(),
    document: {
      getElementById: id => elements.get(id) || null,
      querySelector: selector => {
        const match = selector.match(/data-next-up-category="([a-z-]+)".*data-next-up-item-id="(\d+)"/);
        const row = match && rows.get(`${match[1]}:${match[2]}`);
        return row ? { closest: () => row } : null;
      },
      querySelectorAll: selector => selector === '.pick-focused'
        ? Array.from(rows.values()).filter(row => row.classList.contains('pick-focused')) : [],
      addEventListener: (name, fn) => listeners.set(name, fn),
      removeEventListener: (name, fn) => { if (listeners.get(name) === fn) listeners.delete(name); },
    },
    window: {
      location: { href: url }, history,
      addEventListener: (name, fn) => windowListeners.set(name, fn),
      removeEventListener: (name, fn) => { if (windowListeners.get(name) === fn) windowListeners.delete(name); },
    },
    hasStoredAuth: () => options.authenticated !== false,
    getTabButton: tab => tabs.get(tab),
    libraryPageConfig: tab => config[tab],
    alert: message => alerts.push(message),
    authenticatedFetch: async (requestUrl, requestOptions) => {
      requests.push({ url: requestUrl, options: requestOptions });
      return options.response || { ok: true, json: async () => options.item || { id: 42, title: 'My saved title' } };
    },
    switchTab: async tab => {
      context.currentTab = tab;
      loads.push(tab);
      if (options.listReady) await options.listReady;
      if (options.missingRow) return;
      const id = context.libraryPages.get(tab)?.focusId;
      rows.set(`${tab}:${id}`, element(`row-${tab}-${id}`));
    },
    openCollectionFromLocation: () => { context.collectionCalls = (context.collectionCalls || 0) + 1; return true; },
  });
  vm.runInContext(source.slice(source.indexOf('const LIBRARY_SEARCH_SOURCES ='), source.indexOf('let librarySearchIndex =')), context);
  vm.runInContext(source.slice(source.indexOf('function consumeLibraryNavigationTarget('), source.indexOf('async function openCollectionFromLocation(')), context);
  vm.runInContext(source.slice(source.indexOf('async function openLibraryItem('), source.indexOf('function renderNextUpQueue(')), context);
  return { context, requests, elements, listeners, windowListeners, history, rows, tabs, loads, alerts, options, status };
}

test('all six categories open the exact owner-scoped item and consume identifiers while preserving unrelated URL state', async () => {
  for (const category of ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']) {
    const s = setup(`https://omnitrackr.xyz/?source=review&library_category=${category}&library_item=42&keep=yes#library`);
    assert.equal(await s.context.openDashboardTargetFromLocation(), true);
    assert.deepEqual(s.requests, [{ url: `/library/item/${category}/42`, options: undefined }]);
    assert.deepEqual(s.loads, [category]);
    assert.equal(s.context.libraryPages.get(category).focusId, 42);
    const row = s.rows.get(`${category}:42`);
    assert.equal(row.focused, true);
    assert.equal(row.scrollCount, 1);
    assert.equal(row.tabIndex, -1);
    assert.match(s.status.textContent, /Opened “My saved title”/);
    assert.equal(s.history.replacements[0].value, '/?source=review&keep=yes#library');
    assert.equal(s.history.replacements[0].state, s.history.state);
    assert.equal(s.listeners.size + s.windowListeners.size, 0);
    assert.equal(await s.context.openLibraryItemFromLocation(), false);
    assert.equal(s.requests.length, 1);
    assert.match(s.status.textContent, /Opened/);
  }
});

test('malformed categories, missing identifiers, duplicates, and invalid PostgreSQL IDs never fetch or change filters', async () => {
  const queries = [
    'library_category=books', 'library_item=42', 'library_category=book&library_item=42',
    'library_category=movies&library_category=books&library_item=42',
    'library_category=books&library_item=42&library_item=43',
    'library_category=//evil.example&library_item=42', 'library_category=books%2F..%2Fmovies&library_item=42',
    ...['', '0', '-1', '1.5', '1e2', '01', '%2B2', '2147483648', '9007199254740993', '42%0A', '42%00', 'https://evil.example'].map(id => `library_category=books&library_item=${id}`),
  ];
  for (const query of queries) {
    const s = setup(`https://omnitrackr.xyz/?keep=yes&${query}#anchor`);
    assert.equal(await s.context.openDashboardTargetFromLocation(), false, query);
    assert.equal(s.requests.length + s.loads.length, 0, query);
    assert.equal(s.elements.get('bookSearch').value, 'existing filter', query);
    assert.equal(s.history.replacements[0].value, '/?keep=yes#anchor', query);
    assert.match(s.status.textContent, /invalid/, query);
  }
});

test('largest supported ID resolves and ambiguous collection/item handoffs are both consumed without a race', async () => {
  const s = setup('https://omnitrackr.xyz/?library_category=books&library_item=2147483647', { item: { id: 2147483647, title: 'Last supported ID' } });
  assert.equal(await s.context.openDashboardTargetFromLocation(), true);
  assert.equal(s.requests[0].url, '/library/item/books/2147483647');
  const mixed = setup('https://omnitrackr.xyz/?collection=8&library_category=books&library_item=42&keep=yes');
  assert.equal(await mixed.context.openDashboardTargetFromLocation(), false);
  assert.equal(mixed.requests.length + mixed.loads.length, 0);
  assert.equal(mixed.context.collectionCalls || 0, 0);
  assert.equal(mixed.context.window.location.href, 'https://omnitrackr.xyz/?keep=yes');
  assert.match(mixed.status.textContent, /conflicting/);
  const collection = setup('https://omnitrackr.xyz/?collection=8');
  assert.equal(await collection.context.openDashboardTargetFromLocation(), true);
  assert.equal(collection.context.collectionCalls, 1);
});

test('anonymous navigation leaves the target untouched and cannot send a request', async () => {
  const s = setup(undefined, { authenticated: false });
  assert.equal(await s.context.openDashboardTargetFromLocation(), false);
  assert.equal(s.history.replacements.length + s.requests.length, 0);
});

test('missing, foreign, malformed, and failed owner responses have clear feedback without opening another item', async () => {
  for (const response of [
    { ok: false, status: 404 }, { ok: false, status: 500 },
    { ok: true, json: async () => ({ id: 7, title: 'Other title' }) },
    { ok: true, json: async () => ({ id: 42, title: null }) },
    { ok: true, json: async () => { throw new Error('Invalid JSON'); } },
  ]) {
    const s = setup(undefined, { response });
    assert.equal(await s.context.openLibraryItemFromLocation(), false);
    assert.equal(s.loads.length, 0);
    assert.match(s.status.textContent, /unavailable|Could not open/);
    assert.equal(s.listeners.size + s.windowListeners.size, 0);
  }
});

test('visibility readiness prevents opening hidden categories before settings arrive', async () => {
  const ready = deferred();
  const s = setup(undefined, { visibilityReady: ready.promise });
  const navigation = s.context.openLibraryItemFromLocation();
  await settle();
  assert.equal(s.requests.length, 0);
  s.tabs.get('books').style.display = 'none';
  ready.resolve();
  assert.equal(await navigation, false);
  assert.equal(s.loads.length + s.requests.length, 0);
  assert.match(s.status.textContent, /Enable this media category/);
});

test('an existing edit is preserved without fetching or altering the library', async () => {
  const s = setup(undefined, { editingRowId: 7 });
  assert.equal(await s.context.openLibraryItemFromLocation(), false);
  assert.equal(s.requests.length + s.loads.length, 0);
  assert.equal(s.context.editingRowId, 7);
  assert.equal(s.elements.get('bookSearch').value, 'existing filter');
  assert.match(s.status.textContent, /Save or cancel your current edit/);
});

test('interaction, navigation, edits, and logout during a delayed lookup prevent late filter changes and focus', async () => {
  for (const action of ['pointerdown', 'keydown', 'wheel', 'touchstart', 'popstate', 'hashchange', 'tab', 'edit', 'logout']) {
    const response = deferred();
    const s = setup();
    s.context.authenticatedFetch = () => response.promise;
    const navigation = s.context.openLibraryItemFromLocation();
    await settle();
    if (action === 'tab') s.context.currentTab = 'music';
    else if (action === 'edit') s.context.editingRowId = 7;
    else if (action === 'logout') s.options.authenticated = false;
    else (s.listeners.get(action) || s.windowListeners.get(action))();
    response.resolve({ ok: true, json: async () => ({ id: 42, title: 'My saved title' }) });
    assert.equal(await navigation, false, action);
    assert.equal(s.loads.length, 0, action);
    assert.equal(s.elements.get('bookSearch').value, 'existing filter', action);
    assert.equal(s.status.hidden, true, action);
    assert.equal(s.listeners.size + s.windowListeners.size, 0, action);
  }
});

test('a late JSON response cannot replace a title after the user has moved on', async () => {
  const json = deferred();
  const s = setup(undefined, { response: { ok: true, json: () => json.promise } });
  const navigation = s.context.openLibraryItemFromLocation();
  await settle();
  s.listeners.get('keydown')();
  json.resolve({ id: 42, title: 'My saved title' });
  assert.equal(await navigation, false);
  assert.equal(s.loads.length, 0);
});

test('exact item renders while startup is pending but focuses only once after layout settles', async () => {
  const layout = deferred();
  const s = setup(undefined, { layoutReady: layout.promise });
  const navigation = s.context.openLibraryItemFromLocation();
  await settle();
  const row = s.rows.get('books:42');
  assert.ok(row);
  assert.equal(row.focused, undefined);
  layout.resolve();
  assert.equal(await navigation, true);
  assert.equal(row.focused, true);
  assert.equal(row.scrollCount, 1);
});

test('navigation, edits, logout, and interaction during layout or list loading never steal focus', async () => {
  for (const phase of ['layout', 'list']) {
    for (const action of ['pointerdown', 'tab', 'edit', 'logout']) {
      const wait = deferred();
      const s = setup(undefined, phase === 'layout' ? { layoutReady: wait.promise } : { listReady: wait.promise });
      const navigation = s.context.openLibraryItemFromLocation();
      await settle();
      if (action === 'tab') s.context.currentTab = 'music';
      else if (action === 'edit') s.context.editingRowId = 7;
      else if (action === 'logout') s.options.authenticated = false;
      else s.listeners.get(action)();
      wait.resolve();
      assert.equal(await navigation, false, `${phase}:${action}`);
      assert.equal(s.rows.get('books:42')?.focused, undefined, `${phase}:${action}`);
      assert.equal(s.rows.get('books:42')?.scrollCount, undefined, `${phase}:${action}`);
      assert.equal(s.status.hidden, true, `${phase}:${action}`);
    }
  }
});

test('a busy library cancels navigation before changing an existing filter if the user starts editing', async () => {
  const s = setup();
  const wait = deferred();
  s.context.isLoadingBooks = true;
  s.context.setTimeout = callback => { wait.promise.then(callback); };
  const navigation = s.context.openLibraryItemFromLocation();
  await settle();
  s.context.editingRowId = 7;
  wait.resolve();
  assert.equal(await navigation, false);
  assert.equal(s.loads.length, 0);
  assert.equal(s.elements.get('bookSearch').value, 'existing filter');
});

test('an unavailable exact row reports failure instead of focusing a same-title substitute', async () => {
  const s = setup(undefined, { missingRow: true });
  assert.equal(await s.context.openLibraryItemFromLocation(), false);
  assert.match(s.status.textContent, /could not be located/);
  assert.equal(s.rows.size, 0);
});

test('ordinary explicit library navigation retains edit protection and works without new guard options', async () => {
  const s = setup();
  assert.equal(await s.context.openLibraryItem({ category: 'books', id: 42, title: 'My saved title' }), true);
  assert.equal(s.rows.get('books:42').focused, true);
  s.context.editingRowId = 7;
  assert.equal(await s.context.openLibraryItem({ category: 'movies', id: 2, title: 'Another title' }), false);
  assert.match(s.alerts[0], /Save or cancel/);
  assert.deepEqual(s.loads, ['books']);
});
