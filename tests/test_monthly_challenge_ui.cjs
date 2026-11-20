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

test('a revisit step that is not done offers to log one in the Journal', () => {
  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const open = challenge.stepItem({ kind: 'revisit', label: 'Go back to something you love', done: false, count: 0, target: 1 });
    const button = open.children.find(node => node.tag === 'button');
    assert.ok(button);
    assert.equal(button.textContent, 'Log a revisit');
    assert.equal(button.type, 'button');
    assert.equal(button.dataset.challengeAction, 'log-revisit');
    const done = challenge.stepItem({ kind: 'revisit', label: 'Go back to something you love', done: true, count: 1, target: 1 });
    assert.equal(done.children.some(node => node.tag === 'button'), false);
    const other = challenge.stepItem({ kind: 'reflect', label: 'Write down what you love about one', done: false, count: 0, target: 1 });
    assert.equal(other.children.some(node => node.tag === 'button'), false);
  } finally {
    delete global.document;
  }
});

test('a stretch step lists the formats that count for this member until it is done', () => {
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: ['manga', 'podcasts', 'audiobooks'] }),
    'Counts for you: manga, podcasts or audiobooks');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: ['audiobooks'] }), 'Counts for you: audiobooks');
  const all = ['movies', 'TV', 'anime', 'games', 'albums', 'books', 'manga', 'podcasts', 'audiobooks'];
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: all }), 'Any format counts for you');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: true, formats: ['manga'] }), '');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false }), '');
  assert.equal(challenge.stretchHint({ kind: 'reflect', done: false, formats: ['manga'] }), '');
});
