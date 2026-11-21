// New Year challenge: the hours estimate, reading the pledge form and the dashboard card wording.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const nyc = require(path.join(__dirname, '../app/static/new-year-challenge.js'));

function row(category, hours, value) {
  return { dataset: { category, hours: String(hours) }, querySelector: () => ({ value }) };
}

function form(rows, max = 1000) {
  return { dataset: { max: String(max) }, querySelectorAll: () => rows };
}

test('hours read the same as on the server', () => {
  assert.equal(nyc.hoursLabel(0), '');
  assert.equal(nyc.hoursLabel(0.44), 'about 25 minutes a week');
  assert.equal(nyc.hoursLabel(0.01), 'about 5 minutes a week');
  assert.equal(nyc.hoursLabel(1), 'about 1 hour a week');
  assert.equal(nyc.hoursLabel(2.3), 'about 2.5 hours a week');
  assert.equal(nyc.hoursLabel(8), 'about 8 hours a week');
});

test('weekly hours add up typed numbers and skip blanks and the overall goal', () => {
  const rows = [row('books', 8, '52'), row('movies', 1.917, ''), row('all', 0, '100'), row('music', 0.75, 'abc')];
  assert.equal(nyc.weeklyHours(rows), 8);
  assert.match(nyc.totalText(8), /about 8 hours a week/);
  assert.match(nyc.totalText(0), /Fill in a number/);
});

test('the form sends numbers, null for blanks, and flags bad input', () => {
  const ok = nyc.collect(form([row('books', 8, '12'), row('movies', 2, ' ')]));
  assert.deepEqual(ok, { values: { books: 12, movies: null }, count: 1, invalid: false });
  assert.equal(nyc.collect(form([row('books', 8, '2.5')])).invalid, true);
  assert.equal(nyc.collect(form([row('books', 8, '0')])).invalid, true);
  assert.equal(nyc.collect(form([row('books', 8, '1001')])).invalid, true);
});

test('the dashboard card speaks to members who have and have not pledged', () => {
  const before = nyc.cardCopy({ year: 2027, pledged: false, started: false });
  assert.equal(before.title, "Pick what you'll finish in 2027");
  assert.equal(before.action, 'Make your pledge');
  const waiting = nyc.cardCopy({ year: 2027, pledged: true, started: false, goals: 1, days_until_start: 1, shared: false });
  assert.equal(waiting.title, "You're in. 1 day to go");
  assert.equal(waiting.summary, '1 goal pledged. Share your pledge card so friends can join you.');
  const going = nyc.cardCopy({ year: 2027, pledged: true, started: true, goals: 3, shared: true });
  assert.equal(going.title, "You're in with 3 goals");
  assert.equal(going.action, 'See your pledge');
});

test('sample years only use real goal categories', () => {
  const known = ['all', 'movies', 'tv-shows', 'anime', 'video-games', 'music', 'books', 'manga', 'podcasts', 'audiobooks'];
  Object.values(nyc.SAMPLES).forEach(sample => Object.keys(sample).forEach(key => assert.ok(known.includes(key), key)));
});

test('a draft from before signing in keeps goals the member already has', () => {
  const inputs = { books: { value: '10' }, anime: { value: '9' }, movies: { value: '' } };
  const rows = Object.keys(inputs).map(category => ({ dataset: { category }, querySelector: () => inputs[category] }));
  const page = { querySelectorAll: () => rows };
  // The draft has its own number for books and movies, and nothing for anime.
  nyc.fill(page, { books: 24, movies: 12 }, true);
  assert.deepEqual([inputs.books.value, inputs.anime.value, inputs.movies.value], ['24', '9', '12']);
  // Presets and "Clear" still replace the whole form.
  nyc.fill(page, { books: 6 });
  assert.deepEqual([inputs.books.value, inputs.anime.value, inputs.movies.value], ['6', '', '']);
  // A draft that isn't an object changes nothing.
  nyc.fill(page, null, true);
  assert.equal(inputs.books.value, '6');
});

test('the dashboard card is only asked for from November to January (UTC)', () => {
  const on = month => nyc.cardSeason(new Date(Date.UTC(2026, month, 15)));
  assert.deepEqual([10, 11, 0].map(on), [true, true, true]);
  assert.deepEqual([1, 2, 3, 4, 5, 6, 7, 8, 9].map(on), Array(9).fill(false));
  // The month is read in UTC, like the server's opening day.
  assert.equal(nyc.cardSeason(new Date('2027-01-31T23:59:00Z')), true);
  assert.equal(nyc.cardSeason(new Date('2027-02-01T00:00:00Z')), false);
});
