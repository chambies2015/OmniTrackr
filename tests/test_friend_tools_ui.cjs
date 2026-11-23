// The one idea under the friends list in What's new (home-today.js, app/friend_tools.py, Nov 23 2026).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = '';
    this.dataset = {}; this.attributes = {}; this.listeners = {};
  }
  appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
  append(...children) { children.forEach(child => this.appendChild(typeof child === 'string' ? Object.assign(new Node('#text'), { textContent: child }) : child)); }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  remove() { this.removed = true; }
  get text() { return [this.textContent, ...this.children.map(child => child.text)].join(' ').replace(/\s+/g, ' ').trim(); }
}

function setup(storage = {}) {
  const ids = ['homeNews', 'homeNewsEyebrow', 'homeNewsSummary', 'homeNewsShows', 'homeNewsShowList', 'homeNewsFriends',
    'homeNewsFriendList', 'homeNewsFriendsMore', 'homeNewsStatus', 'homeHeroNews'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  ['homeNews', 'homeNewsShows', 'homeNewsFriends', 'homeHeroNews'].forEach(id => { nodes[id].hidden = true; });
  global.document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: tag => new Node(tag),
    createTextNode: text => Object.assign(new Node('#text'), { textContent: text }),
    addEventListener() {},
  };
  global.localStorage = {
    getItem: key => (key in storage ? storage[key] : null),
    setItem: (key, value) => { storage[key] = String(value); },
  };
  global.window = { addEventListener() {}, setTimeout, clearTimeout, matchMedia: () => ({ matches: false }) };
  delete require.cache[require.resolve('../app/static/home-today.js')];
  const module = require(path.join(__dirname, '../app/static/home-today.js'));
  return { nodes, module, storage };
}

const NOW = new Date(2026, 10, 23, 18, 0);
const SWAP = { key: 'swap-2026', tool: 'swap', title: 'Holiday pick swap', text: 'Draw names.', path: '/swap#start', label: 'Start a swap' };
const FRIENDS = { items: [], new: 0, friends: 2 };

function capture(nodes) {
  const added = [];
  nodes.homeNewsFriends.append = (...children) => { added.push(...children); };
  return added;
}

const ideaOf = added => added.find(node => node.className === 'home-news__idea');

function find(node, className) {
  if (node.className === className) return node;
  for (const child of node.children) {
    const hit = find(child, className);
    if (hit) return hit;
  }
  return null;
}

test('a member with friends sees the idea with a safe link', () => {
  const { nodes, module } = setup();
  const added = capture(nodes);
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: SWAP }, NOW);
  const idea = ideaOf(added);
  assert.ok(idea);
  assert.equal(idea.dataset.tool, 'swap');
  assert.match(idea.text, /Holiday pick swap/);
  assert.equal(find(idea, 'home-news__btn home-news__btn--primary').href, '/swap#start');
  assert.equal(nodes.homeNews.hidden, false);
});

test('someone with no friends yet gets the taste test instead', () => {
  const { nodes, module } = setup();
  const added = capture(nodes);
  module.render({ shows: [], releases: [], friends: { items: [], new: 0, friends: 0 }, counts: {}, idea: SWAP }, NOW);
  assert.equal(ideaOf(added), undefined);
  assert.ok(added.some(node => node.className === 'home-news__invite'));
});

test('Not now hides that idea on this device, and only that one', () => {
  const { nodes, module, storage } = setup();
  const added = capture(nodes);
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: SWAP }, NOW);
  const idea = ideaOf(added);
  find(idea, 'home-news__link').listeners.click();
  assert.equal(idea.removed, true);
  assert.deepEqual(JSON.parse(storage.omnitrackr_home_idea_hidden), ['swap-2026']);

  added.length = 0;
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: SWAP }, NOW);
  assert.equal(ideaOf(added), undefined);
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: { ...SWAP, key: 'swap-2027' } }, NOW);
  assert.ok(ideaOf(added));
});

test('only the two pages are linked; anything else is dropped', () => {
  const { nodes, module } = setup();
  const added = capture(nodes);
  assert.equal(module.ideaPath('/swap#start'), '/swap#start');
  assert.equal(module.ideaPath('/together'), '/together');
  assert.equal(module.ideaPath('https://evil.example/swap'), null);
  assert.equal(module.ideaPath('/swap/../admin'), null);
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: { ...SWAP, path: 'javascript:alert(1)' } }, NOW);
  assert.equal(ideaOf(added), undefined);
});

test('a broken hidden list in storage does not stop the card', () => {
  const { nodes, module } = setup({ omnitrackr_home_idea_hidden: '{not json' });
  const added = capture(nodes);
  module.render({ shows: [], releases: [], friends: FRIENDS, counts: {}, idea: SWAP }, NOW);
  assert.ok(ideaOf(added));
});
