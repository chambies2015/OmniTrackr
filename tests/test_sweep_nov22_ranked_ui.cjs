// Sweep of #309 (Nov 22 2026): a ranking kept before sign-up remembers the places it was made from,
// so a film and its remake on one shared top ten stay apart.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  const store = new Map();
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  global.document = undefined;
  global.window = {};
  const file = path.join(__dirname, '..', 'app', 'static', 'ranked-share.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const token = 'abcdefghijklmnop';

test('the places go with the titles and come back out', () => {
  const share = load();
  assert.ok(share.storeTake(token, ['Dune', 'Heat', 'Dune'], true, [2, 3, 1]));
  assert.deepEqual(share.readTake(token), { token, titles: ['Dune', 'Heat', 'Dune'], positions: [2, 3, 1], pending: true });
});

test('places that do not line up with the titles are left out, never guessed', () => {
  const share = load();
  const keep = extra => localStorage.setItem(share.KEY, JSON.stringify({ v: 1, token, titles: ['Dune', 'Heat'], at: Date.now(), pending: true, ...extra }));
  for (const positions of [[1], [1, 2, 3], [0, 2], [1, 11], [1.5, 2], ['1', 2], 'nope']) {
    keep({ positions });
    assert.equal(share.readTake(token).positions, null, JSON.stringify(positions));
  }
  keep({});
  assert.deepEqual(share.readTake(token), { token, titles: ['Dune', 'Heat'], positions: null, pending: true });
});
