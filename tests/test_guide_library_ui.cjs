// The /guides library filter (guide-library.js): format chips, the name search and the counts.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(attrs = {}) {
    this.attrs = { ...attrs }; this.hidden = false; this.textContent = ''; this.listeners = {}; this.value = '';
    this.children = []; this.parentNode = null; this.scrollWidth = 0; this.clientWidth = 0; this.offsetLeft = 0;
  }
  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  click() { this.listeners.click({ preventDefault() {} }); }
  scrollIntoView() { this.scrolled = true; }
}

function setup() {
  const rows = [
    new Node({ 'data-formats': 'movie tv', 'data-name': 'star wars in order' }),
    new Node({ 'data-formats': 'anime manga', 'data-name': 'dragon ball in order' }),
    new Node({ 'data-formats': 'anime', 'data-name': 'how long does it take to watch one piece?' }),
    new Node({ 'data-formats': 'book audiobook', 'data-name': 'discworld in order' }),
  ];
  const badges = [new Node(), new Node()];
  const shelves = [
    { node: new Node(), rows: [rows[0], rows[1], rows[3]], badge: badges[0] },
    { node: new Node(), rows: [rows[2]], badge: badges[1] },
  ];
  shelves.forEach(shelf => {
    shelf.node.querySelectorAll = () => shelf.rows.filter(row => !row.hidden);
    shelf.node.querySelector = () => shelf.badge;
  });
  const chipRow = new Node();
  const chip = (format, slug, plural) => {
    const node = new Node({ 'data-format': format, 'data-slug': slug, 'data-plural': plural });
    node.parentNode = chipRow;
    return node;
  };
  const chips = [chip('', '', ''), chip('movie', 'films', 'films'), chip('anime', 'anime', 'anime')];
  chips[0].setAttribute('aria-current', 'true');
  const count = new Node(); const find = new Node(); const input = new Node(); const empty = new Node();
  find.hidden = true; empty.hidden = true;
  const tools = new Node();
  tools.querySelectorAll = () => chips;
  tools.querySelector = selector => ({ '[data-gl-count]': count, '[data-gl-find]': find, '[data-gl-search]': input })[selector];
  const desk = new Node({ 'data-format': 'anime' });
  const heading = new Node();
  const urls = [];
  global.document = {
    readyState: 'complete',
    querySelector: selector => ({ '[data-gl-tools]': tools, '[data-gl-empty]': empty })[selector] || null,
    querySelectorAll: selector => ({ '.gl-row': rows, '[data-gl-shelf]': shelves.map(s => s.node), '.gl-desk__all[data-format]': [desk] })[selector] || [],
    getElementById: () => heading,
    addEventListener() {},
  };
  global.history = { replaceState: (_, __, url) => urls.push(url) };
  global.location = { pathname: '/guides' };
  const file = path.join(__dirname, '..', 'app', 'static', 'guide-library.js');
  delete require.cache[require.resolve(file)];
  require(file);
  return { rows, shelves, chips, count, find, input, empty, desk, heading, urls };
}

test('the search box appears once the script runs', () => {
  const page = setup();
  assert.equal(page.find.hidden, false);
});

test('a format chip hides the other guides and empty shelves without a reload', () => {
  const page = setup();
  page.chips[2].click();
  assert.deepEqual(page.rows.map(row => row.hidden), [true, false, false, true]);
  assert.equal(page.shelves[0].badge.textContent, '1');
  assert.equal(page.shelves[0].node.hidden, false);
  assert.equal(page.chips[2].getAttribute('aria-current'), 'true');
  assert.equal(page.chips[0].getAttribute('aria-current'), null);
  assert.equal(page.count.textContent, 'Showing 2 of 4 guides that cover anime.');
  assert.equal(page.urls.at(-1), '/guides?format=anime#guide-library-heading');
  page.chips[0].click();
  assert.ok(page.rows.every(row => !row.hidden));
  assert.equal(page.count.textContent, 'Showing all 4 guides.');
  assert.equal(page.urls.at(-1), '/guides#guide-library-heading');
});

test('the name search combines with the format and says when nothing matches', () => {
  const page = setup();
  page.input.value = 'In Order';
  page.input.listeners.input();
  assert.deepEqual(page.rows.map(row => row.hidden), [false, false, true, false]);
  assert.equal(page.shelves[1].node.hidden, true);
  assert.equal(page.count.textContent, '3 guides match.');
  page.chips[1].click();
  assert.equal(page.count.textContent, 'One guide covering films matches.');
  page.input.value = 'nothing like this';
  page.input.listeners.input();
  assert.equal(page.empty.hidden, false);
  assert.equal(page.count.textContent, '0 guides covering films match.');
});

test('a format desk link filters the list and scrolls to it', () => {
  const page = setup();
  page.input.value = 'zelda';
  page.desk.click();
  assert.equal(page.input.value, '');
  assert.equal(page.count.textContent, 'Showing 2 of 4 guides that cover anime.');
  assert.equal(page.heading.scrolled, true);
});
