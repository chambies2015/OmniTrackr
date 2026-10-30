const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/visit.js'), 'utf8');

function run({ visibility = 'visible', webdriver = false, search = '?utm_source=Reddit&x=1', referrer = 'https://www.google.com/' } = {}) {
  const beacons = [];
  const timers = [];
  const listeners = {};
  const document = {
    visibilityState: visibility,
    referrer,
    addEventListener: (type, fn) => { listeners[type] = fn; },
  };
  const context = vm.createContext({
    URLSearchParams,
    JSON,
    document,
    window: { location: { pathname: '/reviews', search } },
    navigator: { webdriver, sendBeacon: (url, blob) => { beacons.push({ url, body: JSON.parse(blob.text) }); return true; } },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    setTimeout: fn => { timers.push(fn); return timers.length; },
    clearTimeout: () => {},
  });
  vm.runInContext(source, context);
  return { beacons, timers, listeners, document, flush: () => timers.splice(0).forEach(fn => fn()) };
}

test('a shown page reports its path, referrer and campaign tag once', () => {
  const page = run();
  assert.equal(page.beacons.length, 0); // waits until the tab has been shown a moment
  page.flush();
  assert.deepEqual(page.beacons, [{ url: '/api/visit', body: { path: '/reviews', referrer: 'https://www.google.com/', utm: 'Reddit' } }]);
  page.listeners.visibilitychange();
  page.flush();
  assert.equal(page.beacons.length, 1);
});

test('a background tab reports only once it is shown', () => {
  const page = run({ visibility: 'hidden' });
  page.flush();
  assert.equal(page.beacons.length, 0);
  page.document.visibilityState = 'visible';
  page.listeners.visibilitychange();
  page.flush();
  assert.equal(page.beacons.length, 1);
});

test('a browser run by automation never reports', () => {
  const page = run({ webdriver: true });
  page.flush();
  assert.equal(page.beacons.length, 0);
  assert.equal(page.listeners.visibilitychange, undefined);
});

test('Site stats starts the funnel from every homepage load when people were not counted yet', () => {
  const { funnelSteps, trafficSet } = require('../app/static/site-stats.js');
  const funnel = {
    steps: [{ event: 'landing_seen', label: 'Homepage seen by a person', count: 0 }, { event: 'signup_form_opened', label: 'Started', count: 3 }],
    raw: [{ event: 'landing_viewed', label: 'Homepage loads, all requests', count: 900 }],
  };
  assert.deepEqual(funnelSteps(funnel).map(step => [step.event, step.count]), [['landing_viewed', 900], ['signup_form_opened', 3]]);
  funnel.steps[0].count = 40;
  assert.equal(funnelSteps(funnel)[0].event, 'landing_seen');
  const traffic = { totals: { views: 9 }, human: { totals: { views: 2 }, tracking_since: '2026-10-30' } };
  assert.equal(trafficSet(traffic, 'human').totals.views, 2);
  assert.equal(trafficSet(traffic, 'all').totals.views, 9);
});
