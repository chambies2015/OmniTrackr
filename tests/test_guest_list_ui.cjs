// Guest list kept in the browser before sign-up, and its move into a new library.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function setup({ publicShell = 'true', user = null, fetchImpl } = {}) {
  const store = new Map();
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  const body = { children: [], appendChild(node) { this.children.push(node); } };
  global.document = {
    readyState: 'complete', documentElement: { dataset: { publicShell } }, body,
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
    createElement: () => ({ setAttribute() {}, remove() {}, textContent: '' }),
  };
  const events = [];
  global.window = { reportFunnelEvent: event => events.push(event) };
  global.getUser = () => user;
  global.fetch = fetchImpl || (async () => ({ ok: true, json: async () => ({ added: [], existing: [], missing: 0 }) }));
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/guest-list.js')];
  const api = require(path.join(__dirname, '../app/static/guest-list.js'));
  return { api, store, events, body };
}

test('adding, de-duplicating and removing titles', () => {
  const { api, events } = setup();
  assert.equal(api.add('movie', 'interstellar-2014', 'Interstellar').added, true);
  assert.equal(api.add('movie', 'interstellar-2014', 'Interstellar').added, false);
  assert.deepEqual(api.read(), [{ kind: 'movie', slug: 'interstellar-2014', title: 'Interstellar' }]);
  assert.deepEqual(events, ['guest_pick_added']);
  assert.deepEqual(api.remove('movie', 'interstellar-2014'), []);
});

test('bad or tampered entries are ignored', () => {
  const { api, store } = setup();
  store.set(api.KEY, JSON.stringify([{ kind: 'movie', slug: '../../etc', title: 'x' }, { kind: 'podcast', slug: 'a', title: 'x' },
    { kind: 'book', slug: 'dune-1965', title: 'Dune' }]));
  assert.deepEqual(api.read().map(item => item.slug), ['dune-1965']);
  store.set(api.KEY, 'not json');
  assert.deepEqual(api.read(), []);
  assert.equal(api.add('movie', 'Has Caps', 'x').added, false);
});

test('the list is capped', () => {
  const { api } = setup();
  for (let i = 0; i < api.MAX + 5; i += 1) api.add('movie', `t-${i}`, `T ${i}`);
  assert.equal(api.read().length, api.MAX);
  assert.equal(api.add('movie', 'one-more', 'x').full, true);
});

test('nothing is imported on the public homepage or when signed out', async () => {
  let calls = 0;
  const { api } = setup({ fetchImpl: async () => { calls += 1; return { ok: true, json: async () => ({}) }; } });
  api.add('movie', 'up-2009', 'Up');
  assert.equal(await api.importList(), null);
  const second = setup({ publicShell: 'false', user: null, fetchImpl: async () => { calls += 1; return { ok: true }; } });
  second.api.add('movie', 'up-2009', 'Up');
  assert.equal(await second.api.importList(), null);
  assert.equal(calls, 0);
});

test('signed in: the list is sent once, cleared and confirmed', async () => {
  let sent = null;
  const { api, body } = setup({
    publicShell: 'false', user: { id: 1 },
    fetchImpl: async (url, options) => { sent = { url, body: JSON.parse(options.body) }; return { ok: true, json: async () => ({ added: [{ title: 'Up' }], existing: [], missing: 0 }) }; },
  });
  api.add('movie', 'up-2009', 'Up <b>');
  const result = await api.importList();
  assert.equal(sent.url, '/api/guest-list/import');
  assert.deepEqual(sent.body, { items: [{ kind: 'movie', slug: 'up-2009' }] });  // titles never sent
  assert.equal(result.added.length, 1);
  assert.deepEqual(api.read(), []);
  assert.match(body.children[0].textContent, /Added 1 title/);
});

test('a network failure keeps the list for next time', async () => {
  const { api } = setup({ publicShell: 'false', user: { id: 1 }, fetchImpl: async () => { throw new Error('offline'); } });
  api.add('movie', 'up-2009', 'Up');
  assert.equal(await api.importList(), null);
  assert.equal(api.read().length, 1);
});

test('a title-page save button toggles once per click (not also treated as a homepage tile)', () => {
  const store = new Map();
  global.localStorage = { getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k) };
  const listeners = [];
  const button = {
    dataset: { guestKind: 'movie', guestSlug: 'arrival-2016', guestTitle: 'Arrival' }, textContent: '',
    setAttribute() {}, addEventListener: (name, fn) => listeners.push(fn),
  };
  const status = { textContent: '' };
  global.document = {
    readyState: 'complete', documentElement: { dataset: { publicShell: 'true' } }, addEventListener() {},
    // A selector that ignores :not([data-guest-save]) would bind the button twice.
    querySelectorAll: selector => (selector.includes('data-guest-save') && !selector.includes(':not') ? [button]
      : selector.includes(':not([data-guest-save])') ? [] : [button]),
    querySelector: selector => (selector === '.title-hero__status' ? status : null),
  };
  global.window = { reportFunnelEvent() {} };
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/guest-list.js')];
  const api = require(path.join(__dirname, '../app/static/guest-list.js'));
  assert.equal(listeners.length, 1);
  listeners.forEach(fn => fn());
  assert.equal(api.read().length, 1);
  assert.match(button.textContent, /Saved/);
});
