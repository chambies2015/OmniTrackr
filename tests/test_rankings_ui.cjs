// Rankings (rankings.js): the home card's copy, picking a format, placed wording, and the home layout rules.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

function load() {
  global.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; }, querySelectorAll() { return []; } };
  global.window = { addEventListener() {}, location: { hash: '' } };
  const file = path.join(__dirname, '..', 'app', 'static', 'rankings.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const question = extra => ({
  category: 'movies', label: 'Films', noun: 'film', nouns: 'films', ranked: 4, finished: 9, step: 1, left: 3,
  placing: { id: 1, title: 'Dune: Part Two' }, against: { id: 2, title: 'Arrival', position: 2 }, ...extra,
});

test('the home card says why it is asking', () => {
  const ui = load();
  assert.equal(ui.cardSummary({ status: 'fresh', question: question() }),
    'You finished Dune: Part Two this week. A few picks put it in its place among your films.');
  assert.equal(ui.cardSummary({ status: 'placing', question: question() }),
    "You're part-way through placing Dune: Part Two among your films.");
  assert.match(ui.cardSummary({ status: 'start', question: question({ ranked: 0 }) }), /got 9 to sort/);
  assert.match(ui.cardSummary({ status: 'start', question: question({ ranked: 0, finished: 2 }) }), /got two to start with/);
  assert.equal(ui.cardSummary({ status: 'more', question: question({ ranked: 1, noun: 'book', nouns: 'books' }) }),
    '1 book ranked so far. Keep going and your top ten sorts itself out.');
});

test('the tab opens on the format asked for, then one part-way placed, then the fullest with titles waiting', () => {
  const ui = load();
  const formats = [
    { category: 'movies', finished: 12, waiting: 0, placing: false },
    { category: 'books', finished: 4, waiting: 3, placing: false },
    { category: 'anime', finished: 0, waiting: 0, placing: false },
  ];
  assert.equal(ui.pickFormat(formats, 'movies'), 'movies');
  assert.equal(ui.pickFormat(formats, 'anime'), 'books');  // nothing finished there
  assert.equal(ui.pickFormat(formats, ''), 'books');       // films are all ranked; books still wait
  formats[0].placing = true;
  assert.equal(ui.pickFormat(formats, ''), 'movies');
  assert.equal(ui.pickFormat([{ category: 'music', finished: 0, waiting: 0 }], ''), 'music');
});

test('the words read out once a title lands', () => {
  const ui = load();
  assert.equal(ui.placedWords({ title: { title: 'Heat' }, position: 4, total: 12, noun: 'film', nouns: 'films' }),
    'Heat placed at number 4 of 12 films.');
  assert.equal(ui.placedWords({ title: { title: 'Piranesi' }, position: 1, total: 1, noun: 'book', nouns: 'books' }),
    'Piranesi placed at number 1 of 1 book.');
});

test('server text is only ever set as text, and links stay on this site', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'static', 'rankings.js'), 'utf8');
  assert.ok(!source.includes('innerHTML'));
  assert.ok(!source.includes('insertAdjacentHTML'));
  assert.ok(source.includes("const localPath = url => typeof url === 'string' && url.startsWith('/') && !url.startsWith('//')"));
  assert.ok(source.includes("url.startsWith('https://')"));
});

test('home layout keeps the card out mid-game and tucks it when it is only an offer', () => {
  global.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null; }, activeElement: null };
  global.window = { addEventListener() {}, location: { hash: '' }, localStorage: null };
  const file = path.join(__dirname, '..', 'app', 'static', 'home-layout.js');
  delete require.cache[require.resolve(file)];
  const layout = require(file);
  const unit = (status, engaged) => ({
    id: 'rankDuel', dataset: { status, ...(engaged ? { engaged: 'true' } : {}) },
    classList: { contains: () => false }, contains: () => false, querySelector: () => null,
  });
  for (const status of ['fresh', 'placing', 'placed']) assert.equal(layout.engaged(unit(status)), true, status);
  assert.equal(layout.engaged(unit('more')), false);
  assert.equal(layout.engaged(unit('more', true)), true);  // answered here this visit
  assert.equal(layout.quiet(unit('more')), true);
  assert.equal(layout.quiet(unit('start')), false);
});
