const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/public-landing.js'), 'utf8');

function node(props = {}) {
  const el = {
    attrs: {}, dataset: {}, classes: new Set(), parent: null, open: false, focused: false,
    classList: {toggle: name => { if (el.classes.has(name)) { el.classes.delete(name); return false; } el.classes.add(name); return true; }, add() {}, remove() {}},
    setAttribute(k, v) { el.attrs[k] = String(v); },
    getAttribute(k) { return el.attrs[k] ?? null; },
    contains(other) { let n = other; while (n) { if (n === el) return true; n = n.parent; } return false; },
    closest(selector) { let n = el; while (n) { if (n.matches && n.matches(selector)) return n; n = n.parent; } return null; },
    querySelector: () => null,
    focus() { el.focused = true; },
    ...props,
  };
  return el;
}

function setup() {
  const listeners = {};
  const menu = node({matches: s => s === 'details.lp-menu[open]' ? menu.open : false});
  const summary = node({parent: menu, matches: () => false});
  menu.querySelector = s => (s === 'summary' ? summary : null);
  const panel = node({parent: menu, matches: s => s === '.lp-menu__panel'});
  const link = node({parent: panel, matches: s => s === '.lp-menu__panel a'});
  const outside = node({matches: () => false});
  const faqItem = node({matches: s => s === '.faq-item'});
  const faqQuestion = node({parent: faqItem, matches: s => s === '.faq-question'});
  const calls = [];
  const document = {
    addEventListener: (name, handler) => { listeners[name] = handler; },
    querySelectorAll: selector => (selector === 'details.lp-menu[open]' && menu.open ? [menu] : []),
    getElementById: () => null,
    body: {style: {}},
  };
  const window = {showLoginForm: () => calls.push('login'), showRegisterForm: () => calls.push('register')};
  vm.runInContext(script, vm.createContext({document, window}));
  const click = target => listeners.click({target, preventDefault() {}});
  return {listeners, menu, summary, link, outside, faqItem, faqQuestion, click, calls};
}

test('menu closes after choosing a link or clicking elsewhere, but not when clicking inside', () => {
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

test('escape closes the menu and returns focus to its button', () => {
  const ui = setup();
  ui.menu.open = true;
  ui.listeners.keydown({key: 'Escape'});
  assert.equal(ui.menu.open, false);
  assert.equal(ui.summary.focused, true);
});

test('faq questions toggle and report their state', () => {
  const ui = setup();
  ui.click(ui.faqQuestion);
  assert.equal(ui.faqQuestion.getAttribute('aria-expanded'), 'true');
  ui.click(ui.faqQuestion);
  assert.equal(ui.faqQuestion.getAttribute('aria-expanded'), 'false');
});

test('login and register actions open the matching form', () => {
  const ui = setup();
  for (const action of ['show-login-form', 'show-register-form']) {
    const button = node({dataset: {action}, matches: s => s === '[data-action]'});
    ui.click(button);
  }
  assert.deepEqual(ui.calls, ['login', 'register']);
});
