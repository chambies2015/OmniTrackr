// Nov 12 sweep: what Google Analytics is told about the page, and names in calendar files.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ANALYTICS = fs.readFileSync(path.join(__dirname, '../app/static/analytics.js'), 'utf8');

// Runs analytics.js on a page at `href` and returns what it queued for gtag.js.
function visit(href, { publicShell = true, doNotTrack = null } = {}) {
  const location = href === null ? { origin: 'https://omnitrackr.xyz', pathname: '/', href: 'not an address' } : new URL(href);
  const window = { location, addEventListener() {}, setTimeout() {} };
  const document = {
    readyState: 'loading',
    documentElement: { hasAttribute: name => publicShell && name === 'data-public-shell' },
    getElementById: () => null,
  };
  vm.runInNewContext(ANALYTICS, { window, document, navigator: { doNotTrack }, URL });
  const queued = (window.dataLayer || []).map(entry => Array.from(entry));
  return queued.find(entry => entry[0] === 'config') || null;
}

test('a password reset link is not passed on to Analytics', () => {
  const config = visit('https://omnitrackr.xyz/?reset_token=abc.def-ghi_123&utm_source=mail');
  assert.equal(config[2].page_location, 'https://omnitrackr.xyz/?utm_source=mail');
  assert.ok(!JSON.stringify(config).includes('abc.def-ghi_123'));
});

test('confirmation and email change links lose their key too', () => {
  assert.equal(visit('https://omnitrackr.xyz/?token=eyJ.x.y&email_verified=true')[2].page_location,
    'https://omnitrackr.xyz/?email_verified=true');
  assert.equal(visit('https://omnitrackr.xyz/?email_change_token=eyJ.x.y&email_change=true')[2].page_location,
    'https://omnitrackr.xyz/?email_change=true');
  // The same key twice, or with another spelling of the address, is still removed.
  assert.equal(visit('https://omnitrackr.xyz/?token=one&token=two#login')[2].page_location, 'https://omnitrackr.xyz/#login');
});

test('an ordinary visit is reported as it is', () => {
  assert.equal(visit('https://omnitrackr.xyz/')[2].page_location, 'https://omnitrackr.xyz/');
  assert.equal(visit('https://omnitrackr.xyz/?utm_source=reddit&start=demo#signup')[2].page_location,
    'https://omnitrackr.xyz/?utm_source=reddit&start=demo#signup');
  const settings = visit('https://omnitrackr.xyz/')[2];
  assert.equal(settings.anonymize_ip, true);
  assert.equal(settings.allow_google_signals, false);
});

test('an address that cannot be read is reported as the path alone', () => {
  assert.equal(visit(null)[2].page_location, 'https://omnitrackr.xyz/');
});

test('nothing is queued on the dashboard or when the browser asks not to be tracked', () => {
  assert.equal(visit('https://omnitrackr.xyz/?reset_token=abc', { publicShell: false }), null);
  assert.equal(visit('https://omnitrackr.xyz/?reset_token=abc', { doNotTrack: '1' }), null);
});

test('a plan name from a link cannot start a new line in the calendar file', () => {
  global.document = { readyState: 'complete', addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
  delete require.cache[require.resolve('../app/static/binge-calculator.js')];
  const api = require('../app/static/binge-calculator.js');
  const date = api.parseIso('2026-12-31');
  for (const breakAt of ['\r', '\n', '\r\n']) {
    const file = api.calendarFile(`Dune${breakAt}ATTACH:https://example.com/x`, date, `one${breakAt}two`, 'https://omnitrackr.xyz/binge-calculator');
    const lines = file.split(/\r\n|\r|\n/);
    assert.equal(lines.length, 14, JSON.stringify(breakAt));
    assert.ok(lines.includes('SUMMARY:Finish Dune\\nATTACH:https://example.com/x'));
    assert.ok(lines.includes('DESCRIPTION:one\\ntwo'));
    assert.ok(!lines.some(line => line.startsWith('ATTACH')));
  }
});
