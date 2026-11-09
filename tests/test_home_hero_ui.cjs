// Dashboard welcome strip, library tab counts and heading stat lines (home-hero.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = '';
    this.dataset = {}; this.attributes = {}; this.style = { setProperty: (k, v) => { this.style[k] = v; } };
    this.classList = { toggle: (name, on) => { this.toggled = { name, on }; }, add() {} };
  }
  appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  prepend(child) { this.children.unshift(child); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector() { return null; }
  insertAdjacentElement(_, node) { this.after = node; }
  remove() { this.removed = true; }
  get text() { return [this.textContent, ...this.children.map(child => child.text)].join(' '); }
}

function setup() {
  const ids = ['homeHero', 'homeHeroDate', 'homeHeroTitle', 'homeHeroSummary', 'homeHeroStats', 'homeHeroMix', 'homeHeroCovers'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  nodes.homeHero.hidden = true;
  const tab = new Node('button');
  const heading = new Node('div');
  heading.parentElement = { querySelector: () => null };
  global.document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: tag => new Node(tag),
    querySelectorAll: selector => (selector.includes('data-switch-tab="movies"') ? [tab] : []),
    querySelector: selector => (selector.startsWith('#movies-tab') ? heading : null),
    addEventListener() {},
  };
  global.window = { addEventListener() {}, setTimeout, clearTimeout };
  delete require.cache[require.resolve('../app/static/home-hero.js')];
  const module = require(path.join(__dirname, '../app/static/home-hero.js'));
  return { nodes, module, tab, heading };
}

const LIBRARIES = [
  { key: 'movies', one: 'movie', many: 'movies', verb: 'watched', total: 8, finished: 6, rated: 6, average_rating: 8.8, visible: true },
  { key: 'books', one: 'book', many: 'books', verb: 'read', total: 1, finished: 0, rated: 0, average_rating: null, visible: true },
  { key: 'anime', one: 'anime', many: 'anime', verb: 'watched', total: 3, finished: 1, rated: 0, average_rating: null, visible: false },
  { key: 'music', one: 'album', many: 'albums', verb: 'listened', total: 0, finished: 0, rated: 0, average_rating: null, visible: true },
];

test('greeting follows the time of day', () => {
  const { module } = setup();
  assert.equal(module.greeting(new Date(2026, 10, 9, 8), 'maya'), 'Good morning, maya');
  assert.equal(module.greeting(new Date(2026, 10, 9, 14), 'maya'), 'Good afternoon, maya');
  assert.equal(module.greeting(new Date(2026, 10, 9, 21), 'maya'), 'Good evening, maya');
  assert.equal(module.greeting(new Date(2026, 10, 9, 2), 'maya'), 'Still up, maya?');
});

test('summary names the month and what is still waiting', () => {
  const { module } = setup();
  const now = new Date(2026, 10, 9, 12);
  assert.equal(module.summaryText({ finished_this_month: 3, unfinished: 11 }, now), '3 titles finished in November so far. 11 still waiting for you.');
  assert.equal(module.summaryText({ finished_this_month: 1, unfinished: 0 }, now),
    "1 title finished in November so far. Everything you've saved is done. Time to add something new.");
  assert.equal(module.summaryText({ finished_this_month: 0, unfinished: 2 }, now), 'Nothing finished in November yet. 2 still waiting for you.');
});

test('heading stat line uses the format words', () => {
  const { module } = setup();
  assert.equal(module.headingLine(LIBRARIES[0]), '8 movies · 6 watched · 6 rated · average 8.8');
  assert.equal(module.headingLine(LIBRARIES[1]), '1 book · 0 read');
  assert.equal(module.headingLine(LIBRARIES[3]), '');
});

test('render fills the strip, tab counts, stat line and covers as text only', () => {
  const { module, nodes, tab, heading } = setup();
  module.render({
    name: '<b>maya</b>', total: 9, finished: 6, unfinished: 3, rated: 6, finished_this_month: 2, libraries: LIBRARIES,
    recent: [{ id: 4, category: 'movies', title: '<img src=x>', image: 'https://example.com/a.jpg' }],
  }, new Date(2026, 10, 9, 19));
  assert.equal(nodes.homeHero.hidden, false);
  assert.equal(nodes.homeHeroTitle.textContent, 'Good evening, <b>maya</b>');
  assert.equal(nodes.homeHeroDate.textContent, 'Monday, November 9');
  assert.equal(nodes.homeHeroStats.children.length, 4);
  assert.equal(tab.dataset.count, '8');
  assert.equal(heading.after.textContent, '8 movies · 6 watched · 6 rated · average 8.8');
  // Hidden and empty formats stay out of the mix bar.
  assert.deepEqual(nodes.homeHeroMix.children.map(part => part.dataset.format), ['movies', 'books']);
  assert.match(nodes.homeHeroMix.attributes['aria-label'], /8 movies, 1 book$/);
  const cover = nodes.homeHeroCovers.children[0];
  assert.equal(cover.dataset.action, 'pulse-open-item');
  assert.equal(cover.dataset.pulseItemId, '4');
  assert.equal(cover.attributes['aria-label'], 'Open <img src=x>');
  assert.equal(cover.children[0].src, 'https://example.com/a.jpg');
  assert.equal(nodes.homeHeroCovers.hidden, false);
});

test('an empty library hides the strip', () => {
  const { module, nodes } = setup();
  module.render({ name: 'maya', total: 0, finished: 0, unfinished: 0, rated: 0, finished_this_month: 0, libraries: [], recent: [] });
  assert.equal(nodes.homeHero.hidden, true);
});
