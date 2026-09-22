const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const returnKey = 'omnitrackr_discover_auth_return';
const now = 1900000000000;
const ttl = 24 * 60 * 60 * 1000;
const nextQuery = destination => `?next=${encodeURIComponent(destination)}`;

function setup({ search = '', pathname = '/', publicShell = true, storage = new Map(), blockedStorage = false } = {}) {
  const redirects = [];
  const requests = [];
  const elements = new Map();
  const local = new Map();
  const location = {
    pathname, search, protocol: 'https:', origin: 'https://omnitrackr.xyz',
    assign: destination => redirects.push(destination), reload() {},
  };
  const context = vm.createContext({
    URLSearchParams,
    Date: { now: () => now },
    location,
    window: { location, history: { replaceState() {} } },
    document: {
      readyState: 'loading',
      documentElement: { dataset: { publicShell: String(publicShell) } },
      addEventListener() {},
      querySelector: () => ({ scrollIntoView() {} }),
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, { style: {}, dataset: {}, reset() {} });
        return elements.get(id);
      },
    },
    sessionStorage: {
      getItem(key) { if (blockedStorage) throw new Error('Storage blocked'); return storage.get(key) ?? null; },
      setItem(key, value) { if (blockedStorage) throw new Error('Storage blocked'); storage.set(key, value); },
      removeItem(key) { if (blockedStorage) throw new Error('Storage blocked'); storage.delete(key); },
    },
    localStorage: {
      getItem: key => local.get(key) ?? null,
      setItem: (key, value) => local.set(key, value),
      removeItem: key => local.delete(key),
    },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => ({ user: { id: 1, username: 'reader' } }) };
    },
    confirm: () => true,
    setTimeout: callback => callback(),
  });
  vm.runInContext(source, context);
  context.setupAuthHandlers = () => {};
  context.showAuthModal = () => { context.modalCalls = (context.modalCalls || 0) + 1; };
  context.showMainUI = () => { context.mainUICalls = (context.mainUICalls || 0) + 1; };
  context.showLoginForm = () => {};
  context.updateUserDisplay = () => {};
  context.displayAuthSuccess = () => {};
  return { context, storage, redirects, requests, elements };
}

test('successful login returns to the chosen trail without saving or submitting other requests', async () => {
  const destination = '/discover/finding-your-feet#save-picks';
  const s = setup({ search: nextQuery(destination) });
  s.context.initAuth();
  assert.equal(s.redirects.length, 0);
  assert.equal(s.requests.length, 0);
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
  assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
  assert.equal(s.storage.has(returnKey), false);
  assert.equal(s.context.consumeDiscoverAuthReturn(), '/');
});

test('monthly destinations and detail URLs without an anchor are supported', async () => {
  for (const destination of ['/discover/monthly/september-2026#save-picks', '/discover/clever-mysteries']) {
    const s = setup({ search: nextQuery(destination) });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, [destination]);
  }
});

test('ordinary successful login retains its dashboard destination', async () => {
  const s = setup();
  s.context.initAuth();
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, ['/']);
});

test('failed login preserves the chosen destination for a successful retry', async () => {
  const destination = '/discover/finding-your-feet#save-picks';
  const s = setup({ search: nextQuery(destination) });
  s.context.initAuth();
  const successfulFetch = s.context.fetch;
  s.context.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Invalid credentials' }) });
  await assert.rejects(s.context.login('reader', 'wrong'), /Invalid credentials/);
  assert.equal(s.context.getDiscoverAuthReturn(), destination);
  assert.equal(s.redirects.length, 0);
  s.context.fetch = successfulFetch;
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
});

test('registration and same-tab verification navigation retain the intent without storing credentials', async () => {
  const destination = '/discover/monthly/september-2026#save-picks';
  const firstPage = setup({ search: nextQuery(destination) });
  firstPage.context.initAuth();
  await firstPage.context.register('reader@example.com', 'reader', 'secret-password');
  assert.deepEqual(JSON.parse(firstPage.storage.get(returnKey)), { path: destination, created_at: now });
  assert.equal(firstPage.redirects.length, 0);
  const verifiedPage = setup({ search: '?email_verified=true', storage: firstPage.storage });
  verifiedPage.context.initAuth();
  await verifiedPage.context.login('reader', 'secret-password');
  assert.deepEqual(verifiedPage.redirects, [destination]);
});

