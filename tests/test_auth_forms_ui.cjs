// Sign-in forms: messages under the right box, password strength, Show/Hide, and
// the resend link asking for an email in the page instead of a browser prompt.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function setup({ reply = { ok: true, body: {} } } = {}) {
  const elements = new Map();
  const docListeners = {};
  const requests = [];
  const beacons = [];
  const prompts = [];
  function el(id, props = {}) {
    const node = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, type: 'text', attrs: {}, listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      focus() { focused.id = id; },
      querySelector: () => null,
      querySelectorAll: () => [],
      reset() {},
      ...props,
    };
    elements.set(id, node);
    return node;
  }
  const focused = { id: null };
  const document = {
    readyState: 'loading', title: '', documentElement: { dataset: { publicShell: 'true' } },
    addEventListener(type, fn) { docListeners[type] = fn; },
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => el(`node${elements.size}`),
    // The sign-up form has a Show button instead of a second password box.
    getElementById(id) { return id === 'registerConfirmPassword' ? null : elements.get(id) || el(id); },
  };
  const location = { pathname: '/', search: '', assign() {} };
  const context = vm.createContext({
    URLSearchParams, location, document, Blob: function Blob() {},
    navigator: { sendBeacon: (url, blob) => { beacons.push(url); return true; } },
    window: { location, history: { replaceState() {} } },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: reply.ok, status: reply.status || 200, json: async () => reply.body }; },
    prompt: message => { prompts.push(message); return null; },
    setTimeout: () => 0,
  });
  vm.runInContext(source, context);
  return { context, elements, docListeners, requests, beacons, prompts, focused, el, $: id => document.getElementById(id) };
}

function form(s, id, button) {
  const submit = button || s.el(`${id}Button`, { disabled: false, textContent: 'Go' });
  const node = s.el(id, {
    querySelector: selector => (selector === 'button[type="submit"]' ? submit : null),
    querySelectorAll: () => Array.from(s.elements.values()).filter(item => item.attrs['aria-invalid'] === 'true'),
  });
  return node;
}

test('sign-up mistakes are named under the box they belong to', async () => {
  const s = setup();
  const registerForm = form(s, 'registerFormElement');
  s.context.setupAuthHandlers();
  s.$('registerEmail').value = 'not-an-email';
  s.$('registerUsername').value = 'reader';
  s.$('registerPassword').value = 'long enough phrase';
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  assert.match(s.$('registerEmailError').textContent, /email address/);
  assert.equal(s.$('registerEmailError').hidden, false);
  assert.equal(s.$('registerEmail').attrs['aria-invalid'], 'true');
  assert.equal(s.focused.id, 'registerEmail');
  assert.equal(s.requests.length, 0);

  s.$('registerEmail').value = 'fan@example.com';
  s.$('registerUsername').value = 'x';
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  assert.equal(s.$('registerEmailError').hidden, true, 'fixed boxes lose their message');
  assert.match(s.$('registerUsernameError').textContent, /3–30 characters/);
  assert.equal(s.focused.id, 'registerUsername');
});

test('a taken username from the server lands under the username box', async () => {
  const s = setup({ reply: { ok: false, status: 400, body: { detail: 'That username is already taken.' } } });
  const registerForm = form(s, 'registerFormElement');
  s.context.setupAuthHandlers();
  s.$('registerEmail').value = 'fan@example.com';
  s.$('registerUsername').value = 'reader';
  s.$('registerPassword').value = 'long enough phrase';
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  assert.equal(s.requests.length, 1);
  assert.equal(s.$('registerUsernameError').textContent, 'That username is already taken.');
  assert.equal(s.$('authError').textContent, '');
});

test('errors without a box fall back to the message at the top', () => {
  const s = setup();
  assert.equal(s.context.signupFieldFor('Something went wrong'), null);
  assert.equal(s.context.signupFieldFor('Email already registered'), 'registerEmail');
  assert.equal(s.context.signupFieldFor('That password is too easy to guess.'), 'registerPassword');
  // The old one-line helper still answers with just the message.
  assert.equal(s.context.signupProblem('fan@example.com', 'reader', 'short', 'short'), 'Use at least 8 characters for your password.');
});

