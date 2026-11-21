// Title pages: the save button in the sticky bar mirrors the hero button and, once a guest saves, offers the sign-up.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/title-page.js'), 'utf8');

function element(extra = {}) {
  const attrs = {};
  const listeners = {};
  return {
    hidden: true, disabled: false, textContent: '', tabIndex: 0, ...extra,
    getAttribute: name => (name in attrs ? attrs[name] : null),
    setAttribute: (name, value) => { attrs[name] = String(value); },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    fire: type => listeners[type] && listeners[type](),
  };
}

function setup(guest = true) {
  const heroButton = element({ textContent: guest ? 'Save to my list' : 'Add to my library' });
  if (guest) heroButton.setAttribute('aria-pressed', 'false');
  const dockButton = element();
  const join = guest ? element() : null;
  const dock = element({ querySelector: s => (s === '[data-dock-save]' ? dockButton : s === '[data-dock-join]' ? join : null) });
  const classes = new Set();
  const bar = { classList: { toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)) } };
  heroButton.click = () => {
    heroButton.setAttribute('aria-pressed', 'true');
    heroButton.textContent = 'Saved to your list ✓';
  };
  let observed;
  const document = {
    querySelector: s => ({
      '[data-title-dock]': dock, '.title-tabs': bar,
      '.title-hero [data-guest-save], .title-hero [data-title-add]': heroButton,
    })[s] || null,
    querySelectorAll: () => [],
    getElementById: () => null,
    addEventListener() {},
    documentElement: { style: { setProperty() {} } },
  };
  const context = vm.createContext({
    document, window: { addEventListener() {}, location: { search: '', pathname: '/titles/movie/x' } },
    URLSearchParams, localStorage: { getItem: () => null }, setTimeout: fn => fn(),
    IntersectionObserver: function (fn) { this.observe = () => { observed = fn; }; },
  });
  vm.runInContext(source, context);
  return { heroButton, dockButton, join, dock, classes, scroll: gone => observed([{ isIntersecting: !gone, boundingClientRect: { top: gone ? -50 : 100 } }]) };
}

test('the bar copies the hero button and shows once the hero scrolls away', () => {
  const page = setup();
  assert.equal(page.dock.hidden, false);
  assert.equal(page.dockButton.textContent, 'Save to my list');
  assert.equal(page.join.hidden, true);
  page.scroll(true);
  assert.ok(page.classes.has('title-tabs--docked'));
  page.scroll(false);
  assert.ok(!page.classes.has('title-tabs--docked'));
});

test('saving from the bar presses the hero button, then offers the free account', () => {
  const page = setup();
  page.dockButton.fire('click');
  assert.equal(page.heroButton.getAttribute('aria-pressed'), 'true');
  assert.equal(page.dockButton.textContent, 'Saved');
  assert.equal(page.dockButton.getAttribute('aria-pressed'), 'true');
  assert.equal(page.join.hidden, false);
});

test('members see the add button label and no join link', () => {
  const page = setup(false);
  assert.equal(page.dockButton.textContent, 'Add to my library');
  assert.equal(page.join, null);
});
