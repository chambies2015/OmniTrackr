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

test('signing in from a shared list comes back to that list', () => {
  const context = authContext();
  // The pages' "+ Add to my library" links send guests to /?next=<the list>#landing-auth.
  const allowed = ['/collections/public/12', '/collections/public/2147483647',
    '/collections/link/htKO1i2GJhHMtg9d1jgHtw', '/collections/public/7/save'];
  for (const value of allowed) assert.equal(context.validateDiscoverAuthReturn(value), value);
  const rejected = ['/collections/public/0', '/collections/public/2147483648', '/collections/public/12/',
    '/collections/link/short', '/collections/link/htKO1i2GJhHMtg9d1jgHtw/card.png', '/collections/link/../admin',
    '//evil.example/collections/public/12', 'https://evil.example/collections/public/12',
    '/collections/public/12\n', '/collections/explore'];
  for (const value of rejected) assert.equal(context.validateDiscoverAuthReturn(value), null, value);
});
