const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');
const auth = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
function part(text, start, end) {
  const a = text.indexOf(start), b = text.indexOf(end, a);
  assert.ok(a >= 0 && b > a, start); return text.slice(a, b);
}

test('custom tab lookups only fill fields the tab has and the member left empty', () => {
  const context = vm.createContext({});
  vm.runInContext(part(source, 'function applyMetadataField(', 'async function fetchMetadataForCustomTab('), context);
  const tab = {fields: [
    {key: 'year', field_type: 'number'}, {key: 'director', field_type: 'text'}, {key: 'release_date', field_type: 'date'},
  ]};
  const values = {director: 'Mine'};
  context.applyMetadataField(tab, values, 'year', 2014);
  context.applyMetadataField(tab, values, 'director', 'Christopher Nolan');
  context.applyMetadataField(tab, values, 'genres', 'Action');
  context.applyMetadataField(tab, values, 'release_date', 2014);
  assert.deepEqual(values, {director: 'Mine', year: 2014});
});

test('a rate-limited sign-in explains itself instead of saying the password is wrong', () => {
  const context = vm.createContext({});
  vm.runInContext(part(auth, 'function authErrorMessage(', '// Anonymous sign-up funnel counters'), context);
  assert.match(context.authErrorMessage({error: 'Rate limit exceeded: 5 per 1 minute'}, 'Invalid credentials'), /Too many attempts/);
  assert.equal(context.authErrorMessage({detail: 'Incorrect username or password'}, 'x'), 'Incorrect username or password');
});