test('public-shell verification links reach the verification API before the ordinary login fallback', async () => {
  const s = setup({ search: '?token=verification-token&email_verified=true' });
  s.context.initAuth();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(s.requests.map(request => request.url), ['/auth/verify-email?token=verification-token']);
  assert.equal(s.context.modalCalls, 1);
  assert.equal(s.context.mainUICalls || 0, 0);
});

test('public-shell password reset links open the reset form with the provided token', () => {
  const s = setup({ search: '?reset_token=password-reset-token' });
  s.context.initAuth();
  assert.equal(s.elements.get('resetPasswordFormElement').dataset.resetToken, 'password-reset-token');
  assert.equal(s.elements.get('resetPasswordForm').style.display, 'block');
  assert.equal(s.context.modalCalls, 1);
  assert.equal(s.context.mainUICalls || 0, 0);
});

test('public-shell email-change links still dispatch to their dedicated handler', () => {
  const s = setup({ search: '?email_change_token=change-token&email_change=true' });
  const tokens = [];
  s.context.handleEmailChangeVerification = token => tokens.push(token);
  s.context.initAuth();
  assert.deepEqual(tokens, ['change-token']);
  assert.equal(s.context.mainUICalls || 0, 0);
});

test('an ordinary public shell never opens the private UI from stale local authentication data', () => {
  const s = setup();
  s.context.saveAuthData(null, { id: 1, username: 'reader' });
  s.context.initAuth();
  assert.equal(s.context.modalCalls, 1);
  assert.equal(s.context.mainUICalls || 0, 0);
});

test('unsafe and malformed destinations cannot redirect or retain an older intent', async () => {
  for (const destination of [
    'https://evil.example/discover/example', 'https://omnitrackr.xyz/discover/example',
    '//evil.example/discover/example', '/\\evil.example/discover/example',
    '/discover%2Fexample', '/discover/%2e%2e/example', '/discover/monthly/../example',
    '/discover/example?next=https://evil.example', '/discover/example#other',
    '/discover/example\n', '/discover/example#save-picks\n', '/discover/example\u0000',
    '/discover/', '/discover/monthly/', '/discover/example/', '/account/',
    '/discover/EXAMPLE', '/discover/café', '', '/discover/' + 'a'.repeat(181),
  ]) {
    const storage = new Map([[returnKey, JSON.stringify({ path: '/discover/old', created_at: now })]]);
    const s = setup({ search: nextQuery(destination), storage });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], destination);
    assert.equal(storage.has(returnKey), false, destination);
  }
});

test('ambiguous repeated next parameters clear the previous intent', async () => {
  const storage = new Map([[returnKey, JSON.stringify({ path: '/discover/old', created_at: now })]]);
  const s = setup({ search: '?next=%2Fdiscover%2Fone&next=%2Fdiscover%2Ftwo', storage });
  s.context.initAuth();
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, ['/']);
});

test('next is only captured on the public root landing page', async () => {
  for (const options of [{ publicShell: false }, { pathname: '/discover/example' }]) {
    const s = setup({ search: nextQuery('/discover/finding-your-feet'), ...options });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/']);
  }
});

test('stored context is revalidated and expired, future, or malformed state is discarded', async () => {
  for (const raw of [
    'not JSON', 'null', '[]', JSON.stringify({ path: '/discover/example' }),
    JSON.stringify({ path: '//evil.example', created_at: now }),
    JSON.stringify({ path: '/discover/example', created_at: String(now) }),
    JSON.stringify({ path: '/discover/example', created_at: now - ttl }),
    JSON.stringify({ path: '/discover/example', created_at: now + 1 }),
  ]) {
    const storage = new Map([[returnKey, raw]]);
    const s = setup({ storage });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], raw);
    assert.equal(storage.has(returnKey), false, raw);
  }
});

test('valid session context survives until just before its 24-hour expiry', async () => {
  const destination = '/discover/example#save-picks';
  const storage = new Map([[returnKey, JSON.stringify({ path: destination, created_at: now - ttl + 1 })]]);
  const s = setup({ storage });
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
});

test('logging out clears return context along with authentication state', async () => {
  const s = setup({ search: nextQuery('/discover/example') });
  s.context.initAuth();
  await s.context.logout();
  assert.equal(s.storage.has(returnKey), false);
  assert.equal(s.context.getDiscoverAuthReturn(), null);
});

test('blocked session storage does not prevent login or the current page return', async () => {
  for (const destination of [null, '/discover/example#save-picks']) {
    const s = setup({ search: destination ? nextQuery(destination) : '', blockedStorage: true });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, [destination || '/']);
  }
});
