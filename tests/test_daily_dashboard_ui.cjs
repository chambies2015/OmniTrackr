const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');

function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
function response(data, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => data }; }
function queue(count = 8) {
  return Array.from({ length: count }, (_, i) => ({ id: 600 + i, item_id: 42 + i, title: `Title ${i + 1}`, category: 'books', category_label: 'Book', available: true }));
}
function setup() {
  let context;
  const nodes = new Map(), rows = new Map(), requests = [], loads = [], alerts = [];
  class Element {
    constructor(tag = 'div') { this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.hidden = false; this.disabled = false; this.value = ''; this.style = {}; this._text = ''; this.classes = new Set(); this.classList = { add: value => this.classes.add(value), remove: value => this.classes.delete(value) }; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set innerHTML(_) { throw new Error('Dashboard titles must use textContent'); }
    append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
    appendChild(child) { this.append(child); }
    replaceChildren(...children) { for (const child of this.children) child.parent = null; this.children = []; this._text = ''; this.append(...children); }
    setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'hidden') this.hidden = true; }
    removeAttribute(key) { delete this.attributes[key]; if (key === 'hidden') this.hidden = false; }
    closest(selector) { if (selector === '[data-next-up-row-id]' && this.dataset.nextUpRowId) return this; return this.parent?.closest(selector) || null; }
    contains(node) { return this === node || this.children.some(child => child.contains(node)); }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(selector === 'button' && child.tagName === 'button' ? [child] : []), ...child.querySelectorAll(selector)]); }
    querySelector() { return this.heading || null; }
    focus() { context.document.activeElement = this; }
    scrollIntoView() { this.scrolled = true; }
  }
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const tabs = new Map();
  const categories = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books'];
  categories.forEach(category => tabs.set(category, new Element('button')));
  context = vm.createContext({
    Date, URLSearchParams, setTimeout, console, API_BASE: '',
    currentTab: 'movies', editingRowId: null, account: { id: 1 },
    hasStoredAuth: () => !!context.account, getUser: () => context.account,
    getToken: () => null, returnDeckActive: false,
    todaysPickRequest: 0, todaysPickSelection: null, todaysPickCandidateCount: 0, todaysPickOffset: 0,
    isLoadingMovies: false, isLoadingTVShows: false, isLoadingAnime: false,
    isLoadingVideoGames: false, isLoadingMusic: false, isLoadingBooks: false,
    LIBRARY_SEARCH_SOURCES: categories.map(tab => ({ tab, input: tab + 'Search' })),
    libraryPages: new Map(), libraryPageConfig: tab => [tab + 'Table', tab + 'Sort'],
    getTabButton: tab => tabs.get(tab),
    window: {}, alert: value => alerts.push(value),
    document: {
      getElementById: get, createElement: tag => new Element(tag),
      querySelector: selector => { const match = selector.match(/data-next-up-category="([a-z-]+)".*data-next-up-item-id="(\d+)"/); const row = match && rows.get(`${match[1]}:${match[2]}`); return row ? { closest: () => row } : null; },
      querySelectorAll: () => [...rows.values()].filter(row => row.classes.has('pick-focused')),
      activeElement: null,
    },
    switchTab: async tab => { context.currentTab = tab; loads.push(tab); if (context.listReady) await context.listReady; if (!context.missingRow) rows.set(`${tab}:${context.libraryPages.get(tab).focusId}`, new Element('tr')); },
    authenticatedFetch: async (url, options) => { requests.push({ url, options }); return response([]); },
  });
  context.document.activeElement = get('outside');
  vm.runInContext(source.match(/const dailyDashboardState = .*;/)[0], context);
  vm.runInContext(source.slice(source.indexOf('function dailyDashboardSessionKey('), source.indexOf('const dashboardLayoutRefreshes')), context);
  const refreshPick = context.refreshTodaysPick;
  // Queue mutations refresh these independent panels; individual tests can restore their implementations.
  context.refreshLibraryPulse = () => {};
  context.refreshTodaysPick = () => {};
  const buttons = () => get('nextUpQueueItems').querySelectorAll('button');
  const action = (name, id, direction) => buttons().find(button => button.dataset.action === name && (id === undefined || Number(button.dataset.nextUpId) === id) && (direction === undefined || button.dataset.nextUpDirection === direction));
  return { context, get, tabs, rows, requests, loads, alerts, categories, buttons, action, Element, refreshPick };
}

