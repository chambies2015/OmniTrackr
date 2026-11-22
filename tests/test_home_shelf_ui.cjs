// Homepage "Your library" panel: covers kept with saved titles, the change event, and the panel's words.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function loadGuestList() {
  const store = new Map();
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  const dispatched = [];
  global.CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } };
  global.document = {
    readyState: 'complete', documentElement: { dataset: { publicShell: 'true' } }, body: { appendChild() {} },
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
    dispatchEvent: event => dispatched.push(event),
    createElement: () => ({ setAttribute() {}, remove() {}, textContent: '' }),
  };
  global.window = { reportFunnelEvent() {} };
  global.setTimeout = () => 0;
  delete require.cache[require.resolve('../app/static/guest-list.js')];
  const api = require(path.join(__dirname, '../app/static/guest-list.js'));
  return { api, dispatched };
}

test('a cover is kept with the title only when it is a plain web address', () => {
  const { api } = loadGuestList();
  api.add('movie', 'arrival-2016', 'Arrival', 'https://img.example/arrival.jpg');
  api.add('movie', 'heat-1995', 'Heat', 'javascript:alert(1)');
  api.add('movie', 'up-2009', 'Up', 'https://img.example/a"onerror="x.jpg');
  const [arrival, heat, up] = api.read();
  assert.equal(arrival.image, 'https://img.example/arrival.jpg');
  assert.equal(heat.image, undefined);
  assert.equal(up.image, undefined);
});

test('tapping a tile saves its cover and tells the panel', () => {
  const { api, dispatched } = loadGuestList();
  const tile = {
    dataset: { guestKind: 'game', guestSlug: 'balatro-2024', guestTitle: 'Balatro' },
    querySelector: () => ({ getAttribute: () => 'https://img.example/balatro.jpg' }),
  };
  api.toggleTile(tile);
  assert.equal(api.read()[0].image, 'https://img.example/balatro.jpg');
  const last = dispatched[dispatched.length - 1];
  assert.equal(last.type, 'omni:guest-list');
  assert.equal(last.detail.list.length, 1);
  api.toggleTile(tile);
  assert.deepEqual(api.read(), []);
  assert.equal(dispatched[dispatched.length - 1].detail.list.length, 0);
});

test('a suggestion carries its cover in data-guest-image', () => {
  const { api } = loadGuestList();
  api.toggleTile({ dataset: { guestKind: 'tv', guestSlug: 'severance-2022', guestTitle: 'Severance', guestImage: 'https://img.example/s.jpg' } });
  assert.equal(api.read()[0].image, 'https://img.example/s.jpg');
});

function loadShelf() {
  delete global.document;
  delete global.window;
  delete require.cache[require.resolve('../app/static/home-shelf.js')];
  return require(path.join(__dirname, '../app/static/home-shelf.js'));
}

test('the count line names the formats', () => {
  const shelf = loadShelf();
  assert.equal(shelf.countLine([]), 'Nothing on it yet');
  assert.equal(shelf.countLine([{ kind: 'movie' }]), '1 movie');
  assert.equal(shelf.countLine([{ kind: 'movie' }, { kind: 'movie' }]), '2 movies');
  assert.equal(shelf.countLine([{ kind: 'movie' }, { kind: 'game' }, { kind: 'movie' }]), '3 titles: 2 movies, 1 game');
  assert.equal(shelf.countLine([{ kind: 'anime' }, { kind: 'anime' }, { kind: 'book' }]), '3 titles: 2 anime, 1 book');
});

test('what keeping the list gets you follows what was saved', () => {
  const shelf = loadShelf();
  const films = shelf.perks([{ kind: 'movie', title: 'Arrival' }]);
  assert.equal(films[0], 'Rate Arrival and log the day you finish it');
  assert.ok(films.some(line => /US streaming services/.test(line)));
  const show = shelf.perks([{ kind: 'game', title: 'Balatro' }, { kind: 'tv', title: 'Severance' }]);
  assert.ok(show.some(line => line === 'Get a note when Severance has a new episode out'));
  const books = shelf.perks([{ kind: 'book', title: 'Dune' }]);
  assert.deepEqual(books, ['Rate Dune and log the day you finish it', 'Save the page or chapter you’re on']);
  const games = shelf.perks([{ kind: 'game', title: 'Hades' }]);
  assert.equal(games.length, 2);
  assert.match(games[1], /Year in Review/);
});
