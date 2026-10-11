// Dashboard monthly challenge: plain-language progress and a per-month "not this month" key.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const challenge = require(path.join(__dirname, '../app/static/challenges.js'));

const steps = [{ done: true }, { done: false }, { done: false }];

test('days left reads as plain words', () => {
  assert.equal(challenge.daysLeftText(12), '12 days left');
  assert.equal(challenge.daysLeftText(1), 'Last day');
  assert.equal(challenge.daysLeftText(0), 'Ends today');
});

test('the summary invites, then tracks, then celebrates', () => {
  const base = { month_name: 'October', steps, done_steps: 0, days_left: 9, joined: false, completion: null };
  assert.equal(challenge.summaryText(base), '3 small steps for October. Progress fills in from what you mark finished this month.');
  assert.match(challenge.summaryText({ ...base, done_steps: 1 }), /already 1 of 3 steps in/);
  assert.equal(challenge.summaryText({ ...base, joined: true, done_steps: 1 }), '1 of 3 steps done · 9 days left');
  assert.equal(challenge.summaryText({ ...base, joined: true, completion: { celebrate: true } }), 'Challenge complete. 9 days left in October.');
});

test('dismissing hides only this month for this member', () => {
  global.getUser = () => ({ id: 7 });
  try {
    assert.equal(challenge.dismissKey('2026-10'), 'omnitrackr_challenge_hidden_7_2026-10');
    assert.notEqual(challenge.dismissKey('2026-10'), challenge.dismissKey('2026-11'));
  } finally {
    delete global.getUser;
  }
});