test('Continue shows two recent titles, preserves all collapsed reflections, and never duplicates Next Up', () => {
  const s = setup();
  const items = queue(6).map(item => ({ ...item, id: item.item_id, status_label: 'Not read' }));
  s.context.renderLibraryPulse({ continue_items: items, reflection_items: items, next_up_items: items });
  assert.equal(s.get('libraryPulseContinue').children.length, 2);
  assert.equal(s.get('libraryPulseReflect').children.length, 6);
  assert.equal(s.get('libraryPulseReflections').hidden, false);
  assert.equal(s.get('libraryPulseReflections').open, undefined);
  assert.equal(s.get('libraryPulseReflectionCount').textContent, '(6)');
  assert.equal(s.get('libraryPulseContinue').children[0].dataset.pulseItemId, '42');
  s.get('libraryPulseReflections').open = true;
  s.context.renderLibraryPulse({ continue_items: items, reflection_items: items });
  assert.equal(s.get('libraryPulseReflections').open, true);
  s.context.renderLibraryPulse({ next_up_items: items });
  assert.equal(s.get('libraryPulse').hidden, true);
  s.context.returnDeckActive = true;
  s.context.renderLibraryPulse({ continue_items: items });
  assert.equal(s.get('libraryPulse').hidden, true);
});

test('Next Up previews three in saved order and expands to the full queue with correct reorder positions', () => {
  const s = setup(), items = queue();
  s.context.renderNextUpQueue(items);
  assert.equal(s.get('nextUpQueueItems').children.length, 3);
  assert.match(s.get('nextUpQueueSummary').textContent, /3 of 8 titles/);
  assert.equal(s.get('nextUpQueueToggle').textContent, 'Manage queue (8)');
  assert.equal(s.action('move-next-up'), undefined);
  assert.equal(s.action('pulse-open-item').dataset.pulseItemId, '42');
  assert.equal(s.action('remove-next-up').dataset.nextUpId, 600);
  s.context.toggleNextUpQueue();
  assert.equal(s.get('nextUpQueueItems').children.length, 8);
  assert.equal(s.get('nextUpQueueToggle').attributes['aria-expanded'], 'true');
  assert.equal(s.action('move-next-up', 600, 'up').disabled, true);
  assert.equal(s.action('move-next-up', 607, 'up').dataset.nextUpPosition, 6);
  assert.equal(s.action('move-next-up', 607, 'down').disabled, true);
  s.context.renderNextUpQueue(items);
  assert.equal(s.get('nextUpQueueItems').children.length, 8);
  s.context.toggleNextUpQueue();
  assert.equal(s.get('nextUpQueueItems').children.length, 3);
  assert.deepEqual(items.map(item => item.id), [600, 601, 602, 603, 604, 605, 606, 607]);
});

test('small queues retain management, unavailable titles retain removal, and empty queues stay hidden', () => {
  const s = setup(), items = queue(2); items[0].available = false;
  s.context.renderNextUpQueue(items);
  assert.equal(s.get('nextUpQueueToggle').hidden, false);
  const row = s.get('nextUpQueueItems').children[0];
  assert.deepEqual(row.querySelectorAll('button').map(button => button.dataset.action), ['remove-next-up']);
  assert.match(row.textContent, /deleted/);
  s.context.renderNextUpQueue([]);
  assert.equal(s.get('nextUpQueueToggle').hidden, true);
  assert.equal(s.get('nextUpQueue').hidden, true);
  assert.equal(s.get('nextUpQueueItems').children.length, 0);
});

test('refresh and reorder retain keyboard focus on the same title while removal chooses the nearest title', async () => {
  const s = setup(), items = queue(4);
  s.context.renderNextUpQueue(items); s.context.toggleNextUpQueue();
  s.action('move-next-up', 601, 'up').focus();
  s.context.authenticatedFetch = async () => response([items[1], items[0], items[2], items[3]]);
  await s.context.moveNextUp(601, 0);
  assert.equal(s.context.document.activeElement.dataset.nextUpId, 601);
  assert.equal(s.context.document.activeElement.dataset.nextUpDirection, 'down');
  s.action('remove-next-up', 601).focus();
  s.context.authenticatedFetch = async (url, options) => response(options?.method === 'DELETE' ? null : [items[0], items[2], items[3]]);
  await s.context.removeNextUp(601);
  assert.equal(s.context.document.activeElement.dataset.nextUpId, 600);
  assert.equal(s.context.document.activeElement.dataset.action, 'remove-next-up');
  s.get('outside').focus();
  s.context.renderNextUpQueue(items);
  assert.equal(s.context.document.activeElement, s.get('outside'));
});

