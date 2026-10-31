// Passkeys in the browser: the log-in button, the bytes that go to and from
// navigator.credentials, and adding a passkey from Settings.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const authSource = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const passkeySource = fs.readFileSync(path.join(__dirname, '../app/static/passkeys.js'), 'utf8');

function bytes(text) {
  return new TextEncoder().encode(text).buffer;
}

function fakeCredential(kind) {
  const response = { clientDataJSON: bytes('{"type":"webauthn.' + kind + '"}') };
  if (kind === 'create') {
    response.attestationObject = bytes('attestation');
    response.getTransports = () => ['internal', 'hybrid'];
  } else {
    response.authenticatorData = bytes('authdata');
    response.signature = bytes('sig');
    response.userHandle = null;
  }
  return { id: 'Y3JlZC1pZA', rawId: bytes('cred-id'), type: 'public-key', authenticatorAttachment: 'platform', response };
}

function setup({ replies = [], supported = true, conditional = false, credential, credentialError, settings = false } = {}) {
  const elements = new Map();
  const requests = [];
  const stored = {};
  const assigned = [];
  const credentialCalls = [];
  const domListeners = [];
  function node(id, props = {}) {
    const item = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, checked: false, attrs: {}, listeners: {},
      children: [], className: '', disabled: false,
      classList: { toggle() {}, add() {}, remove() {} },
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
      append(...kids) { this.children.push(...kids); },
      appendChild(kid) { this.children.push(kid); return kid; },
      replaceChildren(...kids) { this.children = kids; },
      contains() { return true; },
      closest() { return null; },
      focus() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      ...props,
    };
    return item;
  }
  function el(id, props = {}) {
    const item = node(id, props);
    elements.set(id, item);
    return item;
  }
  const document = {
    readyState: 'loading', title: '', documentElement: { dataset: { publicShell: 'true' } },
    addEventListener(type, fn) { if (type === 'DOMContentLoaded') domListeners.push(fn); },
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: tag => node(`${tag}${elements.size}`),
    getElementById(id) { return elements.get(id) || el(id); },
  };
  el('accountModal', { style: { display: 'none' } });
  const submit = el('loginSubmit', { textContent: 'Log in' });
  el('loginFormElement', { querySelector: selector => (selector === 'button[type="submit"]' ? submit : null) });
  if (settings) {
    const addSubmit = el('passkeyAddSubmit', { textContent: 'Add a passkey' });
    el('passkeyAddForm', { querySelector: selector => (selector === 'button[type="submit"]' ? addSubmit : null) });
    el('passkeySection');
  }
  const location = { pathname: '/', search: '', assign(url) { assigned.push(url); } };
  const queue = replies.slice();
  const storage = {
    getItem: key => (key in stored ? stored[key] : null),
    setItem(key, value) { stored[key] = String(value); },
    removeItem(key) { delete stored[key]; },
  };
  function PublicKeyCredential() {}
  PublicKeyCredential.isConditionalMediationAvailable = async () => conditional;
  const credentials = {
    async get(options) {
      credentialCalls.push({ kind: 'get', options });
      if (credentialError) throw credentialError;
      return credential === undefined ? fakeCredential('get') : credential;
    },
    async create(options) {
      credentialCalls.push({ kind: 'create', options });
      if (credentialError) throw credentialError;
      return credential === undefined ? fakeCredential('create') : credential;
    },
  };
  const window = { location, history: { replaceState() {} } };
  if (supported) window.PublicKeyCredential = PublicKeyCredential;
  const context = vm.createContext({
    URLSearchParams, location, document, window, Blob: function Blob() {},
    navigator: { sendBeacon: () => true, credentials },
    localStorage: storage,
    sessionStorage: storage,
    atob, btoa, TextEncoder, Uint8Array, ArrayBuffer, AbortController,
    fetch: async (url, options) => {
      requests.push({ url, options });
      const reply = queue.shift() || { ok: true, body: {} };
      if (reply.hold) await reply.hold;
      return { ok: reply.ok !== false, status: reply.status || 200, json: async () => reply.body };
    },
    setTimeout: () => 0,
  });
  if (supported) context.PublicKeyCredential = PublicKeyCredential;
  vm.runInContext(authSource, context);
  const before = domListeners.length;
  context.authenticatedFetch = (url, options) => context.fetch(url, options);
  vm.runInContext(passkeySource, context);
  domListeners.slice(before).forEach(fn => fn());
  const tick = () => new Promise(resolve => setImmediate(resolve));
  async function settle() { for (let i = 0; i < 12; i += 1) await tick(); }
  return { context, elements, requests, stored, assigned, credentialCalls, el, settle, $: id => document.getElementById(id) };
}

