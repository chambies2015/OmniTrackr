// People you follow: sentence wording, same-site links only, and server text kept as text.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag) {
  return {
    tagName: tag, children: [], attributes: {}, className: '', textContent: '', hidden: false, style: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    addEventListener() {},
    setAttribute(name, value) { this.attributes[name] = String(value); },
  };
}

function load(nodes = {}) {
  const module = { exports: {} };
  const document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: element,
    createTextNode: text => ({ textContent: text }),
    addEventListener() {},
  };
  const context = vm.createContext({ module, window: { addEventListener() {} }, document, setTimeout: () => 0, Date });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/follows.js'), 'utf8'), context);
  return module.exports;
}

function text(node) {
  return (node.textContent || '') + (node.children || []).map(text).join('');
}

test('each update reads as a short sentence', () => {
  const { verb } = load();
  assert.equal(verb({ kind: 'review' }), 'reviewed');
  assert.equal(verb({ kind: 'collection' }), 'published a collection');
  assert.equal(verb({ kind: 'diary', repeat: true }), 'revisited');
  assert.equal(verb({ kind: 'diary' }), 'finished');
});

test('only same-site paths become links', () => {
  const { safePath, rating } = load();
  assert.equal(safePath('/u/critic'), '/u/critic');
  assert.equal(safePath('//evil.example/x'), null);
  assert.equal(safePath('javascript:alert(1)'), null);
  assert.equal(rating(8), '8/10');
  assert.equal(rating(7.5), '7.5/10');
  assert.equal(rating(null), '');
});

test('feed items are drawn from text, and spoilers stay folded', () => {
  const list = element('ol');
  const status = element('p');
  const { renderFeed } = load({ followingList: list, followingStatus: status });
  renderFeed({ following: 1, items: [
    { kind: 'review', username: '<b>critic</b>', profile_url: '/u/critic', title: '<img src=x onerror=alert(1)>',
      url: '/reviews/1?category=movie', label: 'Movie', rating: 9, date: '2026-10-29', excerpt: 'Loved it', spoilers: false },
    { kind: 'review', username: 'critic', profile_url: '//evil.example', title: 'Dune', url: '/reviews/2?category=book',
      label: 'Book', date: '2026-10-28', excerpt: 'The ending is...', spoilers: true },
  ] });
  assert.equal(list.children.length, 2);
  assert.ok(text(list.children[0]).includes('<b>critic</b> reviewed <img src=x onerror=alert(1)>'));
  const second = list.children[1];
  assert.ok(text(second).includes('Contains spoilers') && !text(second).includes('The ending'));
  // A link that leaves the site is drawn as plain text.
  const who = second.children[1].children[0].children[0];
  assert.equal(who.tagName, 'span');
  assert.equal(who.href, undefined);
});

test('an empty feed says why', () => {
  const list = element('ol');
  const status = element('p');
  const { renderFeed } = load({ followingList: list, followingStatus: status });
  renderFeed({ following: 0, items: [] });
  assert.match(status.textContent, /Follow members from their public profile/);
  renderFeed({ following: 2, items: [] });
  assert.match(status.textContent, /Nothing new/);
});
