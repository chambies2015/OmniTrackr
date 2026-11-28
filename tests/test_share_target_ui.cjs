// Run with: node --test tests/test_share_target_ui.cjs
// A link or text shared from another app: the sign-in return path and the dashboard's reader.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const dashboard = require('./helpers/dashboard_source.cjs');
const auth = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function validator() {
  const context = vm.createContext({});
  vm.runInContext(auth.slice(auth.indexOf('const SHARE_RETURN'), auth.indexOf('function clearDiscoverAuthReturn(')), context);
  return context.validateDiscoverAuthReturn;
}

test('the log-in form brings a share back after signing in', () => {
  const validate = validator();
  for (const value of [
    '/?share=1',
    '/?share=1&q=Past%20Lives&kind=movies&via=letterboxd',
    '/?share=1&q=Dune%3A%20Part%20Two&kind=screen&year=2024&via=imdb',
    `/?share=1&q=${'%E8%91%AC'.repeat(44)}&kind=anime`,
  ]) assert.equal(validate(value), value, value);
  for (const value of [
    '/?share=1&q=Dune&kind=movies&via=imdb\n',
    '/?share=1&q=<script>',
    '/?share=1&q=Dune&next=https://evil.example',
    '/?share=1&via=imdb&q=Dune',
    '/?share=1&kind=documentaries',
    '//evil.example/?share=1',
    `/?share=1&q=${'a'.repeat(401)}`,
  ]) assert.equal(validate(value), null, value);
  // Existing return paths still work.
  assert.equal(validate('/daily'), '/daily');
});

function reader(href) {
  const replaced = [];
  const opened = [];
  const notices = [];
  const window = {
    location: { href },
    history: { state: null, replaceState(state, title, url) { replaced.push(url); window.location.href = `https://omnitrackr.xyz${url}`; } },
  };
  const context = vm.createContext({
    URL, window, hasStoredAuth: () => true, Promise,
    openSharedTitle: shared => { opened.push(shared); },
    showNotice: message => notices.push(message),
    consumeLibraryNavigationTarget() {}, consumeCollectionNavigationTarget() {},
    openLibraryItemFromLocation: () => 'library', openCollectionFromLocation: () => 'collection',
    document: { getElementById: () => null },
  });
  vm.runInContext(dashboard.slice(dashboard.indexOf('const SHARE_KINDS'), dashboard.indexOf('function consumeCollectionNavigationTarget(')), context);
  return { context, replaced, opened, notices };
}

test('the dashboard reads a share once and clears it from the address bar', () => {
  const r = reader('https://omnitrackr.xyz/?share=1&q=Dune%3A%20Part%20Two&kind=screen&year=2024&via=imdb#top');
  assert.equal(r.context.openDashboardTargetFromLocation(), true);
  assert.equal(r.opened.length, 1);
  assert.deepEqual({ ...r.opened[0] }, { query: 'Dune: Part Two', kind: 'screen', year: '2024', via: 'imdb' });
  assert.deepEqual(r.replaced, ['/#top']);
  assert.equal(r.context.openDashboardTargetFromLocation(), 'collection', 'a reload does not open it again');
});

test('the dashboard drops share values it does not recognise', () => {
  const r = reader('https://omnitrackr.xyz/?share=1&q=Hades&kind=board-games&year=12&via=Evil%20Site&utm_source=app');
  r.context.openDashboardTargetFromLocation();
  assert.deepEqual({ ...r.opened[0] }, { query: 'Hades', kind: '', year: '', via: '' });
  assert.deepEqual(r.replaced, ['/?utm_source=app']);
});
