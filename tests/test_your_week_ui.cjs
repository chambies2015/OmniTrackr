// "Your week" on the home screen (your-week.js): the headline and summary copy for each state.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null } };
  global.window = { addEventListener() {}, location: { hash: '' } };
  const file = path.join(__dirname, '..', 'app', 'static', 'your-week.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const DAYS = goal => ({ kind: 'days', target: goal });
const FINISH = { kind: 'finish', target: 1 };

// Seven days, Monday first, with `today` as an index; `lit` lists the logged days.
function week(today, lit = []) {
  return Array.from({ length: 7 }, (_, index) => ({
    logged: lit.includes(index), today: index === today, future: index > today,
  }));
}

test('setup names the member’s own weeks only when there are at least two', () => {
  const yw = load();
  assert.equal(yw.headline({ status: 'setup', active_weeks: 5 }), 'You logged something in 5 of the last 8 weeks');
  assert.equal(yw.headline({ status: 'setup', active_weeks: 1 }), 'Make it a weekly thing');
  assert.match(yw.summary({ status: 'setup' }), /Pick a pace/);
});

test('a kept week says how long the run is, or that it is the first', () => {
  const yw = load();
  assert.equal(yw.headline({ status: 'kept', goal: DAYS(3) }), 'Week kept');
  assert.equal(yw.summary({ status: 'kept', goal: DAYS(3), run: 4 }), 'That’s 4 weeks in a row. Anything else you log this week is a bonus.');
  assert.equal(yw.summary({ status: 'kept', goal: DAYS(3), run: 1 }), 'That’s your first one. Anything else you log this week is a bonus.');
});

test('an open week counts days and says what keeping it would make', () => {
  const yw = load();
  const card = { status: 'open', goal: DAYS(3), logged_days: 1, needed: 2, run_before: 2, days: week(2, [0]) };
  assert.equal(yw.headline(card), '1 of 3 days so far');
  assert.equal(yw.daysOpen(card), 5);
  assert.equal(yw.summary(card), '2 days with something logged keep your week, and 5 are still open. Keep it and that’s 3 in a row.');
  const nothing = { ...card, logged_days: 0, needed: 3, run_before: 0, days: week(2) };
  assert.equal(yw.headline(nothing), 'Nothing logged yet this week');
  assert.ok(!yw.summary(nothing).includes('in a row'));
});

test('one more day, the once-a-week pace, and Sunday', () => {
  const yw = load();
  assert.equal(yw.summary({ status: 'open', goal: DAYS(3), needed: 1, run_before: 0, days: week(3, [0, 1]) }), 'One more day keeps your week.');
  assert.match(yw.summary({ status: 'open', goal: DAYS(1), needed: 1, run_before: 0, days: week(1) }), /^Log anything by Sunday night/);
  assert.equal(yw.summary({ status: 'open', goal: DAYS(3), needed: 1, run_before: 1, days: week(6, [0, 3]) }),
    'Last day of the week. Log one thing today and it’s kept. Keep it and that’s 2 in a row.');
});

test('a week out of reach offers the week off only when the card allows it', () => {
  const yw = load();
  const card = { status: 'open', goal: DAYS(5), needed: 4, run_before: 2, days: week(5, [1]) };
  assert.match(yw.summary({ ...card, can_rest: true }), /take it as a week off and keep your run/);
  assert.match(yw.summary({ ...card, can_rest: false }), /next week starts fresh on Monday/);
});

test('the finish pace and a week off', () => {
  const yw = load();
  const finish = { status: 'open', goal: FINISH, needed: 1, run_before: 0, days: week(2) };
  assert.equal(yw.headline(finish), 'Nothing finished yet this week');
  assert.match(yw.summary(finish), /^Finish one thing by Sunday/);
  assert.match(yw.summary({ ...finish, days: week(6) }), /^Last day of the week. Finish one thing today/);
  assert.equal(yw.headline({ status: 'rest', goal: DAYS(3) }), 'Taking this week off');
  assert.equal(yw.summary({ status: 'rest', goal: DAYS(3), run_before: 3 }), 'Your run of 3 weeks waits for you. It picks up again on Monday.');
});
