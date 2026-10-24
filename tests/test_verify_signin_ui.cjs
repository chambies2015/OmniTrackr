// Verification link: same browser goes straight into the library; others get a pre-filled log-in.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function setup(reply) {
  const redirects = [];
  const requests = [];
  const elements = new Map();
  const local = new Map();
  const messages = [];
  const location = { pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz',
    assign: destination => redirects.push(destination), reload() {} };
  const context = vm.createContext({
    URLSearchParams, location,
    window: { location, history: { replaceState() {} } },
    document: {
      readyState: 'loading', documentElement: { dataset: { publicShell: 'true' } }, addEventListener() {},
      querySelector: () => ({ scrollIntoView() {} }),
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, { id, style: {}, dataset: {}, value: '', textContent: '', focus() { this.focused = true; } });
        return elements.get(id);
      },
    },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    localStorage: { getItem: key => local.get(key) ?? null, setItem: (key, value) => local.set(key, value), removeItem: key => local.delete(key) },
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: reply.ok !== false, json: async () => reply.body }; },
    setTimeout: callback => callback(),
  });
  vm.runInContext(source, context);
  context.showAuthModal = () => {};
  context.showLoginForm = () => { context.loginShown = true; };
  context.displayAuthSuccess = message => messages.push(message);
  context.displayAuthError = message => messages.push('ERR ' + message);
  return { context, redirects, requests, elements, local, messages };
}

test('same browser: saves the user and opens the library', async () => {
  const s = setup({ body: { message: 'ok', signed_in: true, user: { id: 5, username: 'newfan' } } });
  await s.context.handleEmailVerification('tok');
  assert.equal(s.requests[0].url, '/auth/verify-email?token=tok');
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.deepEqual(s.redirects, ['/']);
  assert.equal(JSON.parse(s.local.get('omnitrackr_user')).username, 'newfan');
  assert.equal(s.context.loginShown, undefined);
});

test('other browser: log-in form with email filled and password focused, no waiting', async () => {
  const s = setup({ body: { message: 'ok', signed_in: false, login_hint: 'newfan@example.com' } });
  await s.context.handleEmailVerification('tok');
  assert.equal(s.redirects.length, 0);
  assert.equal(s.context.loginShown, true);
  assert.equal(s.elements.get('loginUsername').value, 'newfan@example.com');
  assert.equal(s.elements.get('loginPassword').focused, true);
  assert.match(s.messages.at(-1), /Email verified! Log in/);
});

test('already-verified links still lead to the log-in form', async () => {
  const s = setup({ body: { message: 'Email already verified' } });
  await s.context.handleEmailVerification('tok');
  assert.equal(s.redirects.length, 0);
  assert.equal(s.context.loginShown, true);
});

test('expired links show the server message', async () => {
  const s = setup({ ok: false, body: { detail: 'This verification link has expired' } });
  await s.context.handleEmailVerification('tok');
  assert.ok(s.messages.some(m => m === 'ERR This verification link has expired'));
  assert.equal(s.redirects.length, 0);
});
