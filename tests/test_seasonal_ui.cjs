// Seasonal hub (/halloween) and its dashboard card: plain-language progress, safe links, a per-year "hide" key.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const hub = require(path.join(__dirname, '../app/static/seasonal.js'));
const card = require(path.join(__dirname, '../app/static/seasonal-card.js'));

test('hub progress reads as plain words', () => {
  assert.match(hub.progressText({ total: 24, tracked: 0, done: 0 }), /^None of the 24 picks/);
  assert.equal(hub.progressText({ total: 24, tracked: 3, done: 1 }), "3 of 24 picks are in your library. You've finished 1.");
  assert.equal(hub.progressText({ total: 24, tracked: 24, done: 0 }), 'All 24 picks are in your library. Mark one finished when you get to it.');
  assert.equal(hub.percent({ total: 24, done: 6 }), 25);
  assert.equal(hub.percent({ total: 0, done: 0 }), 0);
});

test('adding a shelf says what changed', () => {
  assert.equal(hub.addedText({ added: [{ title: 'Hereditary' }], existing: [] }), 'Added “Hereditary” to your library.');
  assert.equal(hub.addedText({ added: [], existing: [{ title: 'Thriller' }] }), '“Thriller” is already in your library.');
  assert.equal(hub.addedText({ added: [{}, {}, {}, {}, {}], existing: [{}] }), 'Added 5 picks to your library. 1 was already there.');
  assert.equal(hub.addedText({ added: [], existing: [{}, {}] }), 'All of these are already in your library.');
});

test('the card invites, then tracks', () => {
  const base = { card: 'Twenty-four spooky picks.', total: 24, tracked: 0, done: 0, days_left: 12 };
  assert.equal(card.summaryText(base), 'Twenty-four spooky picks. 12 days left.');
  assert.equal(card.summaryText({ ...base, tracked: 4, done: 2, days_left: 1 }), '4 of 24 picks in your library, 2 finished. 1 day left.');
  assert.equal(card.summaryText({ ...base, tracked: 4 }), '4 of 24 picks in your library. 12 days left.');
});

test('the card only links to this site and hides per member, season and year', () => {
  assert.equal(card.safePath('/halloween'), '/halloween');
  assert.equal(card.safePath('//evil.example'), null);
  assert.equal(card.safePath('javascript:alert(1)'), null);
  global.getUser = () => ({ id: 7 });
  try {
    assert.equal(card.dismissKey({ season: 'halloween', year: 2026 }), 'omnitrackr_season_hidden_7_halloween_2026');
    assert.notEqual(card.dismissKey({ season: 'halloween', year: 2026 }), card.dismissKey({ season: 'halloween', year: 2027 }));
  } finally {
    delete global.getUser;
  }
});

test('progress and the card speak for whichever season is running', () => {
  assert.equal(hub.progressText({ total: 24, tracked: 0, done: 0 }, 'Holiday'),
    'None of the 24 picks are in your library yet. Add a shelf to start your Holiday list.');
  assert.match(hub.progressText({ total: 24, tracked: 0, done: 0 }), /start your seasonal list\.$/);
});
