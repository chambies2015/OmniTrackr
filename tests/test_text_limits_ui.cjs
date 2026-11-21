// Review length limit (text_limits.REVIEW_MAX) in the dashboard counter and the title page composer.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

const limits = fs.readFileSync(path.join(__dirname, '../app/text_limits.py'), 'utf8');
const SERVER_MAX = Number(limits.match(/^REVIEW_MAX = (\d+)$/m)[1]);

function dashboard() {
  const context = vm.createContext({ document: { querySelector: () => null }, setTimeout });
  vm.runInContext(source.slice(source.indexOf('const REVIEW_PREVIEW_LEN'), source.indexOf('function setupReviewQualityCounters(')), context);
  return context;
}

function counterFor(context, value) {
  const listeners = {};
  const classes = new Set();
  const counter = { textContent: '', classList: { toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)) } };
  const textarea = { id: 'edit-movie-review', value, dataset: {}, addEventListener: (type, fn) => { listeners[type] = fn; } };
  context.document.querySelector = selector => (selector === '[data-review-counter-for="edit-movie-review"]' ? counter : null);
  context.setupReviewQualityCounter(textarea);
  return { counter, classes, type: next => { textarea.value = next; listeners.input(); } };
}

test('the dashboard limit matches the server', () => {
  assert.equal(vm.runInContext('REVIEW_MAX_CHARS', dashboard()), SERVER_MAX);
});

test('the counter stays on review quality until a review nears the limit', () => {
  const context = dashboard();
  assert.match(context.getReviewQualityMessage('Short.'), /^6\/80 characters/);
  assert.equal(context.getReviewLengthMessage('x'.repeat(SERVER_MAX * 0.9 - 1)), '');
  assert.equal(context.getReviewQualityMessage('x'.repeat(18500)), '18,500 of 20,000 characters');
  assert.equal(context.getReviewQualityMessage('x'.repeat(SERVER_MAX + 1)),
    '20,001 of 20,000 characters - shorten the review to save it');
});

test('a new review past the limit is marked, and clears once it is short enough', () => {
  const box = counterFor(dashboard(), '');
  box.type('x'.repeat(SERVER_MAX + 5));
  assert.ok(box.classes.has('is-over'));
  assert.ok(!box.classes.has('is-ready'));
  box.type('A good review. '.repeat(100));
  assert.ok(!box.classes.has('is-over'));
  assert.ok(box.classes.has('is-ready'));
});

test('a review saved before the limit can be edited and shortened but not lengthened', () => {
  const saved = 'y'.repeat(30000);
  const box = counterFor(dashboard(), saved);
  assert.ok(!box.classes.has('is-over'));
  assert.match(box.counter.textContent, /saved before the limit, so you can edit or shorten it but not add to it$/);
  box.type(saved.slice(0, -100));
  assert.ok(!box.classes.has('is-over'));
  box.type(`${saved}!`);
  assert.ok(box.classes.has('is-over'));
  assert.match(box.counter.textContent, /shorten the review to save it$/);
});

test('the title page composer counts against its maxlength once a review is long', async () => {
  const page = fs.readFileSync(path.join(__dirname, '../app/static/title-page.js'), 'utf8');
  const meter = { textContent: '' };
  const field = (value, extra = {}) => ({ value, checked: false, addEventListener() {}, ...extra });
  const form = {
    dataset: { titleKind: 'movie', titleSlug: 'arrival-2016' },
    elements: { review: field('', { maxLength: SERVER_MAX, dataset: {}, removeAttribute(name) { if (name === 'maxlength') this.maxLength = -1; } }),
      rating: field(''), public: field(''), spoilers: field('') },
    addEventListener() {},
    querySelector: s => (s === '[type="submit"]' ? { disabled: false } : s === '.title-write__status' ? { replaceChildren() {}, append() {} } : meter),
  };
  const document = { querySelector: s => (s === '[data-title-review]' ? form : null), addEventListener() {}, createTextNode: t => t };
  const review = 'Long thoughts here. '.repeat(1250); // 25,000 characters
  vm.runInContext(page, vm.createContext({
    document, window: { location: { search: '', pathname: '/titles/movie/arrival-2016' } }, URLSearchParams,
    localStorage: { getItem: () => null },
    fetch: async () => ({ ok: true, status: 200, json: async () => ({ in_library: true, review, rating: null, public: true }) }),
  }));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(meter.textContent,
    '24,999 of 20,000 characters. This review was saved before the limit: you can edit or shorten it, but not add to it');
  // Loaded without the maxlength, so typing into it still works; the limit is kept for the hint.
  assert.equal(form.elements.review.maxLength, -1);
  assert.equal(form.elements.review.dataset.limit, String(SERVER_MAX));
});
