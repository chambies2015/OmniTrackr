// Break planner (/break) and its home card: day lists, time words, and what the card says in each state.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const page = require(path.join(__dirname, '../app/static/break-plan.js'));
const card = require(path.join(__dirname, '../app/static/break-home.js'));

test('days between two dates are listed in order and capped', () => {
  assert.deepEqual(page.daysBetween('2026-11-26', '2026-11-29'), ['2026-11-26', '2026-11-27', '2026-11-28', '2026-11-29']);
  assert.deepEqual(page.daysBetween('2026-12-31', '2027-01-01'), ['2026-12-31', '2027-01-01']);
  assert.deepEqual(page.daysBetween('2026-11-29', '2026-11-26'), []);
  assert.deepEqual(page.daysBetween('nope', '2026-11-26'), []);
  assert.equal(page.daysBetween('2026-11-01', '2026-12-31').length, 16);
});

test('time reads in plain words', () => {
  assert.equal(page.hoursWords(0), 'Busy');
  assert.equal(page.hoursWords(45), '45 min');
  assert.equal(page.hoursWords(180), '3 hours');
  assert.equal(page.hoursWords(90), '1.5 hours');
  assert.equal(page.lengthWords(133), '2h 13m');
  assert.equal(page.lengthWords(240), '4h');
});

test('a light day starts at an hour and the bar never runs past full', () => {
  const minutes = page.dayDefaults(['2026-11-26', '2026-11-27'], 180, ['2026-11-26']);
  assert.deepEqual(minutes, { '2026-11-26': 60, '2026-11-27': 180 });
  assert.equal(page.dayDefaults(['2026-11-26'], 30, ['2026-11-26'])['2026-11-26'], 30);
  assert.equal(page.fillShare(90, 180), 50);
  assert.equal(page.fillShare(300, 180), 100);
  assert.equal(page.fillShare(20, 0), 100);
});

test('the plan header says where the break is', () => {
  assert.equal(page.phaseLine({ phase: 'upcoming', starts_on: '2026-11-26', today: '2026-11-25' }), 'Starts tomorrow');
  assert.equal(page.phaseLine({ phase: 'during', day_number: 2, day_count: 4 }), 'Day 2 of 4');
  assert.equal(page.phaseLine({ phase: 'after' }), 'All done');
});

test('home card words for each state', () => {
  const offer = card.headline({ state: 'offer', short: 'Thanksgiving', span: 'Thu Nov 26 to Sun Nov 29', starts_in: 3 });
  assert.equal(offer.title, 'Got Thanksgiving off?');
  assert.match(offer.summary, /^It's Thu Nov 26 to Sun Nov 29\./);
  assert.equal(card.headline({ state: 'offer', short: 'the holidays', starts_in: 1 }).title, 'Got time off for the holidays?');

  const upcoming = card.headline({ state: 'upcoming', name: 'Thanksgiving weekend', span: 'Thu Nov 26 to Sun Nov 29', starts_in: 3,
    day_count: 4, totals: { titles: 4, hours: '9.5 hours' } });
  assert.equal(upcoming.title, 'Thanksgiving weekend starts in 3 days');

  const during = card.headline({ state: 'during', name: 'Long weekend', day_number: 1, day_count: 4,
    today_items: [{ done: true }, { done: false }], totals: { done: 1, stretches: 6 } });
  assert.equal(during.title, 'On your break today');
  assert.equal(during.summary, '1 of 6 ticked off so far.');
  const doneToday = card.headline({ state: 'during', name: 'x', day_number: 2, day_count: 4, today_items: [{ done: true }], totals: {} });
  assert.equal(doneToday.title, "Today's done");

  const after = card.headline({ state: 'after', name: "Weekend at my parents'", span: 'Wed Nov 18 to Sat Nov 21',
    totals: { done: 5, stretches: 5, finished: 2, done_hours: '14.5 hours' } });
  assert.equal(after.title, 'How your break went');
  assert.equal(after.summary, 'You ticked off 5 of 5 and finished 2 titles, about 14.5 hours.');
  assert.equal(card.headline({ state: 'after', name: 'x', totals: { done: 0 } }).title, 'Your break is over');
});

test('a game stretch already says how long it is', () => {
  assert.equal(card.itemLine({ unit: 'episode', label: 'Episodes 2–3', length: '1h 50m' }), 'Episodes 2–3 · 1h 50m');
  assert.equal(card.itemLine({ unit: 'block', label: 'Play for about 2 hours', length: '2h' }), 'Play for about 2 hours');
});
