// Run with: node --test tests/test_collection_navigation_ui.cjs
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

function setup(url = 'https://omnitrackr.xyz/?collection=42', options = {}) {
  const elements = new Map();
  const listeners = new Map();
  const requests = [];
  function makeElement(tag = 'div') {
    return {
      tag, children: [], dataset: {}, style: {}, attributes: {}, textContent: '',
      classList: { add() {}, remove() {} },
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); },
      prepend(child) { this.children.unshift(child); },
      replaceChildren(...children) { this.children = children; this.textContent = ''; },
      setAttribute(name, value) { this.attributes[name] = value; },
      focus() { this.focused = true; },
      scrollIntoView() { this.scrolled = true; this.scrollCount = (this.scrollCount || 0) + 1; },
      set id(value) { this._id = value; elements.set(value, this); },
      get id() { return this._id; },
    };
  }
  ['collectionsList', 'collections-tab', 'movies-tab', 'books-tab', 'statsContent'].forEach(id => {
    const element = makeElement(); element.id = id;
  });
  const history = {
    state: { preserve: 'navigation state' }, replacements: [],
    replaceState(state, unused, value) {
      this.replacements.push({ state, value });
      context.window.location.href = new URL(value, context.window.location.href).href;
    },
  };
  const context = vm.createContext({
    URL, API_BASE: '', currentTab: 'movies',
    dashboardStartupLayoutReady: options.layoutReady || Promise.resolve(),
    document: {
      getElementById: id => elements.get(id) || null,
      createElement: makeElement,
      querySelectorAll: () => [],
      addEventListener: (name, handler) => listeners.set(name, handler),
      removeEventListener: (name, handler) => { if (listeners.get(name) === handler) listeners.delete(name); },
    },
    window: { location: { href: url }, history },
    hasStoredAuth: () => options.authenticated !== false,
    getTabButton: () => makeElement('button'),
    loadBooks: async () => {}, loadMovies: async () => {},
    loadModeratorInsights: () => {},
    authenticatedFetch: async (requestUrl, requestOptions) => {
      requests.push({ url: requestUrl, options: requestOptions });
      return options.response || {
        ok: true,
        json: async () => options.collections || [{ id: 42, name: 'Saved picks', items: [], is_public: false }],
      };
    },
  });
  vm.runInContext(source.slice(source.indexOf('function switchTab('), source.indexOf('function disableOtherRowButtons(')), context);
  vm.runInContext(source.slice(source.indexOf('let collectionsCache ='), source.indexOf('function moderatorNumber(')), context);
  return { context, elements, listeners, requests, history };
}

test('saved collection opens the existing panel and focuses its exact card using only an authenticated read', async () => {
  const { context, elements, requests, history, listeners } = setup('https://omnitrackr.xyz/?source=discover&collection=42&filter=quiet#saved');
  assert.equal(await context.openCollectionFromLocation(), true);
  assert.equal(context.currentTab, 'collections');
  assert.equal(elements.get('collection-42').focused, true);
  assert.equal(elements.get('collection-42').scrolled, true);
  assert.equal(elements.get('collection-42').tabIndex, -1);
  assert.deepEqual(requests, [{ url: '/collections/', options: undefined }]);
  assert.equal(history.replacements[0].value, '/?source=discover&filter=quiet#saved');
  assert.equal(history.replacements[0].state, history.state);
  assert.equal(listeners.size, 0);
  assert.equal(await context.openCollectionFromLocation(), false);
  assert.equal(requests.length, 1, 'a consumed target must not reopen on later initialization');
});

test('invalid, duplicate, and out-of-range IDs are consumed without fetching or switching panels', async () => {
  for (const value of ['', '0', '-1', '1.5', '1e2', '01', '+2', 'NaN', '2147483648', '9007199254740993', 'https://example.com/', '42&collection=43']) {
    const { context, requests, history } = setup(`https://omnitrackr.xyz/?keep=yes&collection=${value}#anchor`);
    assert.equal(await context.openCollectionFromLocation(), false, value);
    assert.equal(context.currentTab, 'movies', value);
    assert.equal(requests.length, 0, value);
    assert.equal(history.replacements[0].value, '/?keep=yes#anchor', value);
  }
});

