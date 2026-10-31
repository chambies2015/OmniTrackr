// Pick for me (/pick): random picks skip recent ones, and cards are built with text only.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function fakeNode(tag) {
  return {
    tagName: tag, className: '', textContent: '', dataset: {}, attributes: {}, children: [], hidden: false,
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name]; },
    appendChild(child) { this.children.push(child); return child; },
  };
}

function load() {
  global.document = { createElement: fakeNode, createTextNode: text => ({ textContent: text, children: [] }),
    getElementById: () => null, querySelectorAll: () => [], readyState: 'complete', addEventListener() {} };
  global.window = {};
  delete require.cache[require.resolve('../app/static/pick-for-me.js')];
  return require(path.join(__dirname, '../app/static/pick-for-me.js'));
}

function flatten(node) {
  return [node, ...(node.children || []).flatMap(flatten)];
}

const POOL = [
  { id: 'movie/arrival-2016', kind: 'movie', slug: 'arrival-2016' },
  { id: 'movie/after-yang-2022', kind: 'movie', slug: 'after-yang-2022' },
  { id: 'book/piranesi-2020', kind: 'book', slug: 'piranesi-2020' },
];

test('choose keeps to the format and skips recent picks while others are left', () => {
  const api = load();
  assert.equal(api.choose(POOL, 'book', [], () => 0.9).id, 'book/piranesi-2020');
  assert.equal(api.choose(POOL, 'movie', ['movie/arrival-2016'], () => 0).id, 'movie/after-yang-2022');
  assert.equal(api.choose(POOL, 'book', ['book/piranesi-2020'], () => 0).id, 'book/piranesi-2020');
  assert.equal(api.choose(POOL, 'album', [], () => 0), null);
  assert.ok(['movie', 'book'].includes(api.choose(POOL, '', [], Math.random).kind));
});

test('a guest card is a guest-list button with plain text and safe links', () => {
  const api = load();
  const nodes = api.buildCard({ id: 'movie/x', kind: 'movie', slug: 'x', label: 'Movie', year: 2016, creator: 'D. V.',
    title: '<img src=x onerror=alert(1)>', why: 'Because.', caveat: null, source: 'Trail',
    sourceUrl: 'javascript:alert(1)', url: '//evil.example/x', image: 'javascript:alert(1)' }, false).flatMap(flatten);
  const save = nodes.find(node => node.dataset.guestKind);
  assert.equal(save.dataset.guestSlug, 'x');
  assert.equal(save.attributes['aria-pressed'], 'false');
  assert.ok(nodes.some(node => node.textContent === '<img src=x onerror=alert(1)>'));
  assert.ok(nodes.some(node => node.textContent === 'Movie · 2016 · D. V.'));
  assert.ok(!nodes.some(node => node.tagName === 'img'), 'non-http images are not loaded');
  assert.ok(!nodes.some(node => node.tagName === 'a'), 'unsafe links are dropped');
  assert.ok(!nodes.some(node => node.className === 'caveat pf-card__caveat'));
});

test('a member card adds to the library and links the title page', () => {
  const api = load();
  const nodes = api.buildCard({ id: 'book/piranesi-2020', kind: 'book', slug: 'piranesi-2020', label: 'Book', year: 2020,
    creator: null, title: 'Piranesi', why: 'Why.', caveat: 'Careful.', source: 'Trail', sourceUrl: '/discover/x',
    url: '/titles/book/piranesi-2020', image: 'https://img.example/p.jpg' }, true).flatMap(flatten);
  assert.ok(nodes.some(node => node.dataset.pickAdd === 'book/piranesi-2020'));
  assert.ok(!nodes.some(node => node.dataset.guestKind));
  assert.ok(nodes.some(node => node.tagName === 'a' && node.href === '/titles/book/piranesi-2020'));
  assert.ok(nodes.some(node => node.tagName === 'a' && node.href === '/discover/x'));
  const image = nodes.find(node => node.tagName === 'img');
  assert.equal(image.src, 'https://img.example/p.jpg');
  assert.equal(image.referrerPolicy, 'no-referrer');
});
