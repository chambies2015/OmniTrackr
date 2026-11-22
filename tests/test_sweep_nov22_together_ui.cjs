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

test('signing in from a Watch together invite or plan comes back to it', () => {
  const context = authContext();
  // "Join free", "I have an account" and "Log in to see this plan" send guests to /?next=<page>.
  const allowed = ['/together', '/together/join/QSHVIhDknB3CgnbKZSiC8Q', '/together/12', '/together/2147483647',
    '/together/join/abcdefghijklmnop', '/together/join/' + 'a'.repeat(40)];
  for (const value of allowed) assert.equal(context.validateDiscoverAuthReturn(value), value, value);
  const rejected = ['/together/0', '/together/2147483648', '/together/', '/together/join/short',
    '/together/join/' + 'a'.repeat(41), '/together/join/QSHVIhDknB3CgnbKZSiC8Q/card.png', '/together/join/../admin',
    '//evil.example/together', 'https://evil.example/together/1', '/together\n', '/together/12#notes', '/togetherx'];
  for (const value of rejected) assert.equal(context.validateDiscoverAuthReturn(value), null, value);
});
