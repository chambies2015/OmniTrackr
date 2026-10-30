const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/dashboard/notices.js'), 'utf8');

function element(tag) {
  const node = {
    tagName: tag.toUpperCase(), children: [], attributes: {}, dataset: {}, listeners: {}, parentNode: null,
    className: '', textContent: '', id: '',
    get firstElementChild() { return this.children[0]; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
    append(...children) { children.forEach(child => this.appendChild(child)); },
    remove() {
      if (!this.parentNode) return;
      const siblings = this.parentNode.children;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentNode = null;
    },
    addEventListener(type, fn) { this.listeners[type] = fn; },
  };
  return node;
}

function setup(stored = null) {
  const body = element('body');
  const timers = [];
  const storage = new Map(stored ? [['omnitrackr_pending_notice', stored]] : []);
  const document = {
    body,
    createElement: element,
    getElementById: id => body.children.find(child => child.id === id) || null,
    querySelector: () => null,
  };
  const context = vm.createContext({
    document, Array, JSON, String,
    sessionStorage: {
      getItem: key => (storage.has(key) ? storage.get(key) : null),
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    setTimeout: fn => { timers.push(fn); return timers.length; },
    clearTimeout() {},
  });
  vm.runInContext(source, context);
  const stack = () => document.getElementById('appNotices');
  return { context, body, timers, storage, stack };
}

test('errors are announced as alerts and other tones as status', () => {
  const s = setup();
  s.context.showNotice('Could not save.');
  s.context.showNotice('Saved.', 'success');
  const [error, success] = s.stack().children;
  assert.equal(error.attributes.role, 'alert');
  assert.equal(error.className, 'app-notice app-notice--error');
  assert.equal(error.children[0].textContent, 'Could not save.');
  assert.equal(success.attributes.role, 'status');
  assert.equal(success.className, 'app-notice app-notice--success');
});

test('text is never parsed as markup and empty messages are skipped', () => {
  const s = setup();
  s.context.showNotice('');
  s.context.showNotice(null);
  assert.equal(s.stack(), null);
  s.context.showNotice('<img src=x onerror=alert(1)>');
  assert.equal(s.stack().children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
});

test('a repeated message replaces the old one and the stack holds three', () => {
  const s = setup();
  for (const text of ['one', 'two', 'one', 'three', 'four']) s.context.showNotice(text);
  assert.deepEqual(s.stack().children.map(node => node.dataset.text), ['one', 'three', 'four']);
});

test('short notices close on their own, long summaries wait for the close button', () => {
  const s = setup();
  s.context.showNotice('Short one.');
  assert.equal(s.timers.length, 1);
  s.timers[0]();
  assert.equal(s.stack().children.length, 0);
  s.context.showNotice('Import finished.\nMovies: 3 created', 'success');
  assert.equal(s.timers.length, 1);
  const notice = s.stack().children[0];
  notice.children[1].listeners.click();
  assert.equal(s.stack().children.length, 0);
});

test('a notice saved before a reload shows on the next load, once', () => {
  const first = setup();
  first.context.showNoticeAfterReload('Username changed.');
  const saved = first.storage.get('omnitrackr_pending_notice');
  assert.equal(first.stack(), null);
  const next = setup(saved);
  assert.equal(next.stack().children[0].dataset.text, 'Username changed.');
  assert.equal(next.storage.has('omnitrackr_pending_notice'), false);
});

test('API errors read as sentences instead of [object Object]', () => {
  const { apiErrorText } = setup().context;
  assert.equal(apiErrorText({ detail: 'Already in your library' }, 'x'), 'Already in your library');
  assert.equal(apiErrorText({ detail: [{ loc: ['body', 'year'], msg: 'Input should be less than or equal to 2100' }] }, 'x'),
    'Year can be at most 2100.');
  assert.equal(apiErrorText({ detail: [{ loc: ['body', 'title'], msg: 'String should have at most 500 characters' }] }, 'x'),
    'Title can be up to 500 characters.');
  assert.equal(apiErrorText({ detail: [{ loc: ['body', 'rating'], msg: 'Input should be a valid number, unable to parse string as a number' }] }, 'x'),
    'Rating must be a number.');
  assert.equal(apiErrorText({ detail: [{ loc: ['body', 'title'], msg: 'Field required' }] }, 'x'), 'Title is required.');
  assert.equal(apiErrorText({ detail: [{ loc: ['body', 'total_pages'], msg: 'Value error, too big' }] }, 'x'),
    'total pages: too big');
  assert.equal(apiErrorText({ detail: [{ loc: ['body'], msg: 'Field required' }] }, 'x'), 'Field required');
  assert.equal(apiErrorText({}, 'Could not add that movie.'), 'Could not add that movie.');
  assert.equal(apiErrorText(null, 'fallback'), 'fallback');
});
