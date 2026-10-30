// Two-factor code step on the log-in card, and the recovery-code list in Settings.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const authSource = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const settingsSource = fs.readFileSync(path.join(__dirname, '../app/static/two-factor.js'), 'utf8');

function setup(replies) {
  const elements = new Map();
  const requests = [];
  const stored = {};
  const assigned = [];
  function el(id, props = {}) {
    const node = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, checked: false, attrs: {}, listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      focus() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      reset() {},
      ...props,
    };
    elements.set(id, node);
    return node;
  }
  const document = {
    readyState: 'loading', title: '', documentElement: { dataset: { publicShell: 'true' } },
    addEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => el(`node${elements.size}`),
    getElementById(id) { return elements.get(id) || el(id); },
  };
  const location = { pathname: '/', search: '', assign(url) { assigned.push(url); } };
  const queue = replies.slice();
  const storage = {
    getItem: key => (key in stored ? stored[key] : null),
    setItem(key, value) { stored[key] = String(value); },
    removeItem(key) { delete stored[key]; },
  };
  const context = vm.createContext({
    URLSearchParams, location, document, Blob: function Blob() {},
    navigator: { sendBeacon: () => true },
    window: { location, history: { replaceState() {} } },
    localStorage: storage,
    sessionStorage: storage,
    fetch: async (url, options) => {
      requests.push({ url, options });
      const reply = queue.shift() || { ok: true, body: {} };
      return { ok: reply.ok !== false, status: reply.status || 200, json: async () => reply.body };
    },
    setTimeout: () => 0,
  });
  vm.runInContext(authSource, context);
  return { context, elements, requests, stored, assigned, el, $: id => document.getElementById(id) };
}

function codeForm(s) {
  const submit = s.el('twoFactorSubmit', { disabled: false, textContent: 'Continue' });
  return s.el('twoFactorFormElement', {
    querySelector: selector => (selector === 'button[type="submit"]' ? submit : null),
    querySelectorAll: () => Array.from(s.elements.values()).filter(item => item.attrs['aria-invalid'] === 'true'),
  });
}

test('a correct password for a two-factor account opens the code step instead of the library', async () => {
  const s = setup([{ body: { two_factor_required: true } }]);
  await s.context.login('reader', 'a good long password');
  assert.equal(s.$('twoFactorForm').style.display, 'block');
  assert.equal(s.$('loginForm').style.display, 'none');
  assert.equal(s.$('authTitle').textContent, 'Enter your code');
  assert.deepEqual(s.assigned, []);
  assert.equal(s.stored.omnitrackr_user, undefined);
});

test('the code is sent on its own and finishes the log-in', async () => {
  const user = { id: 7, username: 'reader' };
  const s = setup([{ body: { access_token: 'x', user } }]);
  const form = codeForm(s);
  s.context.setupTwoFactorHandlers();
  s.context.showTwoFactorForm(false);
  s.$('twoFactorCode').value = ' 123 456 ';
  s.$('twoFactorRemember').checked = true;
  await form.listeners.submit({ preventDefault() {}, target: form });
  assert.equal(s.requests.length, 1);
  assert.match(s.requests[0].url, /\/auth\/login\/two-factor$/);
  assert.deepEqual(JSON.parse(s.requests[0].options.body), { code: '123 456', remember_device: true });
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.deepEqual(s.assigned, ['/']);
  assert.equal(JSON.parse(s.stored.omnitrackr_user).username, 'reader');
});

test('a short app code is caught before any request', async () => {
  const s = setup([]);
  const form = codeForm(s);
  s.context.setupTwoFactorHandlers();
  s.context.showTwoFactorForm(false);
  s.$('twoFactorCode').value = '1234';
  await form.listeners.submit({ preventDefault() {}, target: form });
  assert.equal(s.requests.length, 0);
  assert.match(s.$('twoFactorCodeError').textContent, /six digits/);
});

test('a recovery code works and the dashboard is told how many are left', async () => {
  const s = setup([{ body: { access_token: 'x', user: { id: 7, username: 'reader' }, recovery_codes_left: 2 } }]);
  const form = codeForm(s);
  s.context.setupTwoFactorHandlers();
  s.context.showTwoFactorForm(false);
  s.$('twoFactorUseRecovery').listeners.click({ preventDefault() {} });
  assert.equal(s.$('twoFactorCodeLabel').textContent, 'Recovery code');
  s.$('twoFactorCode').value = 'abcde-fghjk';
  await form.listeners.submit({ preventDefault() {}, target: form });
  assert.equal(JSON.parse(s.requests[0].options.body).code, 'abcde-fghjk');
  const notice = JSON.parse(s.stored.omnitrackr_pending_notice);
  assert.match(notice.message, /2 left/);
});

test('a wrong code stays on the code step with the reason under the box', async () => {
  const s = setup([{ ok: false, status: 401, body: { detail: "That code didn't work. Codes change every 30 seconds, so try the newest one." } }]);
  const form = codeForm(s);
  s.context.setupTwoFactorHandlers();
  s.context.showTwoFactorForm(false);
  s.$('twoFactorCode').value = '000000';
  await form.listeners.submit({ preventDefault() {}, target: form });
  assert.match(s.$('twoFactorCodeError').textContent, /didn't work/);
  assert.equal(s.$('twoFactorForm').style.display, 'block');
  assert.deepEqual(s.assigned, []);
});

test('an expired code step goes back to the password form', async () => {
  const s = setup([{ ok: false, status: 401, body: { detail: 'That sign-in timed out. Log in again to get a new code prompt.' } }]);
  const form = codeForm(s);
  s.context.setupTwoFactorHandlers();
  s.context.showTwoFactorForm(false);
  s.$('twoFactorCode').value = '123456';
  await form.listeners.submit({ preventDefault() {}, target: form });
  assert.equal(s.$('loginForm').style.display, 'block');
  assert.equal(s.$('twoFactorForm').style.display, 'none');
  assert.match(s.$('authError').textContent, /timed out/);
});

test('saved recovery codes come out as a plain text file', () => {
  const context = vm.createContext({
    document: { readyState: 'complete', getElementById: () => null, querySelectorAll: () => [] },
    window: {},
  });
  vm.runInContext(settingsSource, context);
  const text = context.window.OmniTwoFactor.codesText();
  assert.match(text, /^OmniTrackr recovery codes\n/);
  assert.match(text, /Each code works once/);
});
