// Dashboard yearly goals: pace wording, ring maths and which categories can still get a goal.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const goals = require(path.join(__dirname, '../app/static/goals.js'));

test('pace reads as plain words', () => {
  assert.equal(goals.paceText({ pace: { status: 'done', difference: 0 } }), 'Goal reached');
  assert.equal(goals.paceText({ pace: { status: 'ahead', difference: 2 } }), '2 ahead of pace');
  assert.equal(goals.paceText({ pace: { status: 'behind', difference: 3 } }), '3 behind pace');
  assert.equal(goals.paceText({ pace: { status: 'on_track', difference: 0 } }), 'On pace');
  assert.equal(goals.paceText({ pace: { status: 'not_started', difference: 0 } }), 'Starts January 1');
  assert.equal(goals.paceText({}), '');
});

test('the ring fills with the percentage and never overflows', () => {
  assert.equal(goals.ringOffset(0), goals.RING_LENGTH);
  assert.equal(goals.ringOffset(100), 0);
  assert.equal(goals.ringOffset(150), 0);
  assert.equal(goals.ringOffset(-5), goals.RING_LENGTH);
  assert.ok(Math.abs(goals.ringOffset(50) - goals.RING_LENGTH / 2) < 1e-9);
});

test('a category with a goal is offered only while editing that goal', () => {
  const data = {
    goals: [{ category: 'books' }],
    categories: [{ key: 'all', noun: 'titles' }, { key: 'books', noun: 'books' }, { key: 'movies', noun: 'movies' }],
  };
  assert.deepEqual(goals.openCategories(data, null).map(item => item.key), ['all', 'movies']);
  assert.deepEqual(goals.openCategories(data, 'books').map(item => item.key), ['all', 'books', 'movies']);
});
