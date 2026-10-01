// Dashboard "Quick start" and "Coming up for you" rendering.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = ''; this.listeners = {}; this.classList = { toggle: () => {}, add: () => {} }; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  replaceWith() {}
  get text() { return [this.textContent, ...this.children.map(child => (child.text !== undefined ? child.text : String(child.data || '')))].join(' '); }
}

function setup() {
  const ids = ['starterPicks', 'starterPicksPopular', 'starterPicksUpcoming', 'starterPicksUpcomingTitle', 'starterPicksStatus',
    'starterPicksProgress', 'comingUp', 'comingUpList', 'comingUpSummary', 'comingUpEmail', 'comingUpEmailToggle', 'comingUpStatus'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  global.document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: tag => new Node(tag),
    createTextNode: data => ({ data }),
    addEventListener() {},
  };
  global.window = {};
  delete require.cache[require.resolve('../app/static/for-you.js')];
  const module = require(path.join(__dirname, '../app/static/for-you.js'));
  return { nodes, module };
}

test('quick start shows popular picks with member counts and a progress goal', () => {
  const { nodes, module } = setup();
  module.renderStarter({
    library_total: 2,
    popular: [{ category: 'movies', label: 'Movie', title: 'Interstellar <b>', year: 2014, creator: 'Christopher Nolan', image: null, members: 6 }],
    upcoming: [],
  });
  assert.equal(nodes.starterPicks.hidden, false);
  assert.equal(nodes.starterPicksPopular.children.length, 1);
  const card = nodes.starterPicksPopular.children[0];
  assert.match(card.text, /Interstellar <b>/);           // plain text, never parsed as HTML
  assert.match(card.text, /Saved by 6 members/);
  assert.match(card.text, /Movie · 2014 · Christopher Nolan/);
  assert.equal(nodes.starterPicksProgress.textContent, '2 of 5 titles saved');
  assert.equal(nodes.starterPicksUpcomingTitle.hidden, true);
});

test('quick start hides itself when there is nothing to suggest', () => {
  const { nodes, module } = setup();
  module.renderStarter({ library_total: 0, popular: [], upcoming: [] });
  assert.equal(nodes.starterPicks.hidden, true);
});

test('coming up lists library matches first with the reason and offers the email toggle', () => {
  const { nodes, module } = setup();
  module.renderComingUp({
    library_total: 4,
    matches: [{ category: 'tv', label: 'TV', title: 'Severance', date: '2026-10-02', url: '/release-radar/tv#item-t1', reason: 'In your library: Severance', details: [] }],
    popular: [{ category: 'games', label: 'Game', title: 'Big Game', date: '2026-10-09', url: '/release-radar/games#item-g', reason: '', details: ['PC'] }],
    email: { enabled: true, available: true },
  });
  assert.equal(nodes.comingUp.hidden, false);
  assert.match(nodes.comingUpSummary.textContent, /1 new release connected/);
  assert.equal(nodes.comingUpList.children.length, 2);
  assert.match(nodes.comingUpList.children[0].text, /In your library: Severance/);
  assert.equal(nodes.comingUpEmail.hidden, false);
  assert.equal(nodes.comingUpEmailToggle.checked, true);
});

test('coming up stays hidden for an empty library and hides the toggle when mail is not set up', () => {
  const { nodes, module } = setup();
  module.renderComingUp({ library_total: 0, matches: [], popular: [{ title: 'x' }] });
  assert.equal(nodes.comingUp.hidden, true);
  module.renderComingUp({ library_total: 3, matches: [], popular: [{ category: 'movies', label: 'Movie', title: 'Film', date: null, url: '/x', details: [] }], email: { enabled: false, available: false } });
  assert.equal(nodes.comingUp.hidden, false);
  assert.match(nodes.comingUpSummary.textContent, /popular instead/);
  assert.equal(nodes.comingUpEmail.hidden, true);
});

test('dates read naturally', () => {
  const { module } = setup();
  assert.equal(module.friendlyDate(null), 'Date to be announced');
  assert.equal(module.friendlyDate('not-a-date'), 'Date to be announced');
  assert.match(module.friendlyDate('2030-01-15'), /Jan 15/);
});
