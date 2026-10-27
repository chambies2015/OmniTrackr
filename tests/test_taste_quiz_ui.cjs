// Taste quiz answers kept in the browser, and their move into a library at first log-in.
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
    createElement: () => ({ setAttribute() {}, remove() {}, textContent: '' }),
  };
  const calls = [];
  global.window = {};
  global.getUser = () => user;
  global.fetch = fetchImpl || (async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, status: 200, json: async () => ({ added: [{ title: 'Dune' }], existing: [], suggestions: [] }) };
  });
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/taste-quiz.js')];
  const api = require(path.join(__dirname, '../app/static/taste-quiz.js'));
  return { api, store, calls, body };
}

test('tampered storage is cleaned on read', () => {
  const { api, store } = setup();
  store.set(api.KEY, JSON.stringify({ answers: { 'movie/dune-2021': 'loved', '../x': 'loved', 'tv/ok-1': 'bogus' }, kinds: ['movie', 'podcast'], pending: true }));
  assert.deepEqual(api.read(), { answers: { 'movie/dune-2021': 'loved' }, kinds: ['movie'], pending: true });
  store.set(api.KEY, '{not json');
  assert.equal(api.read(), null);
});

test('skips are never sent to the server', () => {
  const { api } = setup();
  assert.deepEqual(api.answerList({ 'movie/dune-2021': 'want', 'tv/arcane-2021': 'skip' }), [{ id: 'movie/dune-2021', answer: 'want' }]);
});

test('pending answers move into the library once, then stay for a retake', async () => {
  const { api, store, calls, body } = setup();
  store.set(api.KEY, JSON.stringify({ answers: { 'movie/dune-2021': 'loved', 'tv/arcane-2021': 'skip' }, kinds: ['movie'], pending: true }));
  await api.importAnswers();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/taste-quiz/save');
  assert.deepEqual(calls[0].body, { answers: [{ id: 'movie/dune-2021', answer: 'loved' }], kinds: ['movie'], source: 'guest' });
  assert.equal(api.read().pending, false);
  assert.equal(body.children.length, 1);
  await api.importAnswers();
  assert.equal(calls.length, 1);
});

test('nothing is sent from a public page or without a member', async () => {
  for (const options of [{ publicShell: 'true' }, { user: null }, { dashboard: false }]) {
    const { api, store, calls } = setup(options);
    store.set(api.KEY, JSON.stringify({ answers: { 'movie/dune-2021': 'loved' }, pending: true }));
    await api.importAnswers();
    assert.equal(calls.length, 0);
    assert.equal(api.read().pending, true);
  }
});

test('a failed request keeps the answers for the next visit', async () => {
  const { api, store } = setup({ fetchImpl: async () => ({ ok: false, status: 500, json: async () => ({}) }) });
  store.set(api.KEY, JSON.stringify({ answers: { 'movie/dune-2021': 'loved' }, pending: true }));
  await api.importAnswers();
  assert.equal(api.read().pending, true);
});