test('without passkey support the button stays hidden and the username box is left alone', () => {
  const s = setup({ supported: false });
  const button = s.el('passkeyLoginButton', { hidden: true });
  assert.equal(button.hidden, true);
  assert.equal(s.$('loginUsername').attrs.autocomplete, undefined);
});

test('base64url and bytes round-trip, including the characters plain base64 would get wrong', () => {
  const s = setup();
  const api = s.context.window.OmniPasskeys;
  const text = api.toText(new Uint8Array([251, 255, 191, 0, 62, 63]).buffer);
  assert.equal(text, '-_-_AD4_');
  assert.deepEqual(Array.from(new Uint8Array(api.toBytes(text))), [251, 255, 191, 0, 62, 63]);
  assert.deepEqual(Array.from(new Uint8Array(api.toBytes('AQID'))), [1, 2, 3]);
});

test('the button asks the device for a passkey and finishes the log-in', async () => {
  const user = { id: 7, username: 'reader' };
  const s = setup({ replies: [
    { body: { challenge: 'Y2hhbGxlbmdl', rpId: 'omnitrackr.xyz', userVerification: 'required', allowCredentials: [] } },
    { body: { access_token: 'x', user, signed_in_with: 'passkey' } },
  ] });
  const button = s.$('passkeyLoginButton');
  assert.equal(button.hidden, false);
  assert.equal(s.$('loginUsername').attrs.autocomplete, 'username webauthn');
  await button.listeners.click[0]();
  await s.settle();
  assert.equal(s.requests.length, 2);
  assert.match(s.requests[0].url, /\/auth\/passkey\/options$/);
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.equal(s.credentialCalls.length, 1);
  const { options } = s.credentialCalls[0];
  assert.notEqual(options.mediation, 'conditional');
  assert.equal(options.publicKey.rpId, 'omnitrackr.xyz');
  assert.equal(new TextDecoder().decode(options.publicKey.challenge), 'challenge');
  assert.match(s.requests[1].url, /\/auth\/passkey\/login$/);
  const sent = JSON.parse(s.requests[1].options.body);
  assert.equal(sent.id, 'Y3JlZC1pZA');
  assert.equal(sent.rawId, 'Y3JlZC1pZA');
  assert.equal(sent.response.signature, 'c2ln');
  assert.equal(sent.response.authenticatorData, 'YXV0aGRhdGE');
  assert.equal(sent.response.userHandle, null);
  assert.deepEqual(s.assigned, ['/']);
  assert.equal(JSON.parse(s.stored.omnitrackr_user).username, 'reader');
  assert.equal(button.disabled, false);
});

test('a cancelled prompt says nothing and sends nothing', async () => {
  const error = Object.assign(new Error('cancelled'), { name: 'NotAllowedError' });
  const s = setup({ replies: [{ body: { challenge: 'Y2hhbGxlbmdl', rpId: 'x', allowCredentials: [] } }], credentialError: error });
  await s.$('passkeyLoginButton').listeners.click[0]();
  await s.settle();
  assert.equal(s.requests.length, 1);
  assert.equal(s.$('authError').textContent, '');
  assert.deepEqual(s.assigned, []);
});

