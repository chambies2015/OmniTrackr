// Helpers behind the dashboard support note and the /supporters page line.
const test = require('node:test');
const assert = require('node:assert');

const ask = require('../app/static/support-ask.js');
const page = require('../app/static/supporters-page.js');

test('only https ko-fi links are used for the note button', () => {
  assert.equal(ask.safeKofi('https://ko-fi.com/omnitrackr'), 'https://ko-fi.com/omnitrackr');
  assert.equal(ask.safeKofi('javascript:alert(1)'), null);
  assert.equal(ask.safeKofi('https://ko-fi.com.evil.example/'), null);
  assert.equal(ask.safeKofi('http://ko-fi.com/omnitrackr'), null);
});

test('meter width stays between 0 and 100', () => {
  assert.equal(ask.meterWidth(42.4), 42);
  assert.equal(ask.meterWidth(180), 100);
  assert.equal(ask.meterWidth('nope'), 0);
});

test('visit source prefers ?from=, then this site, then outside', () => {
  assert.equal(page.visitSource('?from=email', 'https://elsewhere.example/', 'https://omnitrackr.xyz'), 'email');
  assert.equal(page.visitSource('?from=<b>', 'https://omnitrackr.xyz/faq', 'https://omnitrackr.xyz'), 'site');
  assert.equal(page.visitSource('', 'https://reddit.com/r/x', 'https://omnitrackr.xyz'), 'outside');
  assert.equal(page.visitSource('', '', 'https://omnitrackr.xyz'), 'outside');
});

test('member line on /supporters', () => {
  assert.equal(page.memberLine({ titles: 612, days: 140, since: 'March 2025' }),
    "Since March 2025, you've tracked 612 titles on OmniTrackr and opened it on 140 different days.");
  assert.equal(page.memberLine({ titles: 12, days: 2 }), "You've tracked 12 titles on OmniTrackr.");
  assert.equal(page.memberLine({ titles: 2, days: 2 }), '');
  assert.match(page.memberLine({ supporter: true }), /already support/);
  assert.equal(page.memberLine(null), '');
});
