const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/site.js'), 'utf8');

function node(parent, matcher) {
  const el = {parent, open: false, focused: false};
  el.matches = s => matcher(s, el);
  el.contains = other => { let n = other; while (n) { if (n === el) return true; n = n.parent; } return false; };
  el.closest = s => { let n = el; while (n) { if (n.matches(s)) return n; n = n.parent; } return null; };
  el.focus = () => { el.focused = true; };
  el.querySelector = () => null;
  return el;
}

function setup() {
  const listeners = {};
  const OPEN = 'details.site-menu[open], details.site-dd[open]';
  const menu = node(null, s => (s === OPEN && menu.open) || s === 'details.site-menu' || s === 'details.site-menu, details.site-dd');
  const dropdown = node(null, s => (s === OPEN && dropdown.open) || s === 'details.site-menu, details.site-dd');
  const summary = node(menu, () => false);
  menu.querySelector = s => (s === 'summary' ? summary : null);
  const panel = node(menu, s => s === '.site-menu__panel');
  const link = node(panel, s => s === '.site-menu__panel a, .site-dd__panel a');
  const outside = node(null, () => false);
  const document = {
    body: {classList: {toggle: (name, on) => { bodyClasses[name] = on; }}},
    addEventListener: (name, handler) => { listeners[name] = handler; },
    querySelectorAll: s => (s === OPEN ? [menu, dropdown].filter(m => m.open) : []),
    querySelector: () => null,  // no long-form guide or search button on this page
  };
  const bodyClasses = {};
  vm.runInContext(script, vm.createContext({document, window: {}}));
  return {listeners, menu, dropdown, summary, link, outside, bodyClasses, click: target => listeners.click({target})};
}

test('menu stays open for clicks inside, closes after a choice or an outside click', () => {
  const ui = setup();
  ui.menu.open = true;
  ui.click(ui.summary);
  assert.equal(ui.menu.open, true);
  ui.click(ui.link);
  assert.equal(ui.menu.open, false);
  ui.menu.open = true;
  ui.click(ui.outside);
  assert.equal(ui.menu.open, false);
});

test('escape closes the menu and returns focus to its button; other keys do nothing', () => {
  const ui = setup();
  ui.menu.open = true;
  ui.listeners.keydown({key: 'Enter'});
  assert.equal(ui.menu.open, true);
  ui.listeners.keydown({key: 'Escape'});
  assert.equal(ui.menu.open, false);
  assert.equal(ui.summary.focused, true);
});

test('opening one menu closes the others and locks page scroll for the compact menu', () => {
  const ui = setup();
  ui.dropdown.open = true;
  ui.menu.open = true;
  ui.listeners.toggle({target: ui.menu});
  assert.equal(ui.dropdown.open, false);
  assert.equal(ui.bodyClasses['site-menu-open'], true);
  ui.menu.open = false;
  ui.listeners.toggle({target: ui.menu});
  assert.equal(ui.bodyClasses['site-menu-open'], false);
});
