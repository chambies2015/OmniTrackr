// Coming back to a sign-up that waits for its code (Nov 23 2026). People leave the code step
// to read the email; on a phone the tab often reloads when they return, or they open the site
// in a new tab, and the homepage used to look as if they had never signed up. The card now
// asks the server (which reads the pending-signup cookie) and opens the code step again.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function setup(replies, { finePointer = false } = {}) {
  const queue = Array.isArray(replies) ? [...replies] : [replies];
  const requests = [];
  const events = [];
  const elements = new Map();
  const local = new Map();
  const session = new Map();
  const location = { pathname: '/', search: '', hash: '', protocol: 'https:', origin: 'https://omnitrackr.xyz',
    assign() {}, reload() {} };
  function el(id) {
    const node = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, className: '', attrs: {}, listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      focus() { focused.id = id; },
      select() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      reset() {},
    };
    elements.set(id, node);
    return node;
  }
  const focused = { id: null };
  const context = vm.createContext({
    URLSearchParams, location, Date,
    Blob: function Blob(parts) { this.parts = parts; },
    navigator: { sendBeacon: (url, blob) => { events.push(JSON.parse(blob.parts[0]).event); return true; } },
    window: {
      location, history: { replaceState() {} },
      matchMedia: () => ({ matches: finePointer }),
    },
    document: {
      readyState: 'loading', documentElement: { dataset: { publicShell: 'true' } }, addEventListener() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      getElementById(id) { return id === 'registerConfirmPassword' ? null : elements.get(id) || el(id); },
    },
    sessionStorage: { getItem: key => session.get(key) ?? null, setItem: (key, value) => session.set(key, value), removeItem: key => session.delete(key) },
    localStorage: { getItem: key => local.get(key) ?? null, setItem: (key, value) => local.set(key, value), removeItem: key => local.delete(key) },
    fetch: async (url, options) => {
      requests.push({ url, options });
      const reply = queue.length > 1 ? queue.shift() : queue[0];
      if (reply === 'offline') throw new TypeError('Failed to fetch');
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
  context.revealAuthCard = () => { context.revealed = (context.revealed || 0) + 1; };
  return { context, requests, events, elements, local, session, focused, $: id => context.document.getElementById(id),
    get: name => vm.runInContext(name, context) };
}

test('the code step leaves a mark with the time only, never the address', () => {
  const s = setup({ body: {} });
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  const mark = s.local.get('omnitrackr_signup_waiting');
  assert.match(mark, /^\d{13}$/);
  assert.ok(![...s.local.values()].some(value => String(value).includes('sam@gmail.com')));
  // A reset link isn't a sign-up.
  const r = setup({ body: {} });
  r.context.showInboxPanel('reset', 'sam@gmail.com');
  assert.equal(r.local.has('omnitrackr_signup_waiting'), false);
});

test('a mark older than 48 hours is dropped', () => {
  const s = setup({ body: {} });
  s.local.set('omnitrackr_signup_waiting', String(Date.now() - 49 * 3600 * 1000));
  assert.equal(s.context.signupWaitingMarked(), false);
  assert.equal(s.local.has('omnitrackr_signup_waiting'), false);
  s.local.set('omnitrackr_signup_waiting', String(Date.now() - 3600 * 1000));
  assert.equal(s.context.signupWaitingMarked(), true);
});

test('back on the homepage with a sign-up waiting, the code step opens again', async () => {
  const s = setup({ body: { waiting: true, email: 'sam@gmail.com' } });
  assert.equal(await s.context.resumeWaitingSignup(), true);
  assert.equal(s.requests[0].url, '/auth/pending-signup');
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.equal(s.$('authTitle').textContent, 'Confirm your email');
  assert.equal(s.$('verifySentEmail').textContent, 'sam@gmail.com');
  assert.equal(s.$('verifyCodeForm').hidden, false);
  assert.equal(s.context.revealed, 1);
  assert.deepEqual(s.events, ['signup_waiting_resumed']);
});

test('closing the pop-up on the code step keeps later pages in this tab from opening it', async () => {
  const s = setup({ body: { waiting: true, email: 'sam@gmail.com' } });
  s.context.watchAuthDialogClose();
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('authDialog').listeners.close();
  assert.equal(s.session.get('omnitrackr_signup_waiting_closed'), '1');
  assert.equal(await s.context.resumeWaitingSignup(), true);
  assert.equal(s.context.revealed, undefined);
  assert.equal(s.$('authTitle').textContent, 'Confirm your email');
});

test('confirmed meanwhile in another browser: the log-in form, with the address in', async () => {
  const s = setup({ body: { waiting: false, confirmed: true, login_hint: 'sam@gmail.com' } });
  s.local.set('omnitrackr_signup_waiting', String(Date.now()));
  assert.equal(await s.context.resumeWaitingSignup(), true);
  assert.equal(s.$('loginForm').style.display, 'block');
  assert.equal(s.$('loginUsername').value, 'sam@gmail.com');
  assert.match(s.$('authSuccess').textContent, /Your email is confirmed/);
  assert.equal(s.focused.id, 'loginPassword');
  assert.equal(s.local.has('omnitrackr_signup_waiting'), false);
  assert.deepEqual(s.events, ['signup_waiting_confirmed']);
});

test('nothing waiting: the mark goes and the page opens as usual', async () => {
  const s = setup({ body: { waiting: false } });
  s.local.set('omnitrackr_signup_waiting', String(Date.now()));
  assert.equal(await s.context.resumeWaitingSignup(), false);
  assert.equal(s.local.has('omnitrackr_signup_waiting'), false);
  assert.deepEqual(s.events, []);
});

test('offline or rate limited: the mark stays for the next visit', async () => {
  for (const reply of ['offline', { ok: false, status: 429, body: {} }]) {
    const s = setup(reply);
    s.local.set('omnitrackr_signup_waiting', String(Date.now()));
    assert.equal(await s.context.resumeWaitingSignup(), false);
    assert.equal(s.local.has('omnitrackr_signup_waiting'), true);
  }
});

test('a sign-up button pressed again goes back to the code step', () => {
  const s = setup({ body: {} });
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.context.showLoginForm(false);
  s.context.showRegisterForm(false);
  assert.equal(s.$('authTitle').textContent, 'Check your inbox');
  assert.equal(s.$('verifySentPanel').style.display, 'block');
  assert.equal(s.$('registerForm').style.display, 'none');
});

test('Wrong address? Start again clears the waiting sign-up and opens an empty form', () => {
  const s = setup({ body: {} });
  s.context.setupInboxPanel();
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifySentRestart').listeners.click({ preventDefault() {} });
  assert.equal(s.$('registerForm').style.display, 'block');
  assert.equal(s.$('authTitle').textContent, 'Create your free account');
  assert.equal(s.local.has('omnitrackr_signup_waiting'), false);
  assert.equal(s.get('signupWaiting'), null);
  assert.ok(s.events.includes('signup_restart_clicked'));
});

test('signing in by any route clears the mark', async () => {
  const s = setup({ body: { signed_in: true, user: { id: 9, username: 'sam' } } });
  s.context.setupInboxPanel();
  s.context.showInboxPanel('verify', 'sam@gmail.com');
  s.$('verifyCode').value = '123456';
  await s.context.submitSignupCode();
  assert.equal(s.local.has('omnitrackr_signup_waiting'), false);
  const t = setup({ body: {} });
  t.context.showInboxPanel('pending', 'sam@gmail.com');
  t.context.saveAuthData(null, { id: 9, username: 'sam' });
  assert.equal(t.local.has('omnitrackr_signup_waiting'), false);
});

test('with a mouse the cursor lands in the code box; on a touch screen on the heading', () => {
  const mouse = setup({ body: {} }, { finePointer: true });
  mouse.context.showInboxPanel('verify', 'sam@gmail.com');
  assert.equal(mouse.focused.id, 'verifyCode');
  mouse.context.showInboxPanel('reset', 'sam@gmail.com');
  assert.equal(mouse.focused.id, 'authTitle');
  const touch = setup({ body: {} });
  touch.context.showInboxPanel('verify', 'sam@gmail.com');
  assert.equal(touch.focused.id, 'authTitle');
});

test('a slow mail server is said on the code step', async () => {
  const s = setup({ status: 201, headers: { 'X-Verification-Email': 'sending' }, body: { id: 3 } });
  await s.context.register('sam@gmail.com', 'sam', 'tea on the porch');
  assert.equal(s.$('authTitle').textContent, 'Check your inbox');
  assert.match(s.$('verifySentStatus').textContent, /may take a minute or two/);
});

test('a Create press that never reaches the server is counted and explained', async () => {
  const s = setup('offline');
  await assert.rejects(s.context.register('sam@gmail.com', 'sam', 'tea on the porch'), /couldn't reach OmniTrackr/);
  assert.deepEqual(s.events, ['signup_request_failed']);
  const down = setup({ ok: false, status: 502, body: {} });
  await assert.rejects(down.context.register('sam@gmail.com', 'sam', 'tea on the porch'));
  assert.deepEqual(down.events, ['signup_request_failed']);
  const taken = setup({ ok: false, status: 400, body: { detail: 'Username already taken.' } });
  await assert.rejects(taken.context.register('sam@gmail.com', 'sam', 'tea on the porch'));
  assert.deepEqual(taken.events, []);
});

test('the form checks say which box stopped the visitor', async () => {
  const cases = [['sam@', 'tea on the porch', 'signup_check_email'], ['sam@gmail.com', 'short', 'signup_check_password']];
  for (const [email, password, event] of cases) {
    const s = setup({ body: {} });
    s.context.setupAuthHandlers();
    s.$('registerEmail').value = email;
    s.$('registerUsername').value = 'sam';
    s.$('registerPassword').value = password;
    await s.$('registerFormElement').listeners.submit({ preventDefault() {}, target: s.$('registerFormElement') });
    assert.ok(s.events.includes('signup_rejected_invalid'), event);
    assert.ok(s.events.includes(event), event);
    assert.equal(s.requests.length, 0);
  }
});

test('a suggested username that is reserved is swapped like a taken one', () => {
  const s = setup({ body: {} });
  const box = s.$('registerUsername');
  box.value = 'owner';
  box.dataset.suggested = 'true';
  const message = s.context.offerAnotherUsername('This username is reserved. Choose a different username.');
  assert.match(box.value, /^owner\d{2}$/);
  assert.match(message, /^owner is taken, so we changed it to owner\d{2}\./);
});
