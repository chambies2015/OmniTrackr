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
  assert.equal(nodes.yearInReviewBannerLink.href, '/year-in-review/2026#story');
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

async function runSoFar(isoDate, answer, stored = {}) {
  const ids = ['yearSoFar', 'yearSoFarTitle', 'yearSoFarFinished', 'yearSoFarFinishedLabel', 'yearSoFarHoursTile',
    'yearSoFarHours', 'yearSoFarHoursLabel', 'yearSoFarTasteTile', 'yearSoFarTaste', 'yearSoFarTasteLabel',
    'yearSoFarHint', 'yearSoFarMeter', 'yearSoFarDaysLeft', 'yearSoFarNote', 'yearSoFarLink', 'yearSoFarDismiss'];
  const nodes = { yearInReviewBanner: { hidden: true } };
  ids.forEach(id => {
    nodes[id] = { hidden: true, textContent: '', href: '/year-in-review', dataset: {}, attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; } };
  });
  nodes.yearSoFarMeterFill = { style: {} };
  nodes.yearSoFarDismiss.addEventListener = (type, handler) => { nodes.yearSoFarDismiss.click = handler; };
  const requests = [];
  const RealDate = Date;
  class FixedDate extends RealDate { constructor(...args) { super(...(args.length ? args : [isoDate])); } }
  const window = {};
  const context = {
    Date: FixedDate,
    window,
    localStorage: { getItem: key => stored[key] ?? null, setItem: (key, value) => { stored[key] = value; } },
    document: { getElementById: id => nodes[id] || null },
    fetch: async url => { requests.push(url); return { ok: true, json: async () => answer }; },
  };
  vm.runInNewContext(source, context);
  for (let i = 0; i < 4; i += 1) await new Promise(resolve => setImmediate(resolve));
  return { nodes, requests, window, stored };
}

const SO_FAR = {
  year: 2026, finished: 23, hours: 61, genre: 'Fantasy', top_shelf: { category: 'books', noun: 'books', finished: 12 },
  days_left: 47, since: 'September', recap_opens: 'December 1', hint: '4 books to go and you reach your goal of 20.',
  url: '/year-in-review/2026?from=card',
};

test('November shows the year so far card', async () => {
  const { nodes, requests, window } = await runSoFar('2026-11-15T12:00:00', SO_FAR);
  assert.deepEqual(requests, ['/api/year-in-review-so-far']);
  assert.equal(nodes.yearSoFar.hidden, false);
  assert.equal(nodes.yearSoFarTitle.textContent, 'Your 2026 so far');
  assert.equal(nodes.yearSoFarFinished.textContent, '23');
  assert.equal(nodes.yearSoFarHours.textContent, '~61');
  assert.equal(nodes.yearSoFarTaste.textContent, 'Fantasy');
  assert.equal(nodes.yearSoFarDaysLeft.textContent, '47 days left');
  assert.equal(nodes.yearSoFarMeterFill.style.width, '87%');
  assert.equal(nodes.yearSoFarHint.textContent, SO_FAR.hint);
  assert.match(nodes.yearSoFarNote.textContent, /opens December 1.*Counting from September/);
  assert.equal(nodes.yearSoFarLink.href, '/year-in-review/2026?from=card');
  assert.equal(typeof window.refreshYearSoFar, 'function');
  assert.equal(typeof window.resetYearSoFar, 'function');
});

test('No genre falls back to the shelf; an odd link falls back to the year page', async () => {
  const { nodes } = await runSoFar('2026-11-15T12:00:00', { ...SO_FAR, genre: null, hours: null, url: 'https://evil.example/' });
  assert.equal(nodes.yearSoFarTaste.textContent, 'Books');
  assert.equal(nodes.yearSoFarTasteLabel.textContent, 'most finished');
  assert.equal(nodes.yearSoFarHoursTile.hidden, true);
  assert.equal(nodes.yearSoFarLink.href, '/year-in-review/2026');
});

test('Hide until December sticks for that member and year', async () => {
  const first = await runSoFar('2026-11-15T12:00:00', SO_FAR);
  first.nodes.yearSoFarDismiss.click();
  assert.equal(first.nodes.yearSoFar.hidden, true);
  const again = await runSoFar('2026-11-16T12:00:00', SO_FAR, first.stored);
  assert.equal(again.nodes.yearSoFar.hidden, true);
});

test('Outside November the card asks for nothing', async () => {
  for (const day of ['2026-10-31T12:00:00', '2026-12-02T12:00:00']) {
    const { nodes, requests } = await runSoFar(day, SO_FAR);
    assert.ok(!requests.includes('/api/year-in-review-so-far'));
    assert.equal(nodes.yearSoFar.hidden, true);
  }
});

test('An empty answer keeps the card hidden', async () => {
  const { nodes } = await runSoFar('2026-11-15T12:00:00', { year: null });
  assert.equal(nodes.yearSoFar.hidden, true);
});
