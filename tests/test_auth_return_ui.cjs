const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const returnKey = 'omnitrackr_discover_auth_return';
const demoKey = 'omnitrackr_demo_start';
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

test('next is only captured at the root, regardless of the selected shell', async () => {
  for (const publicShell of [true, false]) {
    const s = setup({ search: nextQuery('/discover/finding-your-feet'), pathname: '/discover/example', publicShell });
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

test('review save destinations support every media category and return after login without saving', async () => {
  for (const category of ['movie', 'tv_show', 'anime', 'video_game', 'music', 'book']) {
    const destination = `/reviews/2147483647/save?category=${category}`;
    const s = setup({ search: nextQuery(destination) });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, [destination]);
    assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
    assert.equal(s.context.getDiscoverAuthReturn(), null);
  }
});

test('review signup and same-tab email verification preserve only the destination until expiry', async () => {
  const destination = '/reviews/42/save?category=book';
  const firstPage = setup({ search: nextQuery(destination) });
  firstPage.context.initAuth();
  await firstPage.context.register('reader@example.com', 'reader', 'secret-password');
  assert.deepEqual(JSON.parse(firstPage.storage.get(returnKey)), { path: destination, created_at: now });
  assert.deepEqual(firstPage.requests.map(request => request.url), ['/auth/register']);
  const verifiedPage = setup({ search: '?email_verified=true', storage: firstPage.storage });
  verifiedPage.context.initAuth();
  await verifiedPage.context.login('reader', 'secret-password');
  assert.deepEqual(verifiedPage.redirects, [destination]);
  const expired = setup({ storage: new Map([[returnKey, JSON.stringify({ path: destination, created_at: now - ttl })]]) });
  await expired.context.login('reader', 'password');
  assert.deepEqual(expired.redirects, ['/']);
});

test('review return paths reject foreign hosts, ambiguous queries, invalid IDs, encodings, and controls', async () => {
  for (const destination of [
    '//evil.example/reviews/42/save?category=book', 'https://omnitrackr.xyz/reviews/42/save?category=book',
    '/reviews/0/save?category=book', '/reviews/01/save?category=book', '/reviews/-1/save?category=book',
    '/reviews/1.0/save?category=book', '/reviews/1e2/save?category=book', '/reviews/2147483648/save?category=book',
    '/reviews/42/save?category=books', '/reviews/42/save?category=Book', '/reviews/42/save?category=book&category=movie',
    '/reviews/42/save?category=book&next=//evil.example', '/reviews/42/save?category=book&',
    '/reviews/42/save/?category=book', '/reviews/42/save?category=book#save', '/reviews/42/save',
    '/reviews/%34%32/save?category=book', '/reviews/42/save?category=%62ook', '/reviews/../42/save?category=book',
    '/reviews/42/save?category=book\n', '/reviews/42/save?category=book\r', '/reviews/42/save?category=book\u0000',
  ]) {
    const s = setup({ search: nextQuery(destination) });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], destination);
    assert.deepEqual(s.requests.map(request => request.url), ['/auth/login'], destination);
  }
});

test('demo signup opens registration and login returns only to the fixed first-title destination', async () => {
  const s = setup({ search: '?start=demo' });
  s.context.initAuth();
  assert.equal(s.elements.get('registerForm').style.display, 'block');
  assert.equal(s.elements.get('loginForm').style.display, 'none');
  assert.deepEqual(JSON.parse(s.storage.get(demoKey)), { source: 'demo', created_at: now });
  assert.equal(s.requests.length, 0);
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, ['/?start=demo']);
  assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
  assert.equal(s.storage.has(demoKey), false);
  assert.equal(s.context.consumeDiscoverAuthReturn(), '/');
});

