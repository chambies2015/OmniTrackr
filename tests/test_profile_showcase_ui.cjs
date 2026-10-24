// Account → Public profile → Showcase picker: what it accepts from the server and how rows read.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = { readyState: 'complete', getElementById: () => null, addEventListener() {} };
  global.window = { location: { hash: '' }, addEventListener() {} };
  delete require.cache[require.resolve('../app/static/profile-showcase.js')];
  return require(path.join(__dirname, '../app/static/profile-showcase.js'));
}

test('only well-formed library titles are kept', () => {
  const { cleanItems } = load();
  const items = cleanItems([
    { category: 'movies', id: 4, title: 'Arrival' },
    { category: 'movies', id: '4', title: 'String id' },
    { category: '../users', id: 1, title: 'Bad category' },
    { category: 'books', id: 2, title: null },
    null,
  ]);
  assert.deepEqual(items.map(item => item.title), ['Arrival']);
  assert.deepEqual(cleanItems('nope'), []);
});

test('the subtitle joins kind, year and rating', () => {
  const { subtitle } = load();
  assert.equal(subtitle({ label: 'Movie', year: 2016, rating: 9 }), 'Movie · 2016 · 9/10');
  assert.equal(subtitle({ label: 'Video game', year: null, rating: null }), 'Video game');
});
