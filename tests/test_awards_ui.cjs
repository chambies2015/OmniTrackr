// Awards ballots: the progress line, moving picks made before sign-up, and the dashboard card wording.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const awards = require(path.join(__dirname, '../app/static/awards.js'));

const OPEN = {
  show: true, state: 'open', slug: 'the-game-awards-2026', name: 'The Game Awards 2026', picked: 0, total: 30,
  days_left: 12, page: '/awards/the-game-awards-2026', shared: false, url: null,
};

test('the progress line counts picks and says when the ballot is full', () => {
  assert.equal(awards.countText(0, 30), '0 of 30 picked');
  assert.equal(awards.countText(7, 30), '7 of 30 picked');
  assert.equal(awards.countText(30, 30), 'All 30 picked');
  assert.equal(awards.countText(0, 0), '0 of 0 picked');
});

test('picks made before signing up fill only categories not picked since', () => {
  const draft = { goty: 'hades-ii', score: 'silksong', junk: 7 };
  assert.deepEqual(awards.mergeDraft(draft, { goty: 'bananza' }), { score: 'silksong' });
  assert.deepEqual(awards.mergeDraft(draft, {}), { goty: 'hades-ii', score: 'silksong' });
  assert.deepEqual(awards.mergeDraft(null, {}), {});
});

test('the card asks for picks, then for the rest, then offers sharing', () => {
  const empty = awards.cardCopy(OPEN);
  assert.equal(empty.action, 'Fill in your ballot');
  assert.match(empty.summary, /30 categories\. 12 days until picks lock/);
  assert.equal(empty.href, '/awards/the-game-awards-2026#ballot');

  const partial = awards.cardCopy({ ...OPEN, picked: 7, days_left: 1 });
  assert.equal(partial.title, '7 of 30 picked');
  assert.match(partial.summary, /^1 day until picks lock\./);
  assert.equal(partial.action, 'Finish your ballot');

  const full = awards.cardCopy({ ...OPEN, picked: 30, days_left: 0 });
  assert.equal(full.title, 'Your ballot is in');
  assert.match(full.summary, /^Picks lock today\./);
  assert.equal(full.action, 'Share your ballot');

  const shared = awards.cardCopy({ ...OPEN, picked: 30, shared: true, url: 'https://omnitrackr.xyz/ballot/abc' });
  assert.equal(shared.action, 'See your ballot');
  assert.equal(shared.href, 'https://omnitrackr.xyz/ballot/abc');
});

test('the home screen only asks about the card from November to March', () => {
  const month = index => new Date(Date.UTC(2026, index, 15));
  assert.deepEqual([10, 11, 0, 1, 2].map(index => awards.cardSeason(month(index))), [true, true, true, true, true]);
  assert.deepEqual([3, 6, 9].map(index => awards.cardSeason(month(index))), [false, false, false]);
});

test('after the show the card gives the score', () => {
  const live = awards.cardCopy({ ...OPEN, state: 'locked', picked: 20, correct: 3, judged: 5, decided: 8 });
  assert.equal(live.title, 'You called 3 of 5');
  assert.match(live.summary, /8 of 30 winners announced so far/);
  const done = awards.cardCopy({ ...OPEN, state: 'results', picked: 20, correct: 11, judged: 20, decided: 30 });
  assert.equal(done.title, 'You called 11 of 20');
  assert.match(done.summary, /Every winner is in/);
  assert.equal(done.action, 'See how it went');
});
