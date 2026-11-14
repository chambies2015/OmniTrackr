// The advent calendar: cleaning stored doors, the progress line and the dashboard card's "today's door".
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const advent = require(path.join(__dirname, '../app/static/advent-calendar.js'));

const DOORS = [1, 2, 3, 4, 5, 6].map(day => ({ day, date: `2026-12-0${day}`, hint: `Hint ${day}` }));

test('stored doors are cleaned, sorted and deduplicated', () => {
  assert.deepEqual(advent.cleanDays([3, '1', 3, 0, 25, 2.5, 'x', 24]), [1, 3, 24]);
  assert.deepEqual(advent.cleanDays(null), []);
});

test('the local date uses the reader\'s own calendar day', () => {
  assert.equal(advent.localDate(new Date(2026, 11, 5, 23, 59)), '2026-12-05');
  assert.equal(advent.localDate(new Date(2026, 0, 9, 0, 1)), '2026-01-09');
});

test('the progress line', () => {
  assert.equal(advent.progressText(0, 0), 'The first door opens on December 1.');
  assert.equal(advent.progressText(2, 5), '2 of 24 so far. 3 more doors are open and waiting for you.');
  assert.equal(advent.progressText(4, 5), '4 of 24 so far. 1 more door is open and waiting for you.');
  assert.equal(advent.progressText(5, 5), '5 of 24 so far, and you\'re up to date. The next door opens at midnight.');
  assert.equal(advent.progressText(24, 24), 'All 24 doors opened. That\'s the whole calendar.');
});

test('today\'s door on the card is the newest one that has started where the member is', () => {
  // Door 6 is open in UTC+14, but it is still December 5 for this member.
  const view = advent.cardView({ total: 24, doors: DOORS, opened_days: [1, 5] }, '2026-12-05');
  assert.equal(view.newest, 5);
  assert.equal(view.unlocked, 5);
  assert.equal(view.newestOpened, true);
  assert.equal(view.missed, 3);
  assert.equal(advent.cardView({ total: 24, doors: DOORS, opened_days: [] }, '2026-11-30'), null);
});

test('card wording', () => {
  const fresh = advent.cardView({ total: 24, doors: DOORS, opened_days: [1, 2] }, '2026-12-06');
  assert.deepEqual(advent.cardCopy(fresh), { title: 'Door 6 is open', summary: 'Hint 6. 2 of 24 opened so far.', action: 'Open today\'s door' });
  const behind = advent.cardView({ total: 24, doors: DOORS, opened_days: [6] }, '2026-12-06');
  assert.equal(advent.cardCopy(behind).action, 'Catch up');
  assert.equal(advent.cardCopy(behind).summary, '1 of 24 opened. 18 doors to go. 5 earlier doors are still shut.');
  const all = Array.from({ length: 24 }, (_, index) => index + 1);
  const done = advent.cardView({ total: 24, doors: all.map(day => ({ day, date: '2026-12-01', hint: '' })), opened_days: all }, '2026-12-24');
  assert.equal(advent.cardCopy(done).title, 'Every door opened');
});

test('the card only asks the server in November and December', () => {
  assert.equal(advent.cardSeason(new Date(2026, 11, 3)), true);
  assert.equal(advent.cardSeason(new Date(2026, 10, 20)), true);
  assert.equal(advent.cardSeason(new Date(2027, 0, 2)), false);
});
