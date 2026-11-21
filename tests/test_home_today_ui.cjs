// "What's new" on the home screen (home-today.js): wording, the since-last-visit clock and rendering.
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

const NOW = new Date(2026, 10, 15, 18, 0);

test('past days count back and coming days name the weekday', () => {
  const { module } = setup();
  assert.equal(module.dayLabel('2026-11-15', NOW), 'today');
  assert.equal(module.dayLabel('2026-11-14', NOW), 'yesterday');
  assert.equal(module.dayLabel('2026-11-13', NOW), '2 days ago');
  assert.equal(module.dayLabel('2026-11-16', NOW), 'tomorrow');
  assert.equal(module.dayLabel('2026-11-20', NOW), 'on Friday');
});

test('since label reads like a person would say it', () => {
  const { module } = setup();
  assert.equal(module.sinceLabel(null, NOW), 'This week');
  assert.equal(module.sinceLabel(new Date(2026, 10, 15, 9), NOW), 'Since earlier today');
  assert.equal(module.sinceLabel(new Date(2026, 10, 14, 9), NOW), 'Since yesterday');
  assert.equal(module.sinceLabel(new Date(2026, 10, 12, 9), NOW), 'Since Thursday');
});

test('summary joins only the parts that have something', () => {
  const { module } = setup();
  const parts = module.summaryParts({ episodes: 2, releases: 0, friends: 1 });
  assert.deepEqual(parts, ['2 new episodes', '1 update from friends']);
  assert.equal(module.joinParts(parts), '2 new episodes and 1 update from friends');
  assert.equal(module.joinParts(['a', 'b', 'c']), 'a, b and c');
  assert.deepEqual(module.summaryParts({}), []);
});

test('a reload within half an hour keeps the same since; a later visit moves it on', () => {
  const { module, storage } = setup();
  const start = Date.UTC(2026, 10, 15, 12);
  assert.equal(module.readSince(start), null);
  assert.equal(module.readSince(start + 10 * 60 * 1000), null);
  const later = module.readSince(start + 3 * 60 * 60 * 1000);
  assert.equal(later.getTime(), start + 10 * 60 * 1000);
  assert.equal(module.readSince(start + 3 * 60 * 60 * 1000 + 60 * 1000).getTime(), start + 10 * 60 * 1000);
  assert.ok(storage.omnitrackr_home_seen.includes('"me"'));
});

test('friend lines use the right verb for each format', () => {
  const { module } = setup();
  assert.equal(module.friendLine({ type: 'title', kind: 'finished', category: 'books', title: 'Dune' }), 'read Dune');
  assert.equal(module.friendLine({ type: 'title', kind: 'rated', category: 'anime', title: 'Dandadan' }), 'rated Dandadan');
  assert.equal(module.friendLine({ type: 'burst', count: 5 }), 'added 5 titles');
  assert.equal(module.friendLine({ type: 'burst', count: 30, finished: 22 }), 'added 30 titles, 22 finished');
  assert.equal(module.friendLine({ type: 'burst', count: 8, finished: 8 }), "added 8 titles they've finished");
});

test('renders shows and friends, and the welcome strip line', () => {
  const { nodes, module } = setup();
  module.state.since = new Date(2026, 10, 14, 9);
  module.render({
    shows: [{ category: 'tv-shows', item_id: 3, title: 'Severance', library_title: 'Severance', image: null, network: 'Apple TV+',
      out: { code: 'S2 E7', date: '2026-11-13', name: 'Chikhai Bardo', new: true, waiting: true },
      next: { code: 'S2 E8', date: '2026-11-20' }, progress: 'S2 E6' }],
    releases: [],
    friends: { items: [{ type: 'title', kind: 'finished', category: 'movies', category_label: 'Movie', title: 'The Substance',
      friend: { id: 2, username: 'jordan' }, at: '2026-11-15T15:00:00', rating: 8, in_library: false, cheered: false, item_id: 9 }],
    new: 1, friends: 1 },
    counts: { episodes: 1, releases: 0, friends: 1 },
  }, NOW);
  assert.equal(nodes.homeNews.hidden, false);
  assert.equal(nodes.homeNews.dataset.columns, '2');
  assert.equal(nodes.homeNewsEyebrow.textContent, 'Since yesterday');
  assert.equal(nodes.homeNewsSummary.textContent, '1 new episode and 1 update from friends.');
  const show = nodes.homeNewsShowList.children[0].text;
  assert.match(show, /Ready to watch S2 E7: Chikhai Bardo · out 2 days ago/);
  assert.match(show, /You're on S2 E6 · next S2 E8 on Friday · Apple TV\+/);
  const friend = nodes.homeNewsFriendList.children[0].text;
  assert.match(friend, /jordan watched The Substance/);
  assert.match(friend, /Cheer Save/);
  assert.equal(nodes.homeHeroNews.hidden, false);
  assert.match(nodes.homeHeroNews.text, /Since yesterday: 1 new episode and 1 update from friends/);
});

test('no friends shows an invite; nothing at all keeps the card hidden once the invite is hidden', () => {
  const { nodes, module } = setup({ omnitrackr_home_invite_hidden: '1' });
  module.render({ shows: [], releases: [], friends: { items: [], new: 0, friends: 0 }, counts: {} }, NOW);
  assert.equal(nodes.homeNews.hidden, true);
  assert.equal(nodes.homeHeroNews.hidden, true);

  const second = setup();
  let invite = null;
  second.nodes.homeNewsFriends.append = node => { invite = node; };
  second.module.render({ shows: [], releases: [], friends: { items: [], new: 0, friends: 0 }, counts: {} }, NOW);
  assert.equal(second.nodes.homeNews.hidden, false);
  assert.match(invite.text, /Send a taste test/);
});
