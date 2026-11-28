// Pick swap scripts: date sums, the formats line, which links and pictures are allowed, and search filtering.
const { test } = require('node:test');
const assert = require('node:assert/strict');

const page = require('../app/static/pick-swap.js');
const home = require('../app/static/pick-swap-home.js');

test('days add across month ends', () => {
  assert.equal(page.addDays('2026-11-30', 1), '2026-12-01');
  assert.equal(page.addDays('2026-12-25', -7), '2026-12-18');
  assert.equal(page.addDays('not a day', 3), '');
});

test('the formats line reads like the server one', () => {
  assert.equal(page.kindsLabel([]), 'Anything: films, shows, books, games, music and more');
  assert.equal(page.kindsLabel(['book']), 'Books');
  assert.equal(page.kindsLabel(['tv', 'movie']), 'Films or shows');
  assert.equal(page.kindsLabel(['movie', 'tv', 'anime']), 'Films, shows or anime');
});

test('countdown words', () => {
  assert.equal(page.daysWords(0), 'Unwrap day is today');
  assert.equal(page.daysWords(1), '1 day to unwrap day');
  assert.equal(page.daysWords(12), '12 days to unwrap day');
});

test('only swap and title paths, and only https pictures', () => {
  assert.equal(page.safePath('/swap/12'), '/swap/12');
  assert.equal(page.safePath('/titles/tv/arcane-2021'), '/titles/tv/arcane-2021');
  assert.equal(page.safePath('https://evil.example/swap/1'), '/swap');
  assert.equal(page.safePath('javascript:alert(1)'), '/swap');
  assert.equal(page.safeImage('https://image.tmdb.org/t/p/w342/a.jpg'), 'https://image.tmdb.org/t/p/w342/a.jpg');
  assert.equal(page.safeImage('http://example.com/a.jpg'), '');
  assert.equal(home.safePath('/swap/3'), '/swap/3');
  assert.equal(home.safePath('/swap/3/../../x'), '/swap');
});

test('search results keep to the swap formats', () => {
  const results = [{ kind: 'movie', title: 'Heat' }, { kind: 'book', title: 'Dune' }, { kind: 'nope', title: 'X' }];
  assert.deepEqual(page.allowedResults(results, ['book']).map(item => item.title), ['Dune']);
  assert.deepEqual(page.allowedResults(results, []).map(item => item.title), ['Heat', 'Dune']);
  assert.deepEqual(page.allowedResults(null, []), []);
});

test('the home card shows three swaps at most', () => {
  const data = { swaps: [1, 2, 3, 4].map(id => ({ id, name: `Swap ${id}` })) };
  assert.equal(home.shown(data).length, 3);
  assert.deepEqual(home.shown(null), []);
});
