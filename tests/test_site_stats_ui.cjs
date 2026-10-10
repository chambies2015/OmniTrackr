// Site stats page helpers: report text for Claude, axis maths, deltas.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const stats = require(path.join(__dirname, '../app/static/site-stats.js'));

function sample() {
  return {
    generated_at: '2026-09-29T12:00:00Z', days: 30, viewer: 'dan',
    members: { new_in_range: 12, new_previous_range: 8, active_24_hours: 3, active_7_days: 9, active_30_days: 20, new_today: 1 },
    traffic: {
      tracking_since: '2026-09-29', enabled: true, today: { views: 4, visitors: 2 },
      totals: { views: 400, visitors: 150 }, previous_totals: { views: 0, visitors: 0 },
      series: [], top_pages: [{ key: '/release-radar', count: 120 }], sources: [{ key: 'google.com', count: 60 }],
      devices: [{ key: 'mobile', count: 200 }], audience: [{ key: 'guest', count: 300 }],
    },
    popular_titles: [{ title: 'Dune', category: 'Books', members: 3 }],
    insights: {
      users: { total: 40, verified: 35 },
      activation: [{ label: 'Accounts created', count: 40 }, { label: 'Email verified', count: 35 }],
      content: { total_items: 900, public_reviews: 22, custom_items: 5, categories: [{ label: 'Movies', total: 400 }] },
      moderation: { approved: 4, views: 88, reports: 1, review_reports: 0 },
      engagement: { friendships: 6, activity_entries_30_days: 70 },
    },
    system: {
      database: 'PostgreSQL',
      integrations: [{ name: 'OMDb (movie/TV posters)', configured: true }, { name: 'Amazon Associates tag', configured: false }],
      release_radar: [{ category: 'Games', items: 14, error: null }],
    },
  };
}

test('the copied report covers traffic, members, content and health in plain text', () => {
  const report = stats.buildReport(sample());
  assert.match(report, /last 30 days/);
  assert.match(report, /150 visitors, 400 page views/);
  assert.match(report, /\/release-radar \(120\)/);
  assert.match(report, /google\.com \(60\)/);
  assert.match(report, /40 total, 35 verified, 12 new \(previous 30 days: 8\)/);
  assert.match(report, /Accounts created 40 → Email verified 35/);
  assert.match(report, /900 titles \(Movies 400\)/);
  assert.match(report, /Dune \[Books\] 3/);
  assert.match(report, /Amazon Associates tag: NOT SET/);
  assert.match(report, /Games 14 titles/);
  assert.doesNotMatch(report, /undefined|NaN/);
});

test('empty sections read as "none yet" instead of blank', () => {
  const data = sample();
  data.traffic.top_pages = [];
  data.popular_titles = [];
  const report = stats.buildReport(data);
  assert.match(report, /Top pages: none yet/);
  assert.match(report, /Most tracked: none yet/);
});

test('axis maximum rounds up to a readable step', () => {
  assert.equal(stats.niceMax(0), 4);
  assert.equal(stats.niceMax(3), 4);
  assert.equal(stats.niceMax(7), 8);
  assert.equal(stats.niceMax(173), 200);
  assert.ok(stats.niceMax(1234) >= 1234);
});

test('period-over-period change handles a zero baseline', () => {
  assert.deepEqual(stats.delta(150, 100), { text: '+50%', up: true });
  assert.deepEqual(stats.delta(50, 100), { text: '-50%', up: false });
  assert.deepEqual(stats.delta(5, 0), { text: 'new', up: true });
  assert.equal(stats.delta(0, 0), null);
  assert.equal(stats.percent(1, 3), 33.3);
  assert.equal(stats.percent(1, 0), 0);
});

test('the copied report lists the growth features with their numbers', () => {
  const data = sample();
  assert.doesNotMatch(stats.buildReport(data), /Growth features/);
  data.growth = {
    invites: { links: 9, new_links: 4, signups: 3, friends_made: 2, awaiting_verification: 1 },
    supporters: { active: 5, monthly: 2, all_time: 7, new: 3, payments: 6, unlinked_payments: 1 },
    weekly_email: { subscribers: 30, new: 8 },
    takes: { asked: 11, answered: 4 },
  };
  const report = stats.buildReport(data);
  assert.match(report, /Growth features \(last 30 days; "now" rows are current totals\):/);
  assert.match(report, /- Friend invite links: Sign-ups through an invite 3; Friendships made by invites 2;/);
  assert.match(report, /- Ko-fi supporters: Active supporters \(now\) 5; Monthly members \(now\) 2;/);
  assert.match(report, /- Weekly email: Subscribers \(now\) 30; New opt-ins 8/);
  assert.match(report, /- Ask a friend for their take: Links shared 11; Friends who answered 4/);
  assert.doesNotMatch(report, /undefined|NaN/);
  assert.equal(stats.growthRows(data.growth).growthInvites.length, 5);
});
