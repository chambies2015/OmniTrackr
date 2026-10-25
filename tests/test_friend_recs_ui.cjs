// Recommend to a friend: the dialog reads its title from the button, and the inbox meta line.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(storage = new Map()) {
  const module = { exports: {} };
  const context = vm.createContext({
    module, window: {}, document: {},
    localStorage: { getItem: key => (storage.has(key) ? storage.get(key) : null), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/friend-recs.js'), 'utf8'), context);
  return module.exports;
}

test('buttons name either a title page or a library item', () => {
  const { sourceFrom } = load();
  assert.deepEqual({ ...sourceFrom({ dataset: { recKind: 'movie', recSlug: 'heat-1995', recTitle: 'Heat' } }) },
    { kind: 'movie', slug: 'heat-1995', title: 'Heat' });
  assert.deepEqual({ ...sourceFrom({ dataset: { recCategory: 'books', recItemId: '12', recTitle: 'Dune' } }) },
    { category: 'books', item_id: 12, title: 'Dune' });
  assert.equal(sourceFrom({ dataset: { recCategory: 'books', recItemId: 'x' } }), null);
});

test('pending links keep only well-formed tokens', () => {
  const storage = new Map([['omnitrackr_pending_recs', JSON.stringify(['KkGJumr8OgXp1n1tQpiPApje', 'bad token', 7])]]);
  assert.deepEqual([...load(storage).readPending()], ['KkGJumr8OgXp1n1tQpiPApje']);
  assert.deepEqual([...load(new Map([['omnitrackr_pending_recs', '{oops']])).readPending()], []);
});

test('the inbox meta line skips what it does not know', () => {
  const { metaLine } = load();
  assert.equal(metaLine({ category_label: 'Movie', year: 2014, creator: 'Christopher Nolan' }), 'Movie · 2014 · Christopher Nolan');
  assert.equal(metaLine({ category_label: 'Game', year: null, creator: null }), 'Game');
});