test('removing the last item hides the queue and returns keyboard focus to Add anything', async () => {
  const s = setup(); s.context.renderNextUpQueue(queue(1));
  s.action('remove-next-up', 600).focus();
  await s.context.removeNextUp(600);
  assert.equal(s.get('nextUpQueue').hidden, true);
  assert.equal(s.context.document.activeElement, s.get('quickCaptureButton'));
});

test('an empty library shows no daily or queue panels, while a deliberately empty category retains its filter', () => {
  const s = setup();
  s.context.renderLibraryPulse({ continue_items: [], reflection_items: [], next_up_items: [] });
  s.context.renderTodaysPick({ pick: null, candidate_count: 0 });
  s.context.renderNextUpQueue([]);
  for (const id of ['libraryPulse', 'todaysPick', 'nextUpQueue']) assert.equal(s.get(id).hidden, true);
  s.get('todaysPickFilter').value = 'books';
  s.context.renderTodaysPick({ pick: null, candidate_count: 0 });
  assert.equal(s.get('todaysPick').hidden, false);
  assert.equal(s.get('todaysPickOpen').hidden, true);
  assert.match(s.get('todaysPickReason').textContent, /another category/);
  s.get('todaysPickFilter').value = '';
  s.context.renderTodaysPick({ pick: { title: 'A first title' }, candidate_count: 1 });
  s.context.renderNextUpQueue(queue(1));
  assert.equal(s.get('todaysPick').hidden, false);
  assert.equal(s.get('nextUpQueue').hidden, false);
});

test('a failed default pick request still displays recovery guidance and a successful empty retry hides it', async () => {
  const s = setup();
  s.context.authenticatedFetch = async () => response({}, 503);
  await s.refreshPick();
  assert.equal(s.get('todaysPick').hidden, false);
  assert.match(s.get('todaysPickReason').textContent, /Could not load a pick/);
  assert.equal(s.get('todaysPickOpen').disabled, false);
  s.context.authenticatedFetch = async () => response({ pick: null, candidate_count: 0 });
  await s.refreshPick();
  assert.equal(s.get('todaysPick').hidden, true);
});

test('pending moves serialize writes and prevent a stale queue read from replacing the final order', async () => {
  const s = setup(), items = queue(4), move = deferred(), read = deferred();
  s.context.renderNextUpQueue(items); s.context.toggleNextUpQueue();
  s.context.authenticatedFetch = (url, options) => { s.requests.push({ url, options }); return options?.method === 'PUT' ? move.promise : read.promise; };
  const moving = s.context.moveNextUp(601, 0);
  await s.context.removeNextUp(602);
  assert.equal(s.requests.length, 1);
  const reading = s.context.refreshNextUpQueue();
  move.resolve(response([items[1], items[0], items[2], items[3]])); await moving;
  read.resolve(response(items)); await reading;
  assert.equal(s.get('nextUpQueueItems').children[0].dataset.nextUpRowId, '601');
});

test('a failed reorder preserves the queue and makes another attempt available', async () => {
  const s = setup(); s.context.renderNextUpQueue(queue(4)); s.context.toggleNextUpQueue();
  s.context.authenticatedFetch = async () => response({}, 500);
  await s.context.moveNextUp(601, 0); await s.context.moveNextUp(601, 0);
  assert.equal(s.alerts.length, 2);
  assert.equal(s.get('nextUpQueueItems').children[0].dataset.nextUpRowId, '600');
  assert.equal(s.get('nextUpQueueItems').attributes['aria-busy'], 'false');
});

test('toggling during a pending mutation cannot strand disabled reorder controls after a failure', async () => {
  const s = setup(), pending = deferred(); s.context.renderNextUpQueue(queue(4)); s.context.toggleNextUpQueue();
  s.context.authenticatedFetch = () => pending.promise;
  const moving = s.context.moveNextUp(601, 0);
  assert.equal(s.get('nextUpQueueToggle').disabled, true);
  s.context.toggleNextUpQueue();
  assert.equal(s.get('nextUpQueueItems').children.length, 4);
  pending.resolve(response({}, 500)); await moving;
  assert.equal(s.get('nextUpQueueToggle').disabled, false);
  assert.equal(s.action('move-next-up', 601, 'up').disabled, false);
  s.context.toggleNextUpQueue();
  assert.equal(s.get('nextUpQueueItems').children.length, 3);
});