test('largest supported positive ID resolves without numeric coercion', async () => {
  const { context, elements } = setup('https://omnitrackr.xyz/?collection=2147483647', {
    collections: [{ id: 2147483647, name: 'Last valid integer', items: [] }],
  });
  assert.equal(await context.openCollectionFromLocation(), true);
  assert.equal(elements.get('collection-2147483647').focused, true);
});

test('missing and other-account IDs never resolve outside the owner-filtered collection response', async () => {
  for (const ownCollections of [[], [{ id: 7, name: 'My private collection', items: [], is_public: false }]]) {
    const { context, elements, requests } = setup('https://omnitrackr.xyz/?collection=42', { collections: ownCollections });
    assert.equal(await context.openCollectionFromLocation(), false);
    const message = elements.get('collectionsList').children[0];
    assert.match(message.textContent, /unavailable in this account/);
    assert.equal(message.attributes.role, 'status');
    assert.equal(message.focused, true);
    assert.equal(elements.has('collection-42'), false);
    if (ownCollections.length) assert.equal(elements.get('collection-7').focused, undefined);
    assert.deepEqual(requests, [{ url: '/collections/', options: undefined }]);
  }
});

test('failed collection read retains the existing error state without opening a stale card', async () => {
  const { context, elements } = setup(undefined, { response: { ok: false } });
  assert.equal(await context.openCollectionFromLocation(), false);
  assert.match(elements.get('collectionsList').textContent, /Could not load collections/);
  assert.equal(elements.get('collectionsList').focused, true);
  assert.equal(elements.has('collection-42'), false);
});

test('an anonymous page cannot consume the target or request a collection', async () => {
  const { context, history, requests } = setup(undefined, { authenticated: false });
  assert.equal(await context.openCollectionFromLocation(), false);
  assert.equal(history.replacements.length, 0);
  assert.equal(requests.length, 0);
});

test('user interaction or a later tab choice prevents delayed navigation from stealing focus', async () => {
  for (const interaction of ['pointerdown', 'keydown', 'wheel', 'touchstart', 'tab']) {
    const { context, elements, listeners } = setup();
    let resolveResponse;
    context.authenticatedFetch = () => new Promise(resolve => { resolveResponse = resolve; });
    const navigation = context.openCollectionFromLocation();
    if (interaction === 'tab') await context.switchTab('books');
    else listeners.get(interaction)();
    resolveResponse({ ok: true, json: async () => [{ id: 42, name: 'Saved picks', items: [] }] });
    assert.equal(await navigation, false, interaction);
    assert.equal(elements.get('collection-42').focused, undefined, interaction);
    assert.equal(listeners.size, 0, interaction);
    if (interaction === 'tab') assert.equal(context.currentTab, 'books');
  }
});

test('collection renders immediately but focus and scroll wait for delayed startup layout', async () => {
  const layout = deferred();
  const { context, elements, requests } = setup(undefined, { layoutReady: layout.promise });
  const navigation = context.openCollectionFromLocation();
  await settle();
  assert.equal(requests.length, 1, 'the collection request does not wait for dashboard guidance');
  const card = elements.get('collection-42');
  assert.ok(card, 'the collection is usable while guidance is still loading');
  assert.equal(card.focused, undefined);
  assert.equal(card.scrolled, undefined);
  card.layoutTop = 1176;
  card.scrollIntoView = function () {
    this.scrollCount = (this.scrollCount || 0) + 1;
    this.scrolledFrom = this.layoutTop;
  };
  layout.resolve();
  assert.equal(await navigation, true);
  assert.equal(card.focused, true);
  assert.equal(card.scrolledFrom, 1176, 'scroll uses the position after panels above finish rendering');
  assert.equal(card.scrollCount, 1);
});

