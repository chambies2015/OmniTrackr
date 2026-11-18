// The "check your inbox" step takes the 6-digit code from the email (Nov 18 2026): typed or
// pasted, it opens the library in this tab. A log-in or a second sign-up for an account that
// was never confirmed lands on the same step instead of a dead end.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function setup(replies) {
  const queue = Array.isArray(replies) ? [...replies] : [replies];
  const redirects = [];
  const requests = [];
  const beacons = [];
  const elements = new Map();
  const local = new Map();
  const location = { pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz',
    assign: destination => redirects.push(destination), reload() {} };
  function el(id) {
    const node = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, className: '', attrs: {}, listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      focus() { this.focused = true; },
      select() { this.selected = true; },
      querySelector: () => null,
      querySelectorAll: () => [],
      reset() {},
    };
    elements.set(id, node);
    return node;
  }
  const context = vm.createContext({
    URLSearchParams, location, Blob: function Blob() {},
    navigator: { sendBeacon: (url, blob) => { beacons.push(url); return true; } },
    window: { location, history: { replaceState() {} } },
    document: {
      readyState: 'loading', documentElement: { dataset: { publicShell: 'true' } }, addEventListener() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      getElementById(id) { return id === 'registerConfirmPassword' ? null : elements.get(id) || el(id); },
    },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    localStorage: { getItem: key => local.get(key) ?? null, setItem: (key, value) => local.set(key, value), removeItem: key => local.delete(key) },
    fetch: async (url, options) => {
      requests.push({ url, options });
      const reply = queue.length > 1 ? queue.shift() : queue[0];
      return {
        ok: reply.ok !== false, status: reply.status || (reply.ok === false ? 400 : 200),
        headers: { get: name => (reply.headers || {})[name] ?? null },
        json: async () => reply.body,
      };
    },
    setTimeout: () => 0,
  });
  vm.runInContext(source, context);
  context.showAuthModal = () => {};
  return { context, redirects, requests, beacons, elements, local, $: id => context.document.getElementById(id) };
}

test('after sign-up the step asks for the code, with the mail button under it', () => {
  const s = setup({ body: {} });
  s.context.setupInboxPanel();
  assert.equal(s.context.showInboxPanel('verify', 'sam@gmail.com'), true);
  assert.equal(s.$('authTitle').textContent, 'Check your inbox');
  assert.equal(s.$('verifySentBefore').textContent, 'We sent a 6-digit code to ');
  assert.equal(s.$('verifyCodeForm').hidden, false);
  assert.equal(s.$('verifySentInbox').className, 'auth-ghost auth-inbox');
  assert.equal(s.$('verifySentInbox').textContent, 'Open Gmail');
  assert.match(s.$('verifySentNote').textContent, /Or open the link in that email on this device/);
  // A password reset has no code: the mail button is the main action there.
  s.context.showInboxPanel('reset', 'sam@gmail.com');
  assert.equal(s.$('verifyCodeForm').hidden, true);
  assert.equal(s.$('verifySentInbox').className, 'auth-submit auth-inbox');
});

test('six digits typed or pasted are checked straight away and open the library', async () => {
  const s = setup({ body: { signed_in: true, user: { id: 9, username: 'sam' } } });
  s.context.setupInboxPanel();
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  const field = s.$('verifyCode');
  field.value = '123 45';
  field.listeners.input();
  assert.equal(s.requests.length, 0);
  field.value = '123 456';
  field.listeners.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(field.value, '123456');
  assert.equal(s.requests[0].url, '/auth/verify-code');
  assert.deepEqual(JSON.parse(s.requests[0].options.body), { email: 'sam@gmail.com', code: '123456' });
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.deepEqual(s.redirects, ['/']);
  assert.equal(JSON.parse(s.local.get('omnitrackr_user')).username, 'sam');
  assert.equal(s.$('authTitle').textContent, 'Your email is confirmed');
});

test('a wrong code is named under the box and the digits are selected for retyping', async () => {
  const s = setup({ ok: false, status: 400, body: { detail: "That code didn't work. Check the newest email from us, or send a new one." } });
  s.context.setupInboxPanel();
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifyCode').value = '000000';
  await s.context.submitSignupCode();
  assert.match(s.$('verifyCodeError').textContent, /didn't work/);
  assert.equal(s.$('verifyCodeError').hidden, false);
  assert.equal(s.$('verifyCode').attrs['aria-invalid'], 'true');
  assert.equal(s.$('verifyCode').selected, true);
  assert.equal(s.redirects.length, 0);
  assert.equal(s.$('verifyCodeSubmit').disabled, false);
});

test('a short code never reaches the server', async () => {
  const s = setup({ body: {} });
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifyCode').value = '12';
  await s.context.submitSignupCode();
  assert.equal(s.requests.length, 0);
  assert.match(s.$('verifyCodeError').textContent, /6 digits/);
});

test('logging in before confirming opens the code step for that address', async () => {
  const s = setup({ ok: false, status: 403, body: { detail: 'Please verify your email address before logging in.', unverified: true, email: 'sam@gmail.com' } });
  await s.context.login('sam', 'tea on the porch');
  assert.equal(s.$('authTitle').textContent, 'Confirm your email');
  assert.equal(s.$('verifySentEmail').textContent, 'sam@gmail.com');
  assert.equal(s.$('verifySentResend').hidden, false);
  assert.equal(s.$('verifySentResend').textContent, 'Send me a new code');
  assert.equal(s.$('verifyCodeForm').hidden, false);
});

test('signing up again with a waiting address opens the same step, not an error', async () => {
  const s = setup({ ok: false, status: 400, body: { detail: 'This email is already registered and waiting to be confirmed.', unverified: true, email: 'sam@gmail.com' } });
  await s.context.register('sam@gmail.com', 'sam', 'tea on the porch');
  assert.equal(s.$('authTitle').textContent, 'Confirm your email');
  assert.notEqual(s.$('authError').textContent, 'This email is already registered and waiting to be confirmed.');
});

test('a failed email is said on the step, and the resend button works there', async () => {
  const s = setup([{ status: 201, headers: { 'X-Verification-Email': 'failed' }, body: { id: 3 } }, { body: { message: 'sent' } }]);
  s.context.setupInboxPanel();
  await s.context.register('sam@gmail.com', 'sam', 'tea on the porch');
  assert.match(s.$('verifySentStatus').textContent, /couldn't send the email/);
  await s.$('verifySentResend').listeners.click();
  assert.equal(s.requests[1].url, '/auth/resend-verification?email=sam%40gmail.com');
  assert.match(s.$('verifySentStatus').textContent, /new code/);
  assert.equal(s.$('verifySentResend').textContent, 'Send the email again');
});

test('Open Gmail is counted once, and only on the code step', () => {
  const s = setup({ body: {} });
  s.context.setupInboxPanel();
  s.context.showInboxPanel('reset', 'sam@gmail.com');
  s.$('verifySentInbox').listeners.click();
  assert.equal(s.beacons.length, 0);
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifySentInbox').listeners.click();
  s.$('verifySentInbox').listeners.click();
  assert.equal(s.beacons.length, 1);
});

test('confirming in another tab hides the code box and makes the button the way in', () => {
  const s = setup({ body: {} });
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifySentPanel').style.display = 'block';
  s.context.inboxPanelConfirmed();
  assert.equal(s.$('verifyCodeForm').hidden, true);
  assert.equal(s.$('verifySentInbox').className, 'auth-submit auth-inbox');
  assert.equal(s.$('verifySentInbox').textContent, 'Open my library');
});
