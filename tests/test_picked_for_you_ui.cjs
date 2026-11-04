// Dashboard "For you" tab and its home card (picked-for-you.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = ''; this.listeners = {}; this.dataset = {}; this.attributes = {}; this.classList = { toggle: () => {}, add: () => {} }; this.parentElement = { hidden: false }; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute(name, value) { this.attributes[name] = value; }
  replaceWith() {}
  get text() { return [this.textContent, ...this.children.map(child => child.text)].join(' '); }
}

function setup() {
  const ids = ['picksTeaser', 'picksTeaserList', 'starterPicks', 'picksGrid', 'picksRows', 'picksFilters', 'picksGuides',
    'picksSummary', 'picksStatus', 'picksAllTitle', 'picksUndo'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  nodes.starterPicks.hidden = true;
  nodes.picksTeaser.hidden = true;
  global.localStorage = { store: new Map(), getItem(k) { return this.store.get(k) ?? null; }, setItem(k, v) { this.store.set(k, v); } };
  global.document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: tag => new Node(tag),
    querySelectorAll: () => [],
    addEventListener() {},
  };
  global.window = { location: { hash: '' }, addEventListener() {} };
  delete require.cache[require.resolve('../app/static/picked-for-you.js')];
  const module = require(path.join(__dirname, '../app/static/picked-for-you.js'));
  return { nodes, module };
}

function pick(id, kind, title, extra = {}) {
  return { id, kind, category: 'movies', label: 'Movie', title, year: 2016, creator: null, image: null,
    url: `/titles/${id}`, reason: `Because you rated Interstellar 9.5/10`, detail: 'Saved by 3 members with similar taste',
    anchor: 'movie/interstellar-2014', anchor_title: 'Interstellar', ...extra };
}

const DATA = {
  state: 'ready', library_total: 12, rated: 8, neighbours: 4,
  picks: [pick('movie/arrival-2016', 'movie', 'Arrival <b>'), pick('movie/contact-1997', 'movie', 'Contact'),
    pick('movie/gravity-2013', 'movie', 'Gravity'), pick('anime/frieren-2023', 'anime', 'Frieren', { anchor: null, anchor_title: null, reason: 'Shares Fantasy and Adventure with Mushishi' })],
  rows: [{ anchor: 'movie/interstellar-2014', title: 'Interstellar', kind: 'movie', label: 'Movie', rating: 9.5,
    picks: ['movie/arrival-2016', 'movie/contact-1997', 'movie/gravity-2013'] }],
  guides: [{ title: 'If you liked Interstellar', url: '/if-you-liked/interstellar', anchor: 'Interstellar' }],
};

test('the tab groups picks under the title behind them and lists the rest below', () => {
  const { nodes, module } = setup();
  module.state.data = DATA;
  module.renderTab();
  assert.equal(nodes.picksRows.children.length, 1);
  const row = nodes.picksRows.children[0];
  assert.match(row.text, /Because you liked Interstellar/);
  assert.match(row.text, /Arrival <b>/);                      // plain text, never parsed as HTML
  assert.doesNotMatch(row.text, /Because you rated/);          // the row heading already says why
  assert.equal(nodes.picksGrid.children.length, 1);
  assert.match(nodes.picksGrid.children[0].text, /Shares Fantasy and Adventure with Mushishi/);
  assert.equal(nodes.picksAllTitle.textContent, 'More picks for you');
  assert.match(nodes.picksSummary.textContent, /^4 members track a lot of what you track/);
  assert.equal(nodes.picksGuides.hidden, false);
  // Filter chips only for formats that have picks.
  assert.deepEqual(nodes.picksFilters.children.map(chip => chip.textContent), ['Everything', 'Movies', 'Anime']);
});

test('a format filter drops the rows and shows only that format', () => {
  const { nodes, module } = setup();
  module.state.data = DATA;
  module.state.filter = 'anime';
  module.renderTab();
  assert.equal(nodes.picksRows.hidden, true);
  assert.equal(nodes.picksGrid.children.length, 1);
  assert.equal(nodes.picksAllTitle.textContent, 'Anime for you');
});

test('the home card shows four picks for an established library and explains each in a few words', () => {
  const { nodes, module } = setup();
  module.state.data = DATA;
  module.renderTeaser();
  assert.equal(nodes.picksTeaser.hidden, false);
  assert.equal(nodes.picksTeaserList.children.length, 4);
  assert.match(nodes.picksTeaserList.children[0].text, /For fans of Interstellar/);
});

test('the home card stays hidden while Quick start shows, for small libraries, or after Hide', () => {
  let { nodes, module } = setup();
  nodes.starterPicks.hidden = false;
  module.state.data = DATA;
  module.renderTeaser();
  assert.equal(nodes.picksTeaser.hidden, true);

  ({ nodes, module } = setup());
  module.state.data = { ...DATA, library_total: 3 };
  module.renderTeaser();
  assert.equal(nodes.picksTeaser.hidden, true);

  ({ nodes, module } = setup());
  localStorage.setItem('omnitrackr_picks_card_hidden_member', '1');
  module.state.data = DATA;
  module.renderTeaser();
  assert.equal(nodes.picksTeaser.hidden, true);
});

test('hidden picks drop out until restored, and an empty list says so', () => {
  const { nodes, module } = setup();
  module.state.data = { ...DATA, rows: [], picks: DATA.picks.slice(0, 1) };
  module.state.hidden.add('movie/arrival-2016');
  module.renderTab();
  assert.equal(nodes.picksGrid.children.length, 0);
  assert.match(nodes.picksStatus.textContent, /seen every pick/);
});

test('summaries match how much the picks know', () => {
  const { module } = setup();
  assert.match(module.summaryText({ state: 'empty' }), /titles members track most/);
  assert.match(module.summaryText({ state: 'thin' }), /doesn’t overlap much/);
  assert.match(module.summaryText({ state: 'ready', neighbours: 1 }), /^1 member tracks/);
});
