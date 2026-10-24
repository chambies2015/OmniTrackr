const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const loader = fs.readFileSync(path.join(__dirname, '../app/static/dashboard/lazy-loader.js'), 'utf8');
const titleLinks = fs.readFileSync(path.join(__dirname, '../app/static/title-links.js'), 'utf8');

function setup({ readyState = 'loading', saveData = false, idle = true } = {}) {
  const scripts = [];
  const listeners = {};
  const idleCallbacks = [];
  class FakeEvent { constructor(type) { this.type = type; this.defaultPrevented = false; } preventDefault() { this.defaultPrevented = true; } }
  const window = {
    OmniDashboardChunks: {
      version: 'abc123', base: '/static/dashboard/lazy/',
      chunks: {
        stats: { files: ['one.js', 'two.js'], exports: ['openStats', 'saveStats'] },
        extra: { files: ['extra.js'], exports: ['openExtra'] },
      },
    },
    addEventListener: (type, callback) => { listeners[type] = callback; },
    setTimeout: callback => idleCallbacks.push(callback),
  };
  if (idle) window.requestIdleCallback = callback => idleCallbacks.push(callback);
  const document = {
    readyState,
    createElement: () => ({ remove() { this.removed = true; } }),
    head: { appendChild: script => scripts.push(script) },
  };
  const context = vm.createContext({ window, document, navigator: { connection: { saveData } }, Event: FakeEvent, Promise });
  vm.runInContext(loader, context);
  return { window, scripts, listeners, idleCallbacks, FakeEvent };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('a placeholder loads its chunk once, in order, then calls the real function', async () => {
  const { window, scripts } = setup();
  const calls = [];
  const first = window.openStats('a');
  const second = window.saveStats('b');
  assert.deepEqual(scripts.map(script => script.src), [
    '/static/dashboard/lazy/one.js?v=abc123',
    '/static/dashboard/lazy/two.js?v=abc123',
  ]);
  assert.ok(scripts.every(script => script.async === false));
  window.openStats = value => { calls.push(['open', value]); return 'opened'; };
  window.saveStats = value => { calls.push(['save', value]); return 'saved'; };
  scripts.forEach(script => script.onload());
  assert.equal(await first, 'opened');
  assert.equal(await second, 'saved');
  assert.deepEqual(calls, [['open', 'a'], ['save', 'b']]);
  assert.equal(scripts.length, 2);
});

test('a placeholder kept by an event listener calls the loaded function directly', async () => {
  const { window, scripts } = setup();
  const standIn = window.openExtra;
  standIn();
  window.openExtra = value => `real ${value}`;
  scripts[0].onload();
  await flush();
  assert.equal(standIn('click'), 'real click');
  assert.equal(scripts.length, 1);
});

test('a submit is cancelled at once, before the chunk has downloaded', async () => {
  const { window, scripts, FakeEvent } = setup();
  const event = new FakeEvent('submit');
  const pending = window.openExtra(event);
  assert.equal(event.defaultPrevented, true);
  let received;
  window.openExtra = value => { received = value; };
  scripts[0].onload();
  await pending;
  assert.equal(received, event);
  const click = new FakeEvent('click');
  window.openStats(click);
  assert.equal(click.defaultPrevented, false);
});

test('a failed download rejects and the next use tries again', async () => {
  const { window, scripts } = setup();
  const failed = window.openExtra();
  scripts[0].onerror();
  await assert.rejects(failed, /Could not load extra.js/);
  assert.equal(scripts[0].removed, true);
  const retry = window.openExtra();
  assert.equal(scripts.length, 2);
  window.openExtra = () => 'ok';
  scripts[1].onload();
  assert.equal(await retry, 'ok');
});

test('every chunk is fetched one after another once the page is idle', async () => {
  const { window, scripts, listeners, idleCallbacks } = setup();
  assert.equal(scripts.length, 0);
  listeners.load();
  assert.equal(idleCallbacks.length, 1);
  idleCallbacks[0]();
  await flush();
  assert.deepEqual(scripts.map(script => script.src.split('/').pop()), ['one.js?v=abc123', 'two.js?v=abc123']);
  scripts.forEach(script => script.onload());
  await flush();
  assert.equal(scripts.at(-1).src, '/static/dashboard/lazy/extra.js?v=abc123');
  assert.equal(typeof window.OmniDashboardChunks.load, 'function');
});

test('data saver skips the background fetch but features still load on use', async () => {
  const { window, scripts, idleCallbacks } = setup({ readyState: 'complete', saveData: true, idle: false });
  assert.equal(idleCallbacks.length, 1);
  idleCallbacks[0]();
  await flush();
  assert.equal(scripts.length, 0);
  window.openExtra();
  assert.equal(scripts.length, 1);
});

test('the six library tables share one privacy request', async () => {
  const tables = ['movieTable', 'tvShowTable', 'animeTable', 'videoGameTable', 'musicTable', 'bookTable'];
  const requests = [];
  let respond;
  const context = vm.createContext({
    window: {},
    MutationObserver: class { observe() {} },
    setTimeout,
    fetch: url => { requests.push(url); return new Promise(resolve => { respond = resolve; }); },
    document: {
      readyState: 'complete',
      documentElement: { dataset: {} },
      addEventListener() {},
      querySelector: () => ({}),
      getElementById: id => (tables.includes(id) ? { querySelectorAll: () => [] } : null),
    },
  });
  vm.runInContext(titleLinks, context);
  await flush();
  assert.deepEqual(requests, ['/account/privacy']);
  respond({ ok: true, json: async () => ({}) });
  await flush();
  assert.equal(requests.length, 1);
});