test('an earlier removal refresh cannot unlock a later pending move', async () => {
  const s = setup(), read = deferred(), move = deferred(), items = queue(4);
  s.context.renderNextUpQueue(items); s.context.toggleNextUpQueue();
  s.context.authenticatedFetch = async (url, options) => {
    s.requests.push({ url, options });
    if (options?.method === 'DELETE') return response(null);
    return options?.method === 'PUT' ? move.promise : read.promise;
  };
  const removing = s.context.removeNextUp(603);
  for (let i = 0; i < 8; i++) await Promise.resolve();
  const moving = s.context.moveNextUp(601, 0);
  read.resolve(response(items.slice(0, 3))); await removing;
  assert.equal(s.get('nextUpQueueToggle').disabled, true);
  await s.context.removeNextUp(602);
  assert.equal(s.requests.filter(request => request.options?.method === 'DELETE').length, 1);
  move.resolve(response([items[1], items[0], items[2]])); await moving;
  assert.equal(s.get('nextUpQueueToggle').disabled, false);
  assert.equal(s.get('nextUpQueueItems').children[0].dataset.nextUpRowId, '601');
});

test('an addition completed during a pending move or removal appears after that mutation settles', async () => {
  for (const operation of ['move', 'remove']) {
    for (const succeeds of [true, false]) {
      const s = setup(), pending = deferred(), items = queue(4), added = queue(5)[4];
      let server = succeeds ? (operation === 'move' ? [items[1], items[0], items[2], items[3]] : items.slice(0, 3)) : items.slice();
      const beforeAddition = server.slice();
      s.context.renderNextUpQueue(items); s.context.toggleNextUpQueue();
      s.context.authenticatedFetch = async (url, options) => {
        s.requests.push({ url, options });
        if (options?.method === 'PUT' || options?.method === 'DELETE') return pending.promise;
        if (options?.method === 'POST') { server.push(added); return response(added); }
        return response(server.slice());
      };
      const mutation = operation === 'move' ? s.context.moveNextUp(601, 0) : s.context.removeNextUp(603);
      await s.context.addToNextUp('books', added.item_id);
      assert.equal(s.requests.filter(request => !request.options?.method).length, 0);
      pending.resolve(response(beforeAddition, succeeds ? 200 : 500));
      await mutation;
      assert.deepEqual(s.get('nextUpQueueItems').children.map(row => row.dataset.nextUpRowId), server.map(item => String(item.id)), `${operation}, success=${succeeds}`);
      assert.equal(s.get('nextUpQueueToggle').attributes['aria-expanded'], 'true');
      assert.equal(s.requests.filter(request => !request.options?.method).length, 1);
    }
  }
});

test('sign-out resets expansion and rejects late queue reads and mutations even when the same account signs back in', async () => {
  for (const operation of ['read', 'move']) {
    const s = setup(), pending = deferred(); s.context.renderNextUpQueue(queue()); s.context.toggleNextUpQueue();
    s.context.authenticatedFetch = () => pending.promise;
    const work = operation === 'read' ? s.context.refreshNextUpQueue() : s.context.moveNextUp(601, 0);
    s.context.resetDailyDashboard();
    pending.resolve(response(queue())); await work;
    assert.equal(s.get('nextUpQueue').hidden, true);
    assert.equal(s.get('nextUpQueueItems').children.length, 0);
    s.context.renderNextUpQueue(queue());
    assert.equal(s.get('nextUpQueueItems').children.length, 3);
  }
});

test('dashboard Open resolves the exact media ID in every category and uses a visible error area', async () => {
  const s = setup();
  for (const category of s.categories) {
    const button = new s.Element('button');
    button.dataset = { pulseTab: category, pulseItemId: '52', pulseTitle: 'Duplicate title' };
    assert.equal(await s.context.openDashboardItem(button), true);
    assert.equal(s.context.libraryPages.get(category).focusId, 52);
    assert.equal(s.get(category + 'Search').value, 'Duplicate title');
    assert.equal(s.context.document.activeElement, s.rows.get(`${category}:52`));
    assert.equal(button.disabled, false);
    assert.equal(s.get('libraryNavigationStatus').hidden, true);
  }
  s.context.missingRow = true;
  const button = new s.Element('button'); button.dataset = { pulseTab: 'books', pulseItemId: '900', pulseTitle: 'Deleted title' };
  assert.equal(await s.context.openDashboardItem(button), false);
  assert.equal(s.get('libraryNavigationStatus').hidden, false);
  assert.match(s.get('libraryNavigationStatus').textContent, /could not be located/);
});

