// Friends feed: card wording, filters, times sent as naive UTC, and safe title links.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load() {
  const module = { exports: {} };
  const context = vm.createContext({ module, window: {}, document: {}, URLSearchParams });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/friends-feed.js'), 'utf8'), context);
  return module.exports;
}

test('each kind of update reads as a short sentence', () => {
  const { action } = load();
  assert.equal(action({ kind: 'finished', category: 'movies' }), 'finished a movie');
  assert.equal(action({ kind: 'finished', category: 'music' }), 'listened to an album');
  assert.equal(action({ kind: 'reviewed', category: 'books' }), 'reviewed a book');
  assert.equal(action({ kind: 'rated', category: 'video-games' }), 'rated a game');
  assert.equal(action({ kind: 'added', category: 'anime', finished: true }), "added an anime they've watched");
  assert.equal(action({ kind: 'added', category: 'tv-shows', finished: false }), 'added a show');
});

test('filters sort updates into finished, opinions and adds', () => {
  const { matches } = load();
  const finished = { type: 'title', kind: 'finished', rating: null };
  const addedDone = { type: 'title', kind: 'added', finished: true, rating: null };
  const rated = { type: 'title', kind: 'added', finished: false, rating: 8 };
  const burst = { type: 'burst' };
  assert.ok(matches(finished, 'finished') && matches(addedDone, 'finished') && !matches(rated, 'finished'));
  assert.ok(matches(rated, 'opinions') && !matches(finished, 'opinions'));
  assert.ok(matches(burst, 'added') && !matches(burst, 'finished') && matches(burst, 'all'));
});

test('server times are UTC even without a zone', () => {
  const { ago, parseTime } = load();
  assert.equal(parseTime('2026-10-25T12:00:00').toISOString(), '2026-10-25T12:00:00.000Z');
  assert.equal(parseTime('2026-10-25T12:00:00+00:00').toISOString(), '2026-10-25T12:00:00.000Z');
  assert.equal(parseTime('nope'), null);
  const now = new Date('2026-10-25T15:00:00Z');
  assert.equal(ago('2026-10-25T14:59:30', now), 'just now');
  assert.equal(ago('2026-10-25T14:15:00', now), '45m ago');
  assert.equal(ago('2026-10-25T10:00:00', now), '5h ago');
  assert.equal(ago('2026-10-22T15:00:00', now), '3d ago');
});

test('only title page paths become links, and ratings read out of ten', () => {
  const { rating, safePath } = load();
  assert.equal(safePath('/titles/movie/interstellar-2014'), '/titles/movie/interstellar-2014');
  assert.equal(safePath('javascript:alert(1)'), null);
  assert.equal(safePath('//evil.example/titles/movie/x'), null);
  assert.equal(rating(8), '8/10');
  assert.equal(rating(8.5), '8.5/10');
  assert.equal(rating(null), '');
});

test('updates are grouped under Today, Yesterday, This week and Earlier', () => {
  const { dayLabel } = load();
  const now = new Date(2026, 10, 13, 15, 0, 0);
  const at = date => date.toISOString().replace('Z', '');
  assert.equal(dayLabel(at(new Date(2026, 10, 13, 9, 0, 0)), now), 'Today');
  assert.equal(dayLabel(at(new Date(2026, 10, 12, 23, 0, 0)), now), 'Yesterday');
  assert.equal(dayLabel(at(new Date(2026, 10, 9, 12, 0, 0)), now), 'This week');
  assert.equal(dayLabel(at(new Date(2026, 9, 30, 12, 0, 0)), now), 'Earlier');
  assert.equal(dayLabel('not a date', now), 'Earlier');
});

test('||double bars|| in a review are kept back as spoilers', () => {
  const { spoilerParts } = load();
  assert.deepEqual(JSON.parse(JSON.stringify(spoilerParts('Rocky rules. ||The ending|| made me cry.'))),
    [{ text: 'Rocky rules. ' }, { text: 'The ending', hidden: true }, { text: ' made me cry.' }]);
  assert.deepEqual(JSON.parse(JSON.stringify(spoilerParts('No secrets here'))), [{ text: 'No secrets here' }]);
  assert.deepEqual(JSON.parse(JSON.stringify(spoilerParts('a || b'))), [{ text: 'a || b' }]);
});
