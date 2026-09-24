const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const progressIntegration = source.slice(source.indexOf('async function refreshLibraryProgressView('));
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

function setup(category = 'books') {
  let now = 0, allowed = true, configuration;
  const timers = [], loads = [], dashboard = [];
  const filters = new Map([[category, { completion: 'unfinished', unrated: true, hasProgress: true }]]);
  const pages = new Map([[category, { offset: 50, total: 51, focusId: 42, signature: 'existing view' }]]);
  const context = vm.createContext({
    Promise, API_BASE: '', libraryBrowseEpoch: 0, currentTab: category, editingRowId: null,
    isLoadingTVShows: false, isLoadingAnime: false, isLoadingBooks: false,
    Date: { now: () => now },
    setTimeout: (callback, delay) => { timers.push({ callback, delay }); },
    getLibraryFilters: key => filters.get(key) || { hasProgress: false },
    libraryPageConfig: key => [null, null, () => {
      loads.push({ category: key, filters: filters.get(key), page: pages.get(key) });
      return Promise.resolve('refreshed');
    }],
    refreshNextUpQueue: async guard => { dashboard.push(['queue', guard]); },
    refreshLibraryPulse: async guard => { dashboard.push(['pulse', guard]); },
    window: { OmniProgress: { configure: value => { configuration = value; } } },
  });
  vm.runInContext(progressIntegration, context);
  return {
    context, filters, pages, loads, timers, dashboard, configuration,
    guard: () => allowed,
    setAllowed: value => { allowed = value; },
    flushWait: async (elapsed = 50) => {
      const timer = timers.shift();
      assert.ok(timer, 'Expected a pending bounded wait');
      assert.equal(timer.delay, 50);
      now += elapsed;
      timer.callback();
      await tick();
    },
  };
}

for (const category of ['tv-shows', 'anime', 'books']) {
  test(`saved or cleared ${category} progress reloads its filtered view without resetting filters or page`, async () => {
    const s = setup(category);
    const initialFilters = s.filters.get(category), initialPage = s.pages.get(category);
    for (const checkpoint of [{ unit: category === 'books' ? 'page' : 'episode', position: 6 }, null]) {
      assert.equal(await s.context.refreshLibraryProgressView({ category, checkpoint }, s.guard), 'refreshed');
    }
    assert.equal(s.loads.length, 2);
    for (const load of s.loads) {
      assert.equal(load.category, category);
      assert.equal(load.filters, initialFilters);
      assert.equal(load.page, initialPage);
      assert.equal(load.page.offset, 50);
    }
  });
}

test('unfiltered, unrelated, unsupported and actively edited libraries are not refreshed', async () => {
  for (const scenario of ['unfiltered', 'other tab', 'unsupported', 'edit', 'cancelled']) {
    const s = setup();
    let category = 'books';
    if (scenario === 'unfiltered') s.filters.get('books').hasProgress = false;
    if (scenario === 'other tab') s.context.currentTab = 'anime';
    if (scenario === 'unsupported') category = 'movies';
    if (scenario === 'edit') s.context.editingRowId = 42;
    if (scenario === 'cancelled') s.setAllowed(false);
    await s.context.refreshLibraryProgressView({ category, checkpoint: null }, s.guard);
    assert.equal(s.loads.length, 0, scenario);
    assert.equal(s.timers.length, 0, scenario);
  }
});

test('progress refresh waits for the in-flight category read instead of being dropped by its busy guard', async () => {
  const s = setup();
  s.context.isLoadingBooks = true;
  const pending = s.context.refreshLibraryProgressView({ category: 'books', checkpoint: null }, s.guard);
  assert.equal(s.loads.length, 0);
  await s.flushWait();
  assert.equal(s.loads.length, 0);
  assert.equal(s.timers.length, 1);
  s.context.isLoadingBooks = false;
  await s.flushWait();
  assert.equal(await pending, 'refreshed');
  assert.equal(s.loads.length, 1);
  assert.equal(s.loads[0].page.offset, 50);
});

test('each wait rechecks auth epoch, navigation, edit, current filters and save lifecycle', async () => {
  for (const scenario of ['auth', 'navigation', 'edit', 'filters', 'lifecycle']) {
    const s = setup();
    s.context.isLoadingBooks = true;
    const pending = s.context.refreshLibraryProgressView({ category: 'books' }, s.guard);
    if (scenario === 'auth') s.context.libraryBrowseEpoch++;
    if (scenario === 'navigation') s.context.currentTab = 'anime';
    if (scenario === 'edit') s.context.editingRowId = 42;
    if (scenario === 'filters') s.filters.get('books').hasProgress = false;
    if (scenario === 'lifecycle') s.setAllowed(false);
    s.context.isLoadingBooks = false;
    await s.flushWait();
    await pending;
    assert.equal(s.loads.length, 0, scenario);
    assert.equal(s.timers.length, 0, scenario);
  }
});

test('a stalled category read stops waiting after ten seconds without issuing a competing request', async () => {
  const s = setup();
  s.context.isLoadingBooks = true;
  const pending = s.context.refreshLibraryProgressView({ category: 'books' }, s.guard);
  await s.flushWait(10000);
  await pending;
  assert.equal(s.loads.length, 0);
  assert.equal(s.timers.length, 0);
});

test('the configured save callback refreshes the filtered library and existing dashboard surfaces', async () => {
  const s = setup();
  await s.configuration.onSaved({ category: 'books', checkpoint: null }, s.guard);
  assert.deepEqual(s.dashboard.map(([name]) => name), ['queue', 'pulse']);
  assert.ok(s.dashboard.every(([, guard]) => guard === s.guard));
  assert.equal(s.loads.length, 1);
  s.setAllowed(false);
  await s.configuration.onSaved({ category: 'books', checkpoint: null }, s.guard);
  assert.equal(s.dashboard.length, 2);
  assert.equal(s.loads.length, 1);
});