test('demo intent survives registration and same-tab verification without carrying sample data', async () => {
  const signup = setup({ search: '?start=demo' });
  signup.context.initAuth();
  await signup.context.register('reader@example.com', 'reader', 'private-password');
  assert.deepEqual(JSON.parse(signup.storage.get(demoKey)), { source: 'demo', created_at: now });
  assert.deepEqual(signup.requests.map(request => request.url), ['/auth/register']);
  const verified = setup({ search: '?email_verified=true', storage: signup.storage });
  verified.context.initAuth();
  assert.equal(verified.elements.has('registerForm'), false);
  await verified.context.login('reader', 'private-password');
  assert.deepEqual(verified.redirects, ['/?start=demo']);
});

test('review, Discover, and collection return destinations take precedence over current or stored demo intent', async () => {
  for (const destination of ['/reviews/42/save?category=book', '/discover/finding-your-feet#save-picks', '/collections/public/42/save']) {
    for (const stored of [false, true]) {
      const storage = new Map([[demoKey, JSON.stringify({ source: 'demo', created_at: now })]]);
      if (stored) storage.set(returnKey, JSON.stringify({ path: destination, created_at: now }));
      const s = setup({ search: stored ? '?start=demo' : `${nextQuery(destination)}&start=demo`, storage });
      s.context.initAuth();
      assert.equal(s.elements.has('registerForm'), false);
      await s.context.login('reader', 'password');
      assert.deepEqual(s.redirects, [destination]);
      assert.equal(s.storage.has(demoKey), false);
    }
  }
});

test('demo intent never overrides verification or password-recovery forms', async () => {
  for (const query of ['reset_token=reset-secret', 'token=verify-secret&email_verified=true', 'email_verified=true', 'password_reset=true', 'email_change_token=change-secret&email_change=true']) {
    const s = setup({ search: `?start=demo&${query}` });
    s.context.handleEmailVerification = () => { s.context.verified = true; };
    s.context.handleEmailChangeVerification = () => { s.context.changed = true; };
    s.context.initAuth();
    assert.notEqual(s.elements.get('registerForm')?.style.display, 'block', query);
    assert.equal(s.context.getDemoStartIntent(), false, query);
    assert.equal(s.redirects.length, 0, query);
  }
});

test('malformed or repeated demo starts cannot retain stale intent or choose a redirect', async () => {
  for (const search of ['?start=', '?start=Demo', '?start=demo%0A', '?start=//evil.example', '?start=demo&start=demo', '?start=demo&next=//evil.example']) {
    const storage = new Map([[demoKey, JSON.stringify({ source: 'demo', created_at: now })]]);
    const s = setup({ search, storage });
    s.context.initAuth();
    assert.notEqual(s.elements.get('registerForm')?.style.display, 'block', search);
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], search);
  }
});

test('stored demo intent expires and rejects malformed timestamps or an unknown source', async () => {
  for (const raw of ['not JSON', 'null', '[]', JSON.stringify({ source: 'demo' }),
    JSON.stringify({ source: 'demo', created_at: String(now) }),
    JSON.stringify({ source: 'demo', created_at: now + 1 }),
    JSON.stringify({ source: 'demo', created_at: now - ttl }),
    JSON.stringify({ source: '//evil.example', created_at: now })]) {
    const s = setup({ storage: new Map([[demoKey, raw]]) });
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], raw);
    assert.equal(s.storage.has(demoKey), false, raw);
  }
  const s = setup({ storage: new Map([[demoKey, JSON.stringify({ source: 'demo', created_at: now - ttl + 1 })]]) });
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, ['/?start=demo']);
});

test('blocked storage supports a current-page demo signup and logout clears its memory fallback', async () => {
  const s = setup({ search: '?start=demo', blockedStorage: true });
  s.context.initAuth();
  assert.equal(s.elements.get('registerForm').style.display, 'block');
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, ['/?start=demo']);
  s.context.initAuth();
  await s.context.logout();
  assert.equal(s.context.getDemoStartIntent(), false);
});