test('login asks for missing boxes before sending anything', async () => {
  const s = setup();
  const loginForm = form(s, 'loginFormElement');
  s.context.setupAuthHandlers();
  await loginForm.listeners.submit({ preventDefault() {}, target: loginForm });
  assert.match(s.$('loginUsernameError').textContent, /username or the email/);
  s.$('loginUsername').value = 'reader';
  await loginForm.listeners.submit({ preventDefault() {}, target: loginForm });
  assert.equal(s.$('loginPasswordError').textContent, 'Enter your password.');
  assert.equal(s.requests.length, 0);
});

test('resend asks for the email in the page, never with a browser prompt', async () => {
  const s = setup();
  s.context.setupAuthHandlers();
  s.$('loginUsername').value = 'reader';
  const box = s.$('resendVerificationEmailField');
  box.hidden = true;
  await s.$('resendVerificationBtn').listeners.click();
  assert.equal(box.hidden, false);
  assert.equal(s.focused.id, 'resendVerificationEmail');
  assert.equal(s.prompts.length, 0);
  assert.equal(s.requests.length, 0);

  s.$('resendVerificationEmail').value = 'fan@example.com';
  await s.$('resendVerificationBtn').listeners.click();
  assert.equal(s.requests[0].url, '/auth/resend-verification?email=fan%40example.com');
});

test('reset password checks length, then the match, under each box', async () => {
  const s = setup();
  const resetForm = form(s, 'resetPasswordFormElement');
  s.context.setupAuthHandlers();
  s.$('newPassword').value = 'short';
  await resetForm.listeners.submit({ preventDefault() {}, target: resetForm });
  assert.match(s.$('newPasswordError').textContent, /8 characters/);
  s.$('newPassword').value = 'a long new phrase';
  s.$('confirmNewPassword').value = 'a long new phrasf';
  await resetForm.listeners.submit({ preventDefault() {}, target: resetForm });
  assert.match(s.$('confirmNewPasswordError').textContent, /don't match/);
  assert.equal(s.requests.length, 0);
});

test('password strength warns about short and guessable passwords', () => {
  const { context } = setup();
  assert.equal(context.passwordStrength('').level, 0);
  assert.deepEqual({ ...context.passwordStrength('abc') }, { level: 1, text: '5 more characters to go' });
  assert.match(context.passwordStrength('password123').text, /Easy to guess/);
  assert.match(context.passwordStrength('12345678').text, /Easy to guess/);
  assert.match(context.passwordStrength('aaaaaaaa').text, /Easy to guess/);
  assert.match(context.passwordStrength('reader99', { username: 'reader' }).text, /Easy to guess/);
  assert.equal(context.passwordStrength('blue kite').level, 2);
  assert.equal(context.passwordStrength('Blue kite 42').level, 4);
  assert.equal(context.passwordStrength('tuesday movie night club').level, 4);
});

test('typing updates the meter and clears an old message; Show/Hide toggles once per click', () => {
  const s = setup();
  s.context.setupPasswordHelpers();
  const text = { textContent: '' };
  const meter = s.el('registerPasswordStrength', { hidden: true, querySelector: () => text });
  const field = s.el('registerPassword', { type: 'password', dataset: { passwordStrength: 'registerPasswordStrength' } });
  field.setAttribute('aria-invalid', 'true');
  s.el('registerPasswordError', { textContent: 'Use at least 8 characters for your password.', hidden: false });
  field.value = 'abc';
  s.docListeners.input({ target: field });
  assert.equal(meter.hidden, false);
  assert.equal(meter.dataset.level, '1');
  assert.equal(text.textContent, 'Strength: 5 more characters to go');
  assert.equal(field.getAttribute('aria-invalid'), null);
  assert.equal(s.$('registerPasswordError').hidden, true);

  const toggle = s.el('toggle', { dataset: { passwordToggle: 'registerPassword' } });
  toggle.closest = selector => (selector === '[data-password-toggle]' ? toggle : null);
  s.docListeners.click({ target: toggle });
  assert.equal(field.type, 'text');
  assert.equal(toggle.textContent, 'Hide');
  assert.equal(toggle.getAttribute('aria-pressed'), 'true');
  s.docListeners.click({ target: toggle });
  assert.equal(field.type, 'password');
  assert.equal(toggle.textContent, 'Show');
});
