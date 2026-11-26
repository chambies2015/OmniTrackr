// Yearbook scripts: which links and pictures are allowed, the four-pick limit, and the home card's title.
const { test } = require('node:test');
const assert = require('node:assert/strict');

const page = require('../app/static/yearbook.js');
const home = require('../app/static/yearbook-home.js');

test('only yearbook paths and https pictures', () => {
  assert.equal(page.safePath('/yearbook/abcdefghijklmnopqrst'), '/yearbook/abcdefghijklmnopqrst');
  assert.equal(page.safePath('/yearbook#waiting'), '/yearbook#waiting');
  assert.equal(page.safePath('https://evil.example/yearbook'), '/yearbook');
  assert.equal(page.safePath('//evil.example'), '/yearbook');
  assert.equal(page.safePath('/yearbook/short'), '/yearbook');
  assert.equal(page.safeImage('https://image.tmdb.org/t/p/w500/x.jpg'), 'https://image.tmdb.org/t/p/w500/x.jpg');
  assert.equal(page.safeImage('http://image.tmdb.org/x.jpg'), null);
  assert.equal(page.safeImage('javascript:alert(1)'), null);
  assert.equal(home.safePath('/yearbook/abcdefghijklmnopqrst#sign'), '/yearbook/abcdefghijklmnopqrst#sign');
  assert.equal(home.safePath('/elsewhere'), '/yearbook');
});

test('picks keep their order and stop at four', () => {
  let picks = [];
  for (const id of [1, 2, 3, 4, 5]) picks = page.togglePick(picks, { category: 'movies', id });
  assert.deepEqual(picks.map(pick => pick.id), [1, 2, 3, 4]);
  picks = page.togglePick(picks, { category: 'movies', id: 2 });
  assert.deepEqual(picks.map(pick => pick.id), [1, 3, 4]);
  picks = page.togglePick(picks, { category: 'books', id: 2 });
  assert.deepEqual(picks.map(pick => `${pick.category}:${pick.id}`), ['movies:1', 'movies:3', 'movies:4', 'books:2']);
});

test('words', () => {
  assert.equal(page.plural(1, 'note'), '1 note');
  assert.equal(page.plural(3, 'person', 'people'), '3 people');
  assert.equal(home.title({ stage: 'start', year: 2026 }), 'Your 2026 yearbook');
  assert.equal(home.title({ stage: 'closed', year: 2026 }), 'Class of 2026');
});