test('demo signup intent is only captured on the server-selected anonymous root shell', async () => {
  for (const options of [{ publicShell: false }, { pathname: '/demo' }]) {
    const s = setup({ search: '?start=demo', ...options });
    s.context.initAuth();
    assert.equal(s.context.getDemoStartIntent(), false);
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/']);
  }
});

test('collection login returns to the exact preview without submitting a copy request', async () => {
  for (const destination of ['/collections/public/1/save', '/collections/public/42/save', '/collections/public/2147483647/save']) {
    const s = setup({ search: nextQuery(destination) });
    s.context.initAuth();
    assert.equal(s.requests.length, 0);
    assert.equal(s.redirects.length, 0);
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, [destination]);
    assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
    assert.equal(s.storage.has(returnKey), false);
    assert.equal(s.context.consumeDiscoverAuthReturn(), '/');
  }
});

test('collection signup and same-tab verification retain only the preview destination for 24 hours', async () => {
  const destination = '/collections/public/42/save';
  const signup = setup({ search: nextQuery(destination) });
  signup.context.initAuth();
  await signup.context.register('reader@example.com', 'reader', 'secret-password');
  assert.deepEqual(JSON.parse(signup.storage.get(returnKey)), { path: destination, created_at: now });
  assert.deepEqual(signup.requests.map(request => request.url), ['/auth/register']);
  assert.deepEqual(signup.redirects, []);
  const verified = setup({ search: '?token=verification-token&email_verified=true', storage: signup.storage });
  verified.context.initAuth();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(verified.requests.map(request => request.url), ['/auth/verify-email?token=verification-token']);
  assert.equal(verified.context.getDiscoverAuthReturn(), destination);
  await verified.context.login('reader', 'secret-password');
  assert.deepEqual(verified.redirects, [destination]);
  assert.deepEqual(verified.requests.map(request => request.url), ['/auth/verify-email?token=verification-token', '/auth/login']);
  for (const createdAt of [now - ttl, now + 1]) {
    const expired = setup({ storage: new Map([[returnKey, JSON.stringify({ path: destination, created_at: createdAt })]]) });
    await expired.context.login('reader', 'password');
    assert.deepEqual(expired.redirects, ['/']);
  }
});

test('collection return paths reject foreign hosts, invalid IDs, suffixes, encodings, and controls', async () => {
  for (const destination of [
    '//evil.example/collections/public/42/save', 'https://omnitrackr.xyz/collections/public/42/save',
    '/\\evil.example/collections/public/42/save', '/collections/public/0/save', '/collections/public/01/save',
    '/collections/public/-1/save', '/collections/public/1.0/save', '/collections/public/1e2/save',
    '/collections/public/2147483648/save', '/collections/public/99999999999/save',
    '/collections/public/42/save/', '/collections/public/42/save?next=//evil.example',
    '/collections/public/42/save?', '/collections/public/42/save#', '/collections/public/42/save#confirm',
    '/collections/public/42/copy', '/collections/public/42', '/collections/public//42/save',
    '/collections/public/%34%32/save', '/collections/public/../42/save', '/collections/public/42%2fsave',
    '/collections/Public/42/save', '/collections/public/42/save\n', '/collections/public/42/save\r',
    '/collections/public/42/save\u0000', '/collections/public/42/save\u2028',
  ]) {
    const storage = new Map([[returnKey, JSON.stringify({ path: '/collections/public/1/save', created_at: now })]]);
    const s = setup({ search: nextQuery(destination), storage });
    s.context.initAuth();
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], destination);
    assert.deepEqual(s.requests.map(request => request.url), ['/auth/login'], destination);
    assert.equal(storage.has(returnKey), false, destination);
  }
});

