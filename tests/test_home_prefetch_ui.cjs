// Home start-up requests (home-prefetch.js): each answer handed out once, writes drop the rest,
// errors go back to the network, and addresses nobody asks for are left out for a week.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SOURCE = fs.readFileSync(path.join(__dirname, '../app/static/home-prefetch.js'), 'utf8');
const ORIGIN = 'https://omnitrackr.xyz';

function setup({ storage = { omnitrackr_token: 'tok' }, pathname = '/', status = () => 200 } = {}) {
  const sent = [];
  const timers = [];
  const listeners = {};
  let clock = Date.UTC(2026, 10, 23, 18, 0, 0);
  const fetch = (input, init) => {
    sent.push({ url: String(input), init });
    const code = status(String(input), sent.length);
    return Promise.resolve({ ok: code >= 200 && code < 300, status: code, url: String(input), n: sent.length });
  };
  const window = {
    location: { pathname, href: `${ORIGIN}${pathname}`, origin: ORIGIN },
    localStorage: {
      getItem: key => (key in storage ? storage[key] : null),
      setItem: (key, value) => { storage[key] = String(value); },
    },
    fetch,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    addEventListener: (type, fn) => { listeners[type] = fn; },
  };
  const context = {
    window, URL, Promise, Map, Set, JSON, Error, String, Boolean, Array, Math,
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : [clock])); }
      static now() { return clock; }
    },
  };
  vm.runInNewContext(SOURCE, context);
  return {
    window, sent, storage, timers, listeners,
    advance: ms => { clock += ms; },
    settle: () => listeners.pagehide && listeners.pagehide(),
  };
}

const PICKS = '/api/for-you/picks';
const STREAMING = '/api/streaming';

test('only runs on the signed-in home page', () => {
  assert.equal(setup({ pathname: '/library' }).sent.length, 0);
  assert.equal(setup({ storage: {} }).sent.length, 0);
  // A cookie session without a stored token still starts (the cookie goes along).
  const cookieOnly = setup({ storage: { omnitrackr_user: '{"id":1}' } });
  assert.ok(cookieOnly.sent.length > 30);
  assert.equal(cookieOnly.sent[0].init.headers.Authorization, undefined);
});

test('sends every address once, with the stored token', () => {
  const page = setup();
  const urls = page.sent.map(request => request.url);
  assert.equal(new Set(urls).size, urls.length);
  assert.deepEqual(urls, Array.from(page.window.OmniHomePrefetch.addresses(), ([, address]) => address));
  assert.ok(urls.includes('/api/break/home?today=2026-11-23'));
  assert.equal(page.sent[0].init.headers.Authorization, 'Bearer tok');
  assert.equal(page.sent[0].init.credentials, 'same-origin');
  // Cards that read the visit count are never started early.
  for (const left of ['/api/badges', '/api/stay-posted', '/api/support-ask']) assert.ok(!urls.includes(left), left);
});

test('a card is handed the early answer once, then goes to the network', async () => {
  const page = setup();
  const before = page.sent.length;
  const first = await page.window.fetch(PICKS, { headers: { Accept: 'application/json' } });
  assert.equal(page.sent.length, before);
  assert.equal(first.url, PICKS);
  await page.window.fetch(PICKS);
  assert.equal(page.sent.length, before + 1);
  assert.deepEqual(Array.from(page.window.OmniHomePrefetch.claimed()), ['for-you-picks']);
  // Full addresses match too.
  await page.window.fetch(`${ORIGIN}${STREAMING}`);
  assert.equal(page.sent.length, before + 1);
});

test('a different address, a Request object or another method is never answered early', async () => {
  const page = setup();
  const before = page.sent.length;
  await page.window.fetch('/api/for-you/picks?fresh=1');
  await page.window.fetch(PICKS, { credentials: 'omit' });
  await page.window.fetch(PICKS, { method: 'HEAD' });
  assert.equal(page.sent.length, before + 3);
  assert.equal(page.window.OmniHomePrefetch.claimed().length, 0);
});

test('an error answer is asked for again', async () => {
  const page = setup({ status: (url, n) => (url === PICKS && n < 20 ? 500 : 200) });
  const before = page.sent.length;
  const answer = await page.window.fetch(PICKS);
  assert.equal(page.sent.length, before + 1);
  assert.equal(answer.ok, true);
});

test('a write drops every answer not handed out yet; visit pings do not', async () => {
  const page = setup();
  const before = page.sent.length;
  await page.window.fetch('/account/visit', { method: 'POST' });
  await page.window.fetch('/api/review-inbox/seen', { method: 'POST' });
  await page.window.fetch(STREAMING);
  assert.equal(page.sent.length, before + 2);
  await page.window.fetch('/api/goals', { method: 'POST', body: '{}' });
  assert.equal(page.window.OmniHomePrefetch.pending().length, 0);
  await page.window.fetch(PICKS);
  assert.equal(page.sent.length, before + 4);
});

test('answers older than 30 seconds are not handed out', async () => {
  const page = setup();
  const before = page.sent.length;
  page.advance(30001);
  await page.window.fetch(PICKS);
  assert.equal(page.sent.length, before + 1);
});

test('an aborted request rejects like fetch does', async () => {
  const page = setup();
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(page.window.fetch(PICKS, { signal: controller.signal }), error => error.name === 'AbortError');
});

test('addresses no card asked for on two visits are left out for a week', async () => {
  const storage = { omnitrackr_token: 'tok' };
  const claimFive = async page => {
    for (const [, address] of page.window.OmniHomePrefetch.addresses().slice(0, 5)) await page.window.fetch(address);
  };
  for (let visit = 0; visit < 2; visit += 1) {
    const page = setup({ storage });
    await claimFive(page);
    page.settle();
  }
  const skips = JSON.parse(storage.omnitrackr_home_prefetch_skip);
  assert.equal(skips['library-movies'], undefined);
  assert.equal(skips.streaming, undefined);
  assert.equal(skips['for-you-picks'].misses, 2);
  const third = setup({ storage });
  const urls = third.sent.map(request => request.url);
  assert.equal(urls.length, 5);
  assert.ok(!urls.includes(PICKS));
  // A visit where hardly anything was asked for teaches nothing.
  const quick = setup({ storage: { omnitrackr_token: 'tok' } });
  quick.settle();
  assert.equal(quick.storage.omnitrackr_home_prefetch_skip, undefined);
});
