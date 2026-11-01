// Title page script: what a signed-in member sees once their own library entry loads.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/title-page.js'), 'utf8');

function setup(myReview) {
  const field = value => ({ value, checked: false, addEventListener() {} });
  const submit = { disabled: false, textContent: 'Save review' };
  const status = { replaceChildren() {}, append() {} };
  const meter = { textContent: '' };
  const form = {
    dataset: { titleKind: 'movie', titleSlug: 'the-matrix-1999' },
    elements: { review: field(''), rating: field(''), public: field(''), spoilers: field('') },
    addEventListener() {},
    querySelector: s => (s === '[type="submit"]' ? submit : s === '.title-write__status' ? status : meter),
  };
  const add = { textContent: 'Add to my library', disabled: false };
  const document = {
    querySelector: s => (s === '[data-title-review]' ? form : s === '[data-title-add]' ? add : null),
    addEventListener() {},
    createTextNode: text => text,
  };
  const context = vm.createContext({
    document, window: { location: { search: '', pathname: '/titles/movie/the-matrix-1999' } }, URLSearchParams,
    localStorage: { getItem: () => null },
    fetch: async () => ({ ok: true, status: 200, json: async () => myReview }),
  });
  vm.runInContext(source, context);
  return { add, form, submit };
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('a title already in the library shows as added instead of offering "Add to my library"', async () => {
  const page = setup({ in_library: true, review: 'Still great.', rating: 9, public: true, spoilers: false });
  await settle();
  assert.equal(page.add.textContent, '✓ In your library');
  assert.equal(page.add.disabled, true);
  assert.equal(page.submit.textContent, 'Update review');
});

test('a title not in the library keeps its add button', async () => {
  const page = setup({ in_library: false, review: '', rating: null, public: true, spoilers: false });
  await settle();
  assert.equal(page.add.textContent, 'Add to my library');
  assert.equal(page.add.disabled, false);
});
