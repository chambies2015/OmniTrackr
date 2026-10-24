// Homepage hero search results: drawn as guest-list tiles with text only.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function fakeNode(tag) {
  return {
    tagName: tag, className: '', textContent: '', dataset: {}, attributes: {}, children: [], hidden: false,
    setAttribute(name, value) { this.attributes[name] = String(value); },
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { nodes.forEach(node => this.children.push(node)); },
    replaceChildren(...nodes) { this.children = nodes; },
  };
}

function load() {
  let refreshed = 0;
  global.document = { createElement: fakeNode, querySelectorAll: () => [], readyState: 'complete', addEventListener() {} };
  global.window = { OmniGuestList: { refreshTiles: () => { refreshed += 1; } } };
  delete require.cache[require.resolve('../app/static/title-search.js')];
  const api = require(path.join(__dirname, '../app/static/title-search.js'));
  return { api, refreshes: () => refreshed };
}

function flatten(node) {
  return [node, ...node.children.flatMap(flatten)];
}

test('a result is a guest-list tile with safe text', () => {
  const { api } = load();
  const button = api.resultButton({ kind: 'movie', label: 'Movie', title: '<img src=x onerror=alert(1)>', year: 2014,
    slug: 'interstellar-2014', image: 'javascript:alert(1)' });
  assert.equal(button.dataset.guestKind, 'movie');
  assert.equal(button.dataset.guestSlug, 'interstellar-2014');
  assert.equal(button.attributes['aria-pressed'], 'false');
  const nodes = flatten(button);
  assert.ok(!nodes.some(node => node.tagName === 'img'), 'non-http images are not loaded');
  assert.ok(nodes.some(node => node.textContent === '<img src=x onerror=alert(1)>'), 'titles are plain text');
  assert.ok(nodes.some(node => node.textContent === 'Movie · 2014'));
});

test('poster images load without a referrer', () => {
  const { api } = load();
  const button = api.resultButton({ kind: 'book', label: 'Book', title: 'Piranesi', year: null, slug: 'piranesi',
    image: 'https://img.example/p.jpg' });
  const image = flatten(button).find(node => node.tagName === 'img');
  assert.equal(image.src, 'https://img.example/p.jpg');
  assert.equal(image.referrerPolicy, 'no-referrer');
  assert.ok(flatten(button).some(node => node.textContent === 'Book'));
});

test('results refresh the list state; no match offers sign-up', () => {
  const { api, refreshes } = load();
  const container = fakeNode('div');
  container.hidden = true;
  api.render(container, [{ kind: 'game', label: 'Video game', title: 'Hades', year: 2020, slug: 'hades-2020' }], 'had');
  assert.equal(container.hidden, false);
  assert.equal(flatten(container).filter(node => node.className === 'lp-search__result').length, 1);
  assert.equal(refreshes(), 1);
  api.render(container, [], 'zzz');
  const cta = flatten(container).find(node => node.dataset.action === 'show-register-form');
  assert.ok(cta, 'empty results point to sign-up');
});
