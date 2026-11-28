// The Essential 100 "Titles only" view: folds the notes away and is remembered in this browser.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load(saved) {
  const store = new Map(saved ? [['omnitrackr_essentials_view', saved]] : []);
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  delete global.document;
  delete require.cache[require.resolve('../app/static/essentials.js')];
  const api = require(path.join(__dirname, '../app/static/essentials.js'));
  const listeners = [];
  const attrs = { 'aria-pressed': 'false' };
  const button = {
    hidden: true,
    getAttribute: name => attrs[name],
    setAttribute: (name, value) => { attrs[name] = String(value); },
    addEventListener: (type, fn) => listeners.push(fn),
  };
  const root = { dataset: {}, querySelector: selector => (selector === '[data-es-view]' ? button : null) };
  api.setupView(root);
  return { api, store, root, button, press: () => listeners.forEach(fn => fn()) };
}

test('the button appears and starts on the full notes', () => {
  const { root, button } = load();
  assert.equal(button.hidden, false);
  assert.equal(button.getAttribute('aria-pressed'), 'false');
  assert.equal(root.dataset.esView, undefined);
});

test('pressing it folds the notes and remembers the choice; pressing again brings them back', () => {
  const { root, button, store, press, api } = load();
  press();
  assert.equal(root.dataset.esView, 'titles');
  assert.equal(button.getAttribute('aria-pressed'), 'true');
  assert.equal(store.get(api.VIEW_KEY), 'titles');
  press();
  assert.equal(root.dataset.esView, undefined);
  assert.equal(store.has(api.VIEW_KEY), false);
});

test('a remembered choice is applied on the next visit, and junk is ignored', () => {
  assert.equal(load('titles').root.dataset.esView, 'titles');
  assert.equal(load('<script>').root.dataset.esView, undefined);
});