test('collection return retains recovery form priority and survives a failed login', async () => {
  const destination = '/collections/public/42/save';
  const s = setup({ search: `${nextQuery(destination)}&reset_token=reset-secret&start=demo` });
  s.context.initAuth();
  assert.equal(s.elements.get('resetPasswordFormElement').dataset.resetToken, 'reset-secret');
  assert.equal(s.elements.get('resetPasswordForm').style.display, 'block');
  assert.notEqual(s.elements.get('registerForm')?.style.display, 'block');
  assert.equal(s.context.getDiscoverAuthReturn(), destination);
  const successfulFetch = s.context.fetch;
  s.context.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Invalid credentials' }) });
  await assert.rejects(s.context.login('reader', 'wrong'), /Invalid credentials/);
  assert.deepEqual(s.redirects, []);
  assert.equal(s.context.getDiscoverAuthReturn(), destination);
  s.context.fetch = successfulFetch;
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
});

test('a current-page collection return still works when session storage is unavailable', async () => {
  const destination = '/collections/public/42/save';
  const s = setup({ search: nextQuery(destination), blockedStorage: true });
  s.context.initAuth();
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
  assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
});

test('an expired cookie selecting the legacy root shell still returns login to the collection preview', async () => {
  const destination = '/collections/public/42/save';
  const s = setup({ search: nextQuery(destination), publicShell: false });
  s.context.initAuth();
  assert.equal(s.context.modalCalls, 1);
  assert.equal(s.context.mainUICalls || 0, 0);
  assert.equal(s.context.getDiscoverAuthReturn(), destination);
  await s.context.login('reader', 'password');
  assert.deepEqual(s.redirects, [destination]);
  assert.deepEqual(s.requests.map(request => request.url), ['/auth/login']);
});

test('a legacy-shell 401 clears stale credentials while retaining the chosen save destination', async () => {
  for (const destination of ['/collections/public/42/save', '/reviews/42/save?category=book', '/discover/finding-your-feet#save-picks']) {
    const s = setup({ search: nextQuery(destination), publicShell: false });
    s.context.saveAuthData(null, { id: 1, username: 'reader' });
    s.context.initAuth();
    assert.equal(s.context.mainUICalls, 1);
    const successfulFetch = s.context.fetch;
    s.context.fetch = async (url, options) => {
      s.requests.push({ url, options });
      return { ok: false, status: 401 };
    };
    await assert.rejects(s.context.authenticatedFetch('/auth/me'), /Session expired/);
    assert.equal(s.context.isAuthenticated(), false);
    assert.equal(s.context.modalCalls, 1);
    assert.equal(s.context.getDiscoverAuthReturn(), destination);
    s.context.fetch = successfulFetch;
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, [destination]);
    assert.deepEqual(s.requests.map(request => request.url), ['/auth/me', '/auth/login']);
    assert.equal(s.storage.has(returnKey), false);
  }
});

test('legacy-shell invalid or ambiguous next parameters cannot keep a previous save destination', async () => {
  const destination = '/collections/public/42/save';
  for (const search of [nextQuery('//evil.example'), nextQuery('/collections/public/42/save?next=//evil.example'),
    nextQuery('/collections/public/0/save'), `${nextQuery(destination)}&next=${encodeURIComponent(destination)}`]) {
    const storage = new Map([[returnKey, JSON.stringify({ path: destination, created_at: now })]]);
    const s = setup({ search, publicShell: false, storage });
    s.context.initAuth();
    assert.equal(s.context.getDiscoverAuthReturn(), null);
    await s.context.login('reader', 'password');
    assert.deepEqual(s.redirects, ['/'], search);
    assert.equal(storage.has(returnKey), false);
  }
});

test('explicit logout clears a collection destination retained during expired-session recovery', async () => {
  const s = setup({ search: nextQuery('/collections/public/42/save'), publicShell: false });
  s.context.initAuth();
  s.context.clearAuth({ preserveReturn: true });
  assert.equal(s.context.getDiscoverAuthReturn(), '/collections/public/42/save');
  await s.context.logout();
  assert.equal(s.context.getDiscoverAuthReturn(), null);
  assert.equal(s.storage.has(returnKey), false);
});
