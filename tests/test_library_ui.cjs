const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/app.js'), 'utf8');

function setup() {
  const elements = { movieSearch: { value: '' }, movieSort: { value: '' } };
  const timers = [];
  const context = vm.createContext({
    URL, isLocal: false, location: { origin: 'http://localhost' }, API_BASE: '',
    LIBRARY_PAGE_SIZE: 50, libraryPages: new Map(), libraryFilters: new Map(), libraryBrowseEpoch: 0,
    LIBRARY_SEARCH_SOURCES: [{ tab: 'movies', input: 'movieSearch' }],
    document: { getElementById: id => elements[id] },
    libraryPageConfig: () => ['movieTable', 'movieSort', () => { context.reloads++; }],
    renderLibraryPager: (...args) => { context.pager = args; },
    setTimeout: callback => timers.push(callback), reloads: 0,
  });
  vm.runInContext(source.slice(source.indexOf('function getLibraryFilters('), source.indexOf('function renderLibraryFilters(')), context);
  vm.runInContext(source.slice(source.indexOf('async function fetchLibraryPage('), source.indexOf('const posterFetchInProgress')), context);
  return { context, elements, timers };
}

test('list requests are bounded and search/sort changes reset pagination', async () => {
  const { context, elements } = setup();
  const urls = [];
  context.authenticatedFetch = async url => {
    urls.push(new URL(url, 'http://localhost'));
    return { ok: true, json: async () => ({ items: [{ id: 1 }], total: 120, offset: Number(urls.at(-1).searchParams.get('offset')) }) };
  };
  let result = await context.fetchLibraryPage('/movies/?');
  assert.equal(result.total, 120);
  assert.equal(urls[0].pathname, '/library/page/movies');
  assert.equal(urls[0].searchParams.get('limit'), '50');
  context.libraryPages.get('movies').offset = 50;
  await context.fetchLibraryPage('/movies/?');
  assert.equal(urls.at(-1).searchParams.get('offset'), '50');
  assert.equal(context.libraryPages.get('movies').browseOnly, true);
  await context.fetchLibraryPage('/movies/?');
  assert.equal(context.libraryPages.get('movies').browseOnly, false);
  elements.movieSearch.value = 'new search';
  await context.fetchLibraryPage('/movies/?search=new%20search');
  assert.equal(urls.at(-1).searchParams.get('offset'), '0');
  context.libraryPages.get('movies').offset = 50;
  elements.movieSort.value = 'rating-desc';
  await context.fetchLibraryPage('/movies/?search=new%20search&sort_by=rating&order=desc');
  assert.equal(urls.at(-1).searchParams.get('offset'), '0');
});

test('search changed during an in-flight request does not render old rows', async () => {
  const { context, elements, timers } = setup();
  let resolve;
  context.authenticatedFetch = () => new Promise(done => { resolve = done; });
  const loading = context.fetchLibraryPage('/movies/?');
  elements.movieSearch.value = 'latest';
  resolve({ ok: true, json: async () => ({ items: [], total: 0, offset: 0 }) });
  assert.equal((await loading).ok, false);
  timers.forEach(callback => callback());
  assert.equal(context.reloads, 1);
});

test('page failure reports an error and does not pretend the library is empty', async () => {
  const { context } = setup();
  context.authenticatedFetch = async () => ({ ok: false });
  assert.equal((await context.fetchLibraryPage('/movies/?')).ok, false);
  assert.match(context.pager[3], /Could not load/);
});

test('exact navigation priority is cleared when the user changes their search', async () => {
  const { context, elements } = setup();
  const urls = [];
  context.libraryPages.set('movies', { offset: 0, total: 100, signature: context.libraryPageSignature('movies'), focusId: 99 });
  context.authenticatedFetch = async url => {
    urls.push(new URL(url, 'http://localhost'));
    return { ok: true, json: async () => ({ items: [], total: 100, offset: 0 }) };
  };
  await context.fetchLibraryPage('/movies/?');
  assert.equal(urls.at(-1).searchParams.get('focus_id'), '99');
  elements.movieSearch.value = 'different';
  await context.fetchLibraryPage('/movies/?search=different');
  assert.equal(urls.at(-1).searchParams.has('focus_id'), false);
});