test('scrolling or navigating during the layout wait prevents the final automatic focus', async () => {
  for (const interaction of ['pointerdown', 'keydown', 'wheel', 'touchstart', 'tab']) {
    const layout = deferred();
    const { context, elements, listeners } = setup(undefined, { layoutReady: layout.promise });
    const navigation = context.openCollectionFromLocation();
    await settle();
    if (interaction === 'tab') await context.switchTab('books');
    else listeners.get(interaction)();
    layout.resolve();
    assert.equal(await navigation, false, interaction);
    assert.equal(elements.get('collection-42').focused, undefined, interaction);
    assert.equal(elements.get('collection-42').scrolled, undefined, interaction);
    assert.equal(listeners.size, 0, interaction);
  }
});

test('startup readiness includes movie/deck producers and all their layout batches, even after rejection', async () => {
  const { context, elements } = setup();
  const movie = deferred();
  const deck = deferred();
  const batches = [];
  const timers = new Map();
  let timerId = 0;
  context.window.setTimeout = callback => { const id = ++timerId; timers.set(id, callback); return id; };
  context.window.clearTimeout = id => timers.delete(id);
  context.launchpadRefreshTimer = null;
  context.launchpadDecisionRefreshRequested = false;
  context.decisionCardsRefreshPromise = null;
  context.setupLibrarySearch = () => {};
  context.loadMovies = async () => { await movie.promise; context.scheduleLibraryLaunchpadRefresh(false); };
  context.bootstrapReturnDeck = async () => { await deck.promise; context.scheduleLibraryLaunchpadRefresh(true); };
  context.refreshLibraryLaunchpad = () => { const batch = { launchpad: deferred(), queue: deferred(), decisions: deferred() }; batches.push(batch); return batch.launchpad.promise; };
  context.refreshNextUpQueue = () => batches.at(-1).queue.promise;
  context.refreshDashboardDecisionCards = () => {
    context.decisionCardsRefreshPromise = batches.at(-1).decisions.promise;
    return context.decisionCardsRefreshPromise;
  };
  vm.runInContext(source.slice(source.indexOf('const dashboardLayoutRefreshes ='), source.indexOf('const loadMovieLibrary =')), context);
  vm.runInContext(source.slice(source.indexOf('// Load initial data'), source.indexOf('// Landing Page Enhancements:')), context);
  function runTimers() {
    const callbacks = Array.from(timers.values()); timers.clear(); callbacks.forEach(callback => callback());
  }

  const navigation = context.openCollectionFromLocation();
  await settle();
  const card = elements.get('collection-42');
  runTimers(); // The first debounce can already be running before movie/deck finish.
  assert.equal(batches.length, 1);
  deck.resolve();
  await settle();
  runTimers();
  assert.equal(batches.length, 2);
  movie.resolve();
  await settle();
  runTimers();
  assert.equal(batches.length, 3);
  assert.equal(card.scrolled, undefined);
  batches[2].launchpad.resolve(); batches[2].queue.resolve();
  batches[1].launchpad.reject(new Error('Optional launchpad unavailable'));
  batches[1].queue.resolve(); batches[1].decisions.resolve();
  await settle();
  assert.equal(card.scrolled, undefined, 'an older in-flight batch can still change layout');

  // Later ordinary interaction must not extend this one-time startup barrier.
  context.scheduleLibraryLaunchpadRefresh(false);
  runTimers();
  assert.equal(batches.length, 4);
  batches[0].launchpad.resolve(); batches[0].queue.resolve();
  assert.equal(await navigation, true);
  assert.equal(card.scrollCount, 1);
  batches[3].launchpad.resolve(); batches[3].queue.resolve();
  await settle();
  assert.equal(card.scrollCount, 1, 'later dashboard updates never trigger another automatic scroll');
});
