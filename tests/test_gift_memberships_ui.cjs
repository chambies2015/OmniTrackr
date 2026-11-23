const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const authScript = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function authContext() {
  const context = vm.createContext({
    URLSearchParams, location: {pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz'},
    window: {location: {pathname: '/', search: ''}, history: {replaceState() {}}},
    document: {readyState: 'loading', documentElement: {dataset: {}}, addEventListener() {}, getElementById: () => ({style: {}, dataset: {}})},
    sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
    localStorage: {getItem: () => null, setItem() {}, removeItem() {}},
  });
  vm.runInContext(authScript, context);
  return context;
}

test('signing up from a gift comes back to open it', () => {
  const context = authContext();
  for (const value of ['/gift/ABCD-EFGH-JKMN', '/gift/2345-6789-WXYZ', '/supporters/gift']) {
    assert.equal(context.validateDiscoverAuthReturn(value), value, value);
  }
  const rejected = ['/gift', '/gift/', '/gift/abcd-efgh-jkmn', '/gift/ABCDEFGHJKMN', '/gift/ABCD-EFGH-JKMN/open',
    '/gift/ABCD-EFGH-JKMN\n', '//evil.example/gift/ABCD-EFGH-JKMN', '/supporters/gift/manage/1-abc', '/supporters/giftx'];
  for (const value of rejected) assert.equal(context.validateDiscoverAuthReturn(value), null, value);
});

test('the resend form says the server reply, or why it could not', () => {
  const {resendMessage} = require('../app/static/gift-membership.js');
  assert.match(resendMessage(429, {}), /Wait an hour/);
  assert.equal(resendMessage(200, {message: 'Sent.'}), 'Sent.');
  assert.equal(resendMessage(422, {detail: 'Type a whole email address'}), 'Type a whole email address');
  assert.match(resendMessage(500, null), /Could not send/);
});

test('Account → Supporter says when the perks are a gift', () => {
  const sandbox = {window: {}, document: {getElementById: () => null, addEventListener() {}}, module: {exports: {}}};
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/supporter.js'), 'utf8'), sandbox);
  const {statusText} = sandbox.module.exports;
  const base = {active: true, since: '2026-12-20T12:00:00', active_until: '2027-04-07T09:00:00', number: 4, months: 0, member: false};
  const text = statusText({...base, founding: true, gift: {count: 1, from_name: 'Alex'}});
  assert.match(text, /^Your supporter perks are a gift from Alex, on until/);
  assert.match(text, /supporter #4/);
  assert.match(text, /founding supporter for good/);
  // Someone who also paid on Ko-fi themselves reads the usual thank-you.
  assert.match(statusText({...base, months: 2, gift: {count: 1, from_name: 'Alex'}}), /^Thank you for supporting/);
  assert.match(statusText({...base, gift: null}), /^Thank you for supporting/);
});