test('dirty edits, hidden categories and invalid item IDs never change the selected library', async () => {
  const s = setup(), button = new s.Element('button'); button.dataset = { pulseTab: 'books', pulseItemId: '52', pulseTitle: 'Title' };
  s.context.editingRowId = 1;
  assert.equal(await s.context.openDashboardItem(button), false);
  assert.match(s.get('libraryNavigationStatus').textContent, /Save or cancel/);
  s.context.editingRowId = null; s.tabs.get('books').style.display = 'none';
  assert.equal(await s.context.openDashboardItem(button), false);
  assert.match(s.get('libraryNavigationStatus').textContent, /Enable this media/);
  s.tabs.get('books').style.display = ''; button.dataset.pulseItemId = 'undefined';
  assert.equal(await s.context.openDashboardItem(button), false);
  assert.equal(s.loads.length, 0);
});

test('navigation and authentication changes during title loading prevent stale focus', async () => {
  for (const interrupt of [s => { s.context.currentTab = 'anime'; }, s => s.context.resetDailyDashboard(), s => { s.context.account = { id: 2 }; }]) {
    const s = setup(), ready = deferred(); s.context.listReady = ready.promise;
    const button = new s.Element('button'); button.dataset = { pulseTab: 'books', pulseItemId: '52', pulseTitle: 'Title' };
    const opening = s.context.openDashboardItem(button);
    interrupt(s); ready.resolve();
    assert.equal(await opening, false);
    assert.equal(s.context.document.activeElement, s.get('outside'));
    assert.equal(button.disabled, false);
  }
});

test('manual category navigation reveals its heading for standard and custom categories', async () => {
  const s = setup();
  s.context.switchTab = tab => { s.context.currentTab = tab; s.loads.push(tab); };
  for (const tab of ['books', 'activity', 'statistics', 'custom-4']) {
    const content = s.get(`${tab}-tab`), heading = new s.Element('h2'); content.heading = heading;
    assert.equal(await s.context.navigateLibraryTab(tab), true);
    assert.equal(s.context.document.activeElement, heading);
    assert.equal(heading.tabIndex, -1);
    assert.equal(heading.scrolled, true);
  }
  assert.match(source, /if \(target\.dataset\.switchTab\) \{\s+navigateLibraryTab\(target\.dataset\.switchTab\)/);
});

test('manual category navigation preserves edits and hidden categories and rejects stale loading results', async () => {
  const s = setup(); s.context.switchTab = tab => { s.context.currentTab = tab; s.loads.push(tab); };
  s.context.editingRowId = 1;
  assert.equal(await s.context.navigateLibraryTab('books'), false);
  s.context.editingRowId = null; s.tabs.get('books').style.display = 'none';
  assert.equal(await s.context.navigateLibraryTab('books'), false);
  assert.equal(s.loads.length, 0); s.tabs.get('books').style.display = '';
  const pending = deferred();
  s.context.switchTab = async tab => { s.context.currentTab = tab; if (tab === 'books') await pending.promise; };
  const first = s.context.navigateLibraryTab('books');
  assert.equal(await s.context.navigateLibraryTab('anime'), true);
  pending.resolve(); assert.equal(await first, false);
  assert.equal(s.context.document.activeElement, s.get('anime-tab'));
  const logout = deferred();
  s.context.switchTab = async tab => { s.context.currentTab = tab; await logout.promise; };
  const second = s.context.navigateLibraryTab('books');
  s.context.resetDailyDashboard(); logout.resolve();
  assert.equal(await second, false);
  assert.equal(s.context.document.activeElement, s.get('anime-tab'));
});

test('journal Open library retains category navigation instead of requiring a possibly deleted item', () => {
  assert.match(source, /'activity-open-library': \(\) => switchTab\(target\.dataset\.pulseTab\)/);
  const card = source.slice(source.indexOf('function buildActivityCard('), source.indexOf('async function loadActivityTimeline('));
  assert.match(card, /open\.dataset\.action = 'activity-open-library'/);
  assert.match(source, /'pulse-open-item': \(\) => openDashboardItem\(target\)/);
});
