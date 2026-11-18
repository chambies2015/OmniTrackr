// Search visitors (Nov 18 2026): the landing cookie in visit.js and the way back after sign-up in guest-list.js.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const visitSource = fs.readFileSync(path.join(__dirname, '../app/static/visit.js'), 'utf8');

function visit({ referrer, pathname = '/in-order/star-wars', cookie = '', protocol = 'https:' }) {
  const timers = [];
  const writes = [];
  const document = {
    visibilityState: 'visible', referrer, addEventListener() {},
    get cookie() { return cookie; },
    set cookie(value) { writes.push(value); },
  };
  const context = vm.createContext({
    URL, URLSearchParams, JSON, document,
    window: { location: { pathname, search: '', protocol } },
    navigator: { webdriver: false, sendBeacon: () => true },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    setTimeout: fn => { timers.push(fn); return timers.length; },
    clearTimeout: () => {},
  });
  vm.runInContext(visitSource, context);
  timers.splice(0).forEach(fn => fn());
  return writes;
}

test('a search landing leaves a one-day cookie naming only the section', () => {
  const [cookie] = visit({ referrer: 'https://www.google.com/' });
  assert.match(cookie, /^omnitrackr_from_search=in-order; Max-Age=86400; Path=\/; SameSite=Lax; Secure$/);
  assert.match(visit({ referrer: 'https://www.bing.com/search?q=x', pathname: '/' })[0], /^omnitrackr_from_search=home;/);
  assert.match(visit({ referrer: 'https://duckduckgo.com/', pathname: '/Weird%20Path' })[0], /^omnitrackr_from_search=other;/);
});

test('other referrers, a later page and an existing cookie leave it alone', () => {
  assert.deepEqual(visit({ referrer: 'https://www.reddit.com/r/movies' }), []);
  assert.deepEqual(visit({ referrer: 'https://omnitrackr.xyz/' }), []);
  assert.deepEqual(visit({ referrer: '' }), []);
  assert.deepEqual(visit({ referrer: 'https://google.com.evil.example/' }), []);
  assert.deepEqual(visit({ referrer: 'https://www.google.com/', cookie: 'omnitrackr_from_search=titles' }), []);
});

function guestList({ stored = {}, user = { id: 1 }, added = [{ title: 'Up' }] } = {}) {
  const store = new Map(Object.entries(stored));
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  const created = [];
  const body = { children: [], dataset: {}, appendChild(node) { this.children.push(node); } };
  const node = tag => {
    const item = { tag, children: [], textContent: '', listeners: {}, setAttribute() {}, remove() {},
      append(...nodes) { this.children.push(...nodes); }, addEventListener(name, fn) { this.listeners[name] = fn; } };
    created.push(item);
    return item;
  };
  global.document = {
    readyState: 'complete', documentElement: { dataset: { publicShell: 'false' } }, body,
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {}, createElement: node,
  };
  const events = [];
  global.window = { reportFunnelEvent: event => events.push(event), location: { pathname: '/in-order/dune' } };
  global.getUser = () => user;
  global.fetch = async () => ({ ok: true, json: async () => ({ added, existing: [], missing: 0 }) });
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/guest-list.js')];
  const api = require(path.join(__dirname, '../app/static/guest-list.js'));
  return { api, store, body, created, events };
}

test('the new library links back to the page the list was saved from', async () => {
  const back = JSON.stringify({ path: '/in-order/dune', title: 'Dune in order', at: Date.now() });
  const { api, store, body, created, events } = guestList({ stored: { omnitrackr_guest_return: back } });
  api.add('movie', 'up-2009', 'Up');
  await api.importList();
  const toast = body.children[0];
  assert.match(toast.textContent, /Added 1 title/);
  const link = created.find(item => item.tag === 'a');
  assert.equal(link.href, '/in-order/dune');
  assert.equal(link.textContent, 'Back to Dune in order →');
  assert.equal(store.has('omnitrackr_guest_return'), false);
  link.listeners.click();
  assert.ok(events.includes('guest_return_clicked'));
});

test('an old, foreign or broken return path is ignored', () => {
  const cases = [
    { path: '/in-order/dune', title: 'Old', at: Date.now() - 4 * 24 * 60 * 60 * 1000 },
    { path: 'https://evil.example/', title: 'x', at: Date.now() },
    { path: '//evil.example/x', title: 'x', at: Date.now() },
    { path: '/in-order/<script>', title: 'x', at: Date.now() },
  ];
  for (const value of cases) {
    const { api } = guestList({ stored: { omnitrackr_guest_return: JSON.stringify(value) } });
    assert.equal(api.readReturn(), null);
  }
  assert.equal(guestList({ stored: { omnitrackr_guest_return: 'not json' } }).api.readReturn(), null);
});
