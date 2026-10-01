const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/app.js'), 'utf8');

function setup(fetch) {
  const elements = new Map();
  const make = () => ({ value: '', dataset: {}, checked: false, textContent: '',
    focus() { this.focused = true; }, setAttribute() {} });
  const get = id => { if (!elements.has(id)) elements.set(id, make()); return elements.get(id); };
  const submit = { disabled: false };
  const form = get('addBookForm');
  form.querySelector = () => submit;
  form.appendChild = el => elements.set(el.id, el);
  form.reset = () => { form.resets = (form.resets || 0) + 1; };
  get('bookTitle').value = 'Sample book';
  get('bookAuthor').value = 'Sample author';
  get('bookYear').value = '2024';
  let loads = 0;
  const context = vm.createContext({ document: { getElementById: get, createElement: make },
    API_BASE: '', authenticatedFetch: fetch, toggleCollapsible() {}, loadBooks() { loads++; } });
  const start = source.indexOf("document.getElementById('addBookForm').onsubmit =");
  vm.runInContext(source.slice(start, source.indexOf('// Export/Import functions', start)), context);
  return { get, submit, form, loads: () => loads, save: () => form.onsubmit({ preventDefault() {} }) };
}

test('missing year gives inline feedback without submitting or clearing input', async () => {
  const s = setup(() => { throw new Error('must not fetch'); });
  s.get('bookYear').value = '';
  await s.save();
  assert.match(s.get('bookSaveStatus').textContent, /enter a year/);
  assert.equal(s.get('bookYear').focused, true);
  assert.equal(s.form.resets, undefined);
});

test('repeated clicks during save submit once, then refresh after success', async () => {
  let resolve, calls = 0;
  const s = setup(() => { calls++; return new Promise(r => { resolve = r; }); });
  const pending = s.save();
  assert.equal(s.submit.disabled, true);
  await s.save();
  assert.equal(calls, 1);
  resolve({ ok: true });
  await pending;
  assert.equal(s.form.resets, 1);
  assert.equal(s.loads(), 1);
  assert.equal(s.submit.disabled, false);
});

for (const message of ['Network failed', 'Session expired. Please login again.']) {
  test(`failed save preserves form and unlocks submit: ${message}`, async () => {
    const s = setup(async () => { throw new Error(message); });
    await s.save();
    assert.equal(s.form.resets, undefined);
    assert.equal(s.get('bookTitle').value, 'Sample book');
    assert.match(s.get('bookSaveStatus').textContent, /not been cleared/);
    assert.equal(s.submit.disabled, false);
  });
}

test('server validation errors preserve input and provide readable feedback', async () => {
  const s = setup(async () => ({ ok: false, json: async () => ({ detail: [{ msg: 'invalid' }] }) }));
  await s.save();
  assert.match(s.get('bookSaveStatus').textContent, /Check the fields/);
  assert.equal(s.form.resets, undefined);
});
