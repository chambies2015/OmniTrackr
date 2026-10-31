const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const now = 1900000000000;

function setup({ search = '', publicShell = false, me = { id: 7, username: 'Riley' }, session = new Map(), known = false, signup = false } = {}) {
  const replaced = [];
  const requests = [];
  const history = [];
  const elements = new Map();
  const links = [{ href: '/auth/google/start', listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; },
    hasAttribute: name => signup && name === 'data-google-signup' }];
  const beacons = [];
  const local = new Map(known ? [['omnitrackr_known_member', '1']] : []);
  const location = {
    pathname: '/', search, protocol: 'https:', origin: 'https://omnitrackr.xyz',
    assign: destination => replaced.push(destination), replace: destination => replaced.push(destination), reload() {},
  };
  const context = vm.createContext({
    URLSearchParams,
    Date: { now: () => now },
    location,
    window: { location, history: { replaceState: (_, __, url) => history.push(url) } },
    document: {
      title: 'OmniTrackr',
      readyState: 'loading',
      documentElement: { dataset: { publicShell: String(publicShell) } },
      addEventListener() {},
      querySelector: () => ({ scrollIntoView() {} }),
      querySelectorAll: selector => (selector === '[data-google-signin]' ? links : []),
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, { style: {}, dataset: {}, textContent: '', reset() {} });
        return elements.get(id);
      },
    },
    sessionStorage: {
      getItem: key => session.get(key) ?? null,
      setItem: (key, value) => session.set(key, value),
      removeItem: key => session.delete(key),
    },
    localStorage: {
      getItem: key => local.get(key) ?? null,
      setItem: (key, value) => local.set(key, value),
      removeItem: key => local.delete(key),
    },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return me ? { ok: true, json: async () => me } : { ok: false, status: 401, json: async () => ({}) };
    },
    navigator: { sendBeacon: (url, blob) => { beacons.push({ url, blob }); return true; } },
    Blob: class { constructor(parts) { this.text = parts.join(''); } },
    confirm: () => true,
    setTimeout: callback => callback(),
  });
  vm.runInContext(source, context);
  context.setupAuthHandlers = () => {};
  context.showAuthModal = () => { context.modalCalls = (context.modalCalls || 0) + 1; };
  context.showMainUI = () => {};
  context.showLoginForm = () => { context.form = 'login'; };
  context.showRegisterForm = () => { context.form = 'register'; };
  context.updateUserDisplay = () => {};
  return { context, replaced, requests, history, elements, links, local, session, beacons };
}

test('returning from Google saves the member and opens the library', async () => {
  const s = setup({ search: '?signed_in=google' });
  await s.context.initAuth();
  assert.deepEqual(s.requests.map(request => request.url), ['/account/me']);
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.deepEqual(JSON.parse(s.local.get('omnitrackr_user')), { id: 7, username: 'Riley' });
  assert.equal(s.local.get('omnitrackr_known_member'), '1');
  assert.deepEqual(s.replaced, ['/']);
});

test('returning from Google goes back to the page the visitor came from', async () => {
  const session = new Map([['omnitrackr_discover_auth_return', JSON.stringify({ path: '/discover/finding-your-feet#save-picks', created_at: now })]]);
  const s = setup({ search: '?signed_in=google&new=1', session });
  await s.context.initAuth();
  assert.deepEqual(s.replaced, ['/discover/finding-your-feet#save-picks']);
  assert.equal(session.has('omnitrackr_discover_auth_return'), false);
});

test('a missing session after Google shows the log-in form with a plain message', async () => {
  const s = setup({ search: '?signed_in=google', me: null });
  await s.context.initAuth();
  assert.deepEqual(s.replaced, []);
  assert.equal(s.context.modalCalls, 1);
  assert.match(s.elements.get('authError').textContent, /Google sign-in didn't work/);
  assert.deepEqual(s.history, ['/']);
});

test('google_error codes map to fixed sentences and never echo the address bar', () => {
  const s = setup({ search: '?google_error=deactivated', publicShell: true, known: true });
  s.context.initAuth();
  assert.equal(s.context.form, 'login');
  assert.match(s.elements.get('authError').textContent, /deactivated/);
  assert.deepEqual(s.history, ['/#landing-auth']);
  const forged = setup({ search: '?google_error=%3Cimg%20src%3Dx%3E', publicShell: true });
  forged.context.initAuth();
  assert.equal(forged.context.form, 'register');
  assert.match(forged.elements.get('authError').textContent, /Google sign-in didn't work/);
  assert.doesNotMatch(forged.elements.get('authError').textContent, /img/);
});

test('the Google button carries a friend invite along', () => {
  const session = new Map([['omnitrackr_friend_invite', 'abcdefghijklmnop1234']]);
  const s = setup({ publicShell: true, session });
  s.context.initAuth();
  s.links[0].listeners.click();
  assert.equal(s.links[0].href, '/auth/google/start?invite=abcdefghijklmnop1234');
});

test('a Google sign-up button counts as starting to sign up, once per visit', () => {
  const session = new Map();
  const s = setup({ publicShell: true, session, signup: true });
  s.context.initAuth();
  s.links[0].listeners.click();
  s.links[0].listeners.click();
  assert.deepEqual(s.beacons.map(beacon => JSON.parse(beacon.blob.text).event), ['signup_form_opened']);
  assert.deepEqual(JSON.parse(session.get('omnitrackr_funnel_sent')), ['signup_form_opened']);
  // A later page in the same visit doesn't count it again.
  const next = setup({ publicShell: true, session, signup: true });
  next.context.initAuth();
  next.links[0].listeners.click();
  assert.equal(next.beacons.length, 0);
});

test('the Google log-in button is not a sign-up', () => {
  const s = setup({ publicShell: true });
  s.context.initAuth();
  s.links[0].listeners.click();
  assert.equal(s.beacons.length, 0);
});
