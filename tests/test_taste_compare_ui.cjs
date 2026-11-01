// Compare-tastes answers kept in a visitor's browser, and their move into a library after sign-up.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function setup({ publicShell = 'false', user = { username: 'new' }, fetchImpl, dashboard = true } = {}) {
  const store = new Map();
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  const body = { children: [], appendChild(node) { this.children.push(node); } };
  global.document = {
    readyState: 'complete', documentElement: { dataset: { publicShell } }, body,
    getElementById: id => (id === 'mainContainer' && dashboard ? {} : null),
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
    createElement: () => ({ setAttribute() {}, remove() {}, append() {}, textContent: '' }),
  };
  const calls = [];
  global.window = {};
  global.getUser = () => user;
  global.fetch = fetchImpl || (async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, status: 200, json: async () => ({ added: [{ title: 'Arrival' }], existing: [], match: { score: 80 } }) };
  });
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/taste-compare.js')];
  const api = require(path.join(__dirname, '../app/static/taste-compare.js'));
  return { api, store, calls, body };
}

const saved = (extra = {}) => JSON.stringify({
  owner: 7, name: 'dana', link: '/u/dana/match', pending: true,
  answers: { 'movies:12': 'loved', 'tv-shows:3': 'skip', 'books:9': 'want' }, ...extra,
});

test('tampered storage is cleaned on read', () => {
  const { api, store } = setup();
  store.set(api.KEY, saved({ link: 'https://evil.example/', answers: { 'movies:12': 'loved', '../x': 'loved', 'books:1': 'bogus' } }));
  assert.deepEqual(api.read(), { owner: 7, name: 'dana', link: '', answers: { 'movies:12': 'loved' }, pending: true });
  store.set(api.KEY, saved({ owner: 'x' }));
  assert.equal(api.read(), null);
  store.set(api.KEY, '{not json');
  assert.equal(api.read(), null);
});

test('pending answers move into the library once and are then cleared', async () => {
  const { api, store, calls, body } = setup();
  store.set(api.KEY, saved());
  await api.importAnswers();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/taste-match/u/7/answers');
  assert.deepEqual(calls[0].body, { answers: [{ id: 'movies:12', answer: 'loved' }, { id: 'books:9', answer: 'want' }], source: 'guest' });
  assert.equal(store.has(api.KEY), false);
  assert.equal(body.children.length, 1);
  await api.importAnswers();
  assert.equal(calls.length, 1);
});

test('nothing is sent from a public page or without a member', async () => {
  for (const options of [{ publicShell: 'true' }, { user: null }, { dashboard: false }]) {
    const { api, store, calls } = setup(options);
    store.set(api.KEY, saved());
    await api.importAnswers();
    assert.equal(calls.length, 0);
  }
});

test('a link that was switched off drops the answers; a network error keeps them', async () => {
  let { api, store } = setup({ fetchImpl: async () => ({ ok: false, status: 404, json: async () => ({}) }) });
  store.set(api.KEY, saved());
  await api.importAnswers();
  assert.equal(store.has(api.KEY), false);
  ({ api, store } = setup({ fetchImpl: async () => { throw new Error('offline'); } }));
  store.set(api.KEY, saved());
  await api.importAnswers();
  assert.equal(api.read().pending, true);
});
