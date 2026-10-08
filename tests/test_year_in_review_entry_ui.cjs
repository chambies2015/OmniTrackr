const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/year-in-review-entry.js'), 'utf8');

async function run(isoDate, season) {
  const nodes = {
    yearInReviewBanner: { hidden: true },
    yearInReviewBannerLink: { href: '/year-in-review' },
    yearInReviewBannerTitle: { textContent: '' },
  };
  const requests = [];
  const RealDate = Date;
  class FixedDate extends RealDate { constructor(...args) { super(...(args.length ? args : [isoDate])); } }
  const context = {
    Date: FixedDate,
    document: { getElementById: id => nodes[id] || null },
    fetch: async url => { requests.push(url); return { ok: true, json: async () => season }; },
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  return { nodes, requests };
}

test('December shows the banner for this year', async () => {
  const { nodes, requests } = await run('2026-12-03T12:00:00', { year: 2026, url: '/year-in-review/2026' });
  assert.equal(requests.length, 1);
  assert.equal(nodes.yearInReviewBanner.hidden, false);
  assert.equal(nodes.yearInReviewBannerLink.href, '/year-in-review/2026');
  assert.match(nodes.yearInReviewBannerTitle.textContent, /2026/);
});

test('Outside December and January nothing is requested or shown', async () => {
  const { nodes, requests } = await run('2026-10-08T12:00:00', { year: null, url: null });
  assert.equal(requests.length, 0);
  assert.equal(nodes.yearInReviewBanner.hidden, true);
});

test('A signed-out or empty answer keeps the banner hidden', async () => {
  const { nodes } = await run('2027-01-10T12:00:00', { year: null, url: null });
  assert.equal(nodes.yearInReviewBanner.hidden, true);
});
