// Run with: node --test tests/test_todays_pick_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/app.js'), 'utf8');

function setup() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, disabled: false, textContent: '',
      removeAttribute() {}, setAttribute() {},
    });
    return elements.get(id);
  };
  const categories = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books'];
  const row = { classList: { add() {} }, focus() { this.focused = true; }, scrollIntoView() {} };
  const context = vm.createContext({
    document: {
      getElementById: element,
      querySelector(selector) { context.selector = selector; return { closest: () => row }; },
      querySelectorAll: () => [],
    },
    URLSearchParams, setTimeout, Date,
    API_BASE: '', hasStoredAuth: () => true,
    LIBRARY_SEARCH_SOURCES: categories.map(tab => ({ tab, input: tab + 'Search' })),
    getTabButton: () => ({ style: {} }),
    switchTab: async tab => { context.openedTab = tab; },
    isLoadingMovies: false, isLoadingTVShows: false, isLoadingAnime: false,
    isLoadingVideoGames: false, isLoadingMusic: false, isLoadingBooks: false,
    todaysPickOffset: 0, todaysPickCandidateCount: 0, todaysPickRequest: 0,
    todaysPickSelection: null,
    editingRowId: null,
    libraryPages: new Map(),
    libraryPageConfig: tab => [tab + 'Table', tab + 'Sort'],
  });
  vm.runInContext(source.slice(source.indexOf('function renderTodaysPick('), source.indexOf('function renderNextUpQueue(')), context);
  return { context, element, row, categories };
}

test('another pick cycles beyond 25 clicks without exceeding the candidate pool', () => {
  const { context } = setup();
  context.todaysPickCandidateCount = 72;
  context.refreshTodaysPick = () => {};
  for (let i = 0; i < 100; i++) context.tryAnotherPick();
  assert.equal(context.todaysPickOffset, 28);
});

test('empty category keeps the filter accessible and hides item actions', () => {
  const { context, element } = setup();
  context.renderTodaysPick({ pick: null, candidate_count: 0 });
  assert.equal(element('todaysPickOpen').hidden, true);
  assert.equal(element('todaysPickAnother').hidden, true);
  assert.match(element('todaysPickReason').textContent, /another category/);
});

test('late response cannot replace the latest category selection', async () => {
  const { context, element } = setup();
  const pending = [];
  context.authenticatedFetch = url => new Promise(resolve => pending.push({ url, resolve }));
  element('todaysPickFilter').value = 'movies';
  const first = context.refreshTodaysPick();
  element('todaysPickFilter').value = 'anime';
  const second = context.refreshTodaysPick();
  assert.match(pending[1].url, /category=anime/);
  pending[1].resolve({ ok: true, json: async () => ({ pick: { title: 'Anime' }, candidate_count: 1 }) });
  await second;
  pending[0].resolve({ ok: true, json: async () => ({ pick: { title: 'Old movie' }, candidate_count: 1 }) });
  await first;
  assert.equal(element('todaysPickName').textContent, 'Anime');
});

test('Open it focuses the exact item ID in each media category', async () => {
  const { context, element, row, categories } = setup();
  for (const category of categories) {
    context.todaysPickSelection = { id: 42, title: 'A shared title', category };
    await context.openTodaysPick();
    assert.equal(context.openedTab, category);
    assert.equal(element(category + 'Search').value, 'A shared title');
    assert.match(context.selector, /data-next-up-item-id="42"/);
    assert.ok(context.selector.includes(`data-next-up-category="${category}"`));
    assert.equal(row.focused, true);
  }
});