test('a passkey the server no longer knows is explained on the card', async () => {
  const s = setup({ replies: [
    { body: { challenge: 'Y2hhbGxlbmdl', rpId: 'x', allowCredentials: [] } },
    { ok: false, status: 401, body: { detail: "We don't know that passkey. It may have been removed from the account." } },
  ] });
  await s.$('passkeyLoginButton').listeners.click[0]();
  await s.settle();
  assert.match(s.$('authError').textContent, /don't know that passkey/);
  assert.deepEqual(s.assigned, []);
});

test('the username box offers saved passkeys once the form is touched', async () => {
  const s = setup({ conditional: true, replies: [
    { body: { challenge: 'Y2hhbGxlbmdl', rpId: 'x', allowCredentials: [] } },
    { body: { access_token: 'x', user: { id: 1, username: 'reader' } } },
  ] });
  s.$('loginUsername').listeners.focus[0]();
  await s.settle();
  assert.equal(s.credentialCalls.length, 1);
  assert.equal(s.credentialCalls[0].options.mediation, 'conditional');
  assert.ok(s.credentialCalls[0].options.signal);
  assert.deepEqual(s.assigned, ['/']);
});

test('clicking the button while the autofill challenge is still loading leaves one prompt, not two', async () => {
  let release;
  const hold = new Promise(resolve => { release = resolve; });
  const s = setup({ conditional: true, replies: [
    { hold, body: { challenge: 'Zmlyc3Q', rpId: 'x', allowCredentials: [] } },
    { body: { challenge: 'c2Vjb25k', rpId: 'x', allowCredentials: [] } },
    { body: { access_token: 'x', user: { id: 1, username: 'reader' } } },
  ] });
  s.$('loginUsername').listeners.focus[0]();
  await s.settle();
  const clicking = s.$('passkeyLoginButton').listeners.click[0]();
  await s.settle();
  release();
  await clicking;
  await s.settle();
  // The superseded autofill request never reached the device; the button's did, with the newer challenge.
  assert.equal(s.credentialCalls.length, 1);
  assert.notEqual(s.credentialCalls[0].options.mediation, 'conditional');
  assert.equal(new TextDecoder().decode(s.credentialCalls[0].options.publicKey.challenge), 'second');
  assert.deepEqual(s.assigned, ['/']);
  assert.equal(s.$('authError').textContent, '');
});

function settingsForm(s) {
  return { form: s.$('passkeyAddForm'), submit: s.$('passkeyAddSubmit') };
}

test('adding a passkey sends the password for a challenge, then what the device made', async () => {
  const s = setup({ settings: true, replies: [
    { body: { rp: { id: 'omnitrackr.xyz', name: 'OmniTrackr' }, user: { id: 'dXNlcg', name: 'reader', displayName: 'reader' },
              challenge: 'Y2hhbGxlbmdl', pubKeyCredParams: [], excludeCredentials: [{ type: 'public-key', id: 'b2xk' }] } },
    { body: { passkeys: [{ id: 3, name: 'Work laptop', created_at: '2026-10-30T10:00:00Z', last_used_at: null, backed_up: true, transports: ['internal'] }],
              has_password: true, limit: 10, added: { id: 3, name: 'Work laptop' } } },
  ] });
  const { form } = settingsForm(s);
  s.el('passkeyName').value = 'Work laptop';
  s.el('passkeyAddPassword').value = 'a good long password';
  s.context.window.OmniPasskeys.state = { passkeys: [], has_password: true, limit: 10 };
  const api = s.context.window.OmniPasskeys;
  const created = s.$('passkeyList');
  api.render();
  assert.equal(created.hidden, true);
  await form.listeners.submit[0]({ preventDefault() {}, target: form });
  await s.settle();
  assert.equal(s.requests.length, 2);
  assert.match(s.requests[0].url, /\/account\/passkeys\/options$/);
  assert.deepEqual(JSON.parse(s.requests[0].options.body), { password: 'a good long password' });
  const create = s.credentialCalls[0];
  assert.equal(create.kind, 'create');
  assert.equal(new TextDecoder().decode(create.options.publicKey.user.id), 'user');
  assert.equal(new TextDecoder().decode(create.options.publicKey.excludeCredentials[0].id), 'old');
  assert.match(s.requests[1].url, /\/account\/passkeys\/register$/);
  const sent = JSON.parse(s.requests[1].options.body);
  assert.equal(sent.name, 'Work laptop');
  assert.equal(sent.credential.response.attestationObject, 'YXR0ZXN0YXRpb24');
  assert.deepEqual(sent.credential.response.transports, ['internal', 'hybrid']);
  assert.equal(created.hidden, false);
  assert.equal(created.children.length, 1);
  assert.equal(s.$('passkeyBadge').textContent, '1 passkey');
  assert.match(s.$('passkeySuccess').textContent, /Work laptop is ready/);
  assert.equal(s.$('passkeyAddPassword').value, '');
  assert.equal(api.state.passkeys.length, 1);
});

test('a device that already holds a passkey for the account gets a plain explanation', async () => {
  const error = Object.assign(new Error('dup'), { name: 'InvalidStateError' });
  const s = setup({ settings: true, replies: [{ body: { rp: {}, user: { id: 'dXNlcg' }, challenge: 'Y2hhbGxlbmdl' } }], credentialError: error });
  const { form } = settingsForm(s);
  s.el('passkeyAddPassword').value = 'pw';
  s.context.window.OmniPasskeys.state = { passkeys: [], has_password: true, limit: 10 };
  await form.listeners.submit[0]({ preventDefault() {}, target: form });
  await s.settle();
  assert.equal(s.requests.length, 1);
  assert.match(s.$('passkeyError').textContent, /already has a passkey/);
});

test('the password is asked for before any request when the account has one', async () => {
  const s = setup({ settings: true });
  const { form } = settingsForm(s);
  s.context.window.OmniPasskeys.state = { passkeys: [], has_password: true, limit: 10 };
  await form.listeners.submit[0]({ preventDefault() {}, target: form });
  assert.equal(s.requests.length, 0);
  assert.match(s.$('passkeyError').textContent, /current password/);
});
