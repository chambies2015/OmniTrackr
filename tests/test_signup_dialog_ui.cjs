const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const landing = fs.readFileSync(path.join(__dirname, '../app/static/public-landing.js'), 'utf8');
const auth = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function element(props = {}) {
  const el = {
    attrs: {}, dataset: {}, listeners: {}, children: [], parentNode: null, style: {},
    setAttribute(k, v) { el.attrs[k] = String(v); },
    getAttribute(k) { return el.attrs[k] ?? null; },
    hasAttribute(k) { return k in el.attrs; },
    addEventListener(type, fn) { el.listeners[type] = fn; },
    appendChild(child) { if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1); child.parentNode = el; el.children.push(child); return child; },
    insertBefore(child, next) {
      if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
      child.parentNode = el;
      const at = next ? el.children.indexOf(next) : -1;
      if (at < 0) el.children.push(child); else el.children.splice(at, 0, child);
      return child;
    },
    get nextSibling() { const p = el.parentNode; return p ? p.children[p.children.indexOf(el) + 1] || null : null; },
    closest(selector) { let n = el; while (n) { if (n.matches && n.matches(selector)) return n; n = n.parentNode; } return null; },
    matches: () => false,
    ...props,
  };
  return el;
}

function setupLanding({ supportsDialog = true } = {}) {
  const listeners = {};
  const section = element();
  const card = element();
  section.appendChild(card);
  section.appendChild(element());
  const slot = element();
  const dialog = element({ open: false, querySelector: s => (s === '[data-auth-dialog-slot]' ? slot : null) });
  if (supportsDialog) {
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; dialog.listeners.close && dialog.listeners.close(); };
  }
  dialog.appendChild(slot);
  const password = element({ type: 'password' });
  const beacons = [];
  const calls = [];
  const document = {
    addEventListener: (name, handler) => { listeners[name] = handler; },
    getElementById: id => ({ authDialog: dialog, registerPassword: password }[id] || null),
    querySelector: s => (s === '.lp-auth__card' ? card : null),
    body: { style: {} },
  };
  const window = {
    reportFunnelEvent: event => beacons.push(event),
    showRegisterForm: () => { calls.push('register'); window.OmniAuthDialog.open(); },
    showLoginForm: () => { calls.push('login'); window.OmniAuthDialog.open(); },
  };
  vm.runInContext(landing, vm.createContext({ document, window }));
  const click = target => listeners.click({ target, preventDefault() {} });
  return { window, document, dialog, slot, section, card, password, beacons, calls, click };
}

test('sign-up buttons open the form card in a pop-up and put it back on close', () => {
  const ui = setupLanding();
  const button = element({ dataset: { action: 'show-register-form' }, matches: s => s === '[data-action]' });
  button.attrs['data-hero-signup'] = '';
  ui.click(button);
  assert.deepEqual(ui.calls, ['register']);
  assert.equal(ui.dialog.open, true);
  assert.equal(ui.card.parentNode, ui.slot);
  assert.equal(ui.document.body.style.overflow, 'hidden');
  assert.deepEqual(ui.beacons, ['hero_signup_clicked']);

  const close = element({ dataset: { action: 'close-auth-dialog' }, matches: s => s === '[data-action]' });
  ui.click(close);
  assert.equal(ui.dialog.open, false);
  assert.equal(ui.card.parentNode, ui.section);
  assert.equal(ui.section.children[0], ui.card, 'the card returns to its original place');
  assert.equal(ui.document.body.style.overflow, '');
});

test('a click on the backdrop closes the pop-up', () => {
  const ui = setupLanding();
  ui.window.OmniAuthDialog.open();
  ui.dialog.listeners.click({ target: ui.slot });
  assert.equal(ui.dialog.open, true);
  ui.dialog.listeners.click({ target: ui.dialog });
  assert.equal(ui.dialog.open, false);
  assert.equal(ui.card.parentNode, ui.section);
});

test('browsers without dialog support keep the scrolling fallback', () => {
  const ui = setupLanding({ supportsDialog: false });
  assert.equal(ui.window.OmniAuthDialog.open(), false);
  assert.equal(ui.card.parentNode, ui.section);
});

test('other sign-up buttons are not counted as hero clicks', () => {
  const ui = setupLanding();
  ui.click(element({ dataset: { action: 'show-register-form' }, matches: s => s === '[data-action]' }));
  assert.deepEqual(ui.beacons, []);
  const heroGoogle = element({ matches: s => s === 'a[data-hero-signup]' });
  ui.click(heroGoogle);
  assert.deepEqual(ui.beacons, ['hero_signup_clicked']);
});

test('the password button shows and hides the password', () => {
  const ui = setupLanding();
  const toggle = element({ dataset: { passwordToggle: 'registerPassword' }, matches: s => s === '[data-password-toggle]' });
  ui.click(toggle);
  assert.equal(ui.password.type, 'text');
  assert.equal(toggle.textContent, 'Hide');
  assert.equal(toggle.getAttribute('aria-pressed'), 'true');
  ui.click(toggle);
  assert.equal(ui.password.type, 'password');
  assert.equal(toggle.textContent, 'Show');
});

function loadAuth() {
  const fields = new Map();
  const context = vm.createContext({
    URLSearchParams,
    window: { location: { pathname: '/', search: '' }, history: { replaceState() {} } },
    location: { pathname: '/', search: '' },
    document: {
      readyState: 'loading', title: '', documentElement: { dataset: {} },
      addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
      getElementById: id => fields.get(id) || null,
    },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    setTimeout: () => 0,
  });
  vm.runInContext(auth, context);
  return { context, fields };
}

test('a username is suggested from the email address', () => {
  const { context } = loadAuth();
  assert.equal(context.suggestUsername('sam.lee@example.com'), 'sam.lee');
  assert.equal(context.suggestUsername('sam.lee+films@example.com'), 'sam.lee');
  assert.equal(context.suggestUsername('_x@example.com'), 'x12');
  assert.equal(context.suggestUsername('josé@example.com'), 'jos');
  assert.equal(context.suggestUsername('a'.repeat(40) + '@example.com'), 'a'.repeat(30));
  assert.equal(context.suggestUsername('+++@example.com'), '');
  assert.equal(context.suggestUsername(''), '');
});

test('the suggestion stops once the visitor types their own username', () => {
  const { context, fields } = loadAuth();
  const email = element({ value: '' });
  const username = element({ value: '' });
  fields.set('registerEmail', email);
  fields.set('registerUsername', username);
  context.setupUsernameSuggestion();
  email.value = 'riley@example.com';
  email.listeners.input();
  assert.equal(username.value, 'riley');
  username.value = 'movie_riley';
  username.listeners.input();
  email.value = 'someone@example.com';
  email.listeners.input();
  assert.equal(username.value, 'movie_riley');
  username.value = '';
  username.listeners.input();
  email.listeners.input();
  assert.equal(username.value, 'someone', 'clearing the field brings the suggestion back');
});
