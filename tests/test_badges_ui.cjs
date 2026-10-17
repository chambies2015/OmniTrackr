// Dashboard trophy case: summary wording, progress lines, the celebration and tier classes.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const badges = require(path.join(__dirname, '../app/static/badges.js'));

const row = (key, name, tier, extra = {}) => ({
  key, name, tier, tier_name: ['', 'Bronze', 'Silver', 'Gold'][tier] || null, counts: 'books read', count: 3,
  next_target: tier < 3 ? 5 : null, ...extra,
});

test('the summary counts tiers, badges and golds', () => {
  const data = { badges: [row('a', 'A', 3), row('b', 'B', 1), row('c', 'C', 0)], earned_levels: 4, total_levels: 9, earned_badges: 2, gold: 1 };
  assert.equal(badges.summaryText(data), '4 of 9 badge tiers earned across 2 badges, 1 gold.');
  assert.equal(badges.summaryText({ ...data, earned_levels: 1, earned_badges: 1, gold: 0 }), '1 of 9 badge tiers earned across 1 badge.');
  assert.match(badges.summaryText({ ...data, earned_levels: 0 }), /^3 badges to earn/);
});

test('progress reads as a count toward the next tier', () => {
  assert.equal(badges.progressText(row('a', 'A', 1)), '3 of 5 books read');
  assert.equal(badges.progressText(row('a', 'A', 3, { count: 120 })), '120 books read · gold');
});

test('the celebration names one, a few, or counts many', () => {
  const data = { badges: [row('a', 'Bookworm', 2), row('b', 'Critic', 1), row('c', 'Rater', 1), row('d', 'Regular', 1)] };
  assert.equal(badges.celebrationText({ ...data, celebrate: ['a'] }), 'New badge: Bookworm, silver!');
  assert.equal(badges.celebrationText({ ...data, celebrate: ['a', 'b'] }), 'New badges: Bookworm (silver) and Critic (bronze)!');
  assert.equal(badges.celebrationText({ ...data, celebrate: ['a', 'b', 'c', 'd'] }), 'You earned 4 badges. Nicely done!');
  assert.equal(badges.celebrationText({ ...data, celebrate: [] }), '');
});

test('tiers map to medal classes and stay in range', () => {
  assert.deepEqual([0, 1, 2, 3, 7, -1, undefined].map(badges.tierClass), ['locked', 'bronze', 'silver', 'gold', 'gold', 'locked', 'locked']);
});
