// Tier list maker (/tier-list): board state survives bad saved data and moves titles predictably.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = undefined;
  global.window = {};
  delete require.cache[require.resolve('../app/static/tier-list.js')];
  return require(path.join(__dirname, '../app/static/tier-list.js'));
}

test('titles are added once, moved between tiers in order, and removed', () => {
  const api = load();
  const state = api.emptyState();
  const dune = api.addItem(state, { title: 'Dune', kind: 'movie', year: 2021 });
  const heat = api.addItem(state, { title: 'Heat', kind: 'movie', year: 1995 }, 'S');
  const up = api.addItem(state, { title: 'Up', kind: 'movie', year: 2009 }, 'S');
  assert.equal(api.addItem(state, { title: 'dune', kind: 'movie', year: 2021 }), null);
  assert.deepEqual(state.pool, [dune]);
  assert.deepEqual(state.tiers.S, [heat, up]);
  assert.ok(api.moveItem(state, dune, 'S', up));
  assert.deepEqual(state.tiers.S, [heat, dune, up]);
  assert.deepEqual(state.pool, []);
  assert.ok(api.moveItem(state, heat, 'pool'));
  assert.deepEqual(state.tiers.S, [dune, up]);
  assert.equal(api.moveItem(state, heat, 'Z'), false);
  assert.ok(api.removeItem(state, up));
  assert.equal(state.items[up], undefined);
  assert.deepEqual(state.tiers.S, [dune]);
});

test('templates and library sets place titles by their suggested tier', () => {
  const api = load();
  const state = api.fromTemplate({ name: 'Mine', items: [
    { title: 'A', kind: 'movie', tier: 'S' }, { title: 'B', kind: 'movie', tier: null }, { title: 'C', kind: 'movie', tier: 'D' },
  ] });
  assert.equal(state.name, 'Mine');
  assert.equal(state.tiers.S.length, 1);
  assert.equal(state.tiers.D.length, 1);
  assert.equal(state.pool.length, 1);
});

test('saved boards are cleaned: unsafe images, bad slugs, duplicates and unknown tiers are dropped', () => {
  const api = load();
  const state = api.normalizeState({
    name: 'x'.repeat(200),
    labels: { S: '  Rewatch every year  ', A: 42 },
    tiers: { S: ['t1', 't1', 'missing'], A: ['t2'], Z: ['t3'] },
    pool: ['t3', 't2'],
    items: {
      t1: { title: 'Ok', kind: 'movie', image: 'javascript:alert(1)', slug: '../../x' },
      t2: { title: '<b>Bold</b>', kind: 'evil', image: 'https://m.media-amazon.com/a.jpg', slug: 'bold-2020' },
      t3: { title: '   ' },
    },
    next: 2,
  });
  assert.equal(state.name.length, 80);
  assert.equal(state.labels.S, 'Rewatch every year');
  assert.equal(state.labels.A, 'A');
  assert.deepEqual(state.tiers.S, ['t1']);
  assert.deepEqual(state.tiers.A, ['t2']);
  assert.deepEqual(state.pool, []);
  assert.equal(state.items.t1.image, null);
  assert.equal(state.items.t1.slug, null);
  assert.equal(state.items.t2.kind, null);
  assert.equal(state.items.t2.slug, null);
  assert.equal(state.items.t2.title, '<b>Bold</b>');
  assert.ok(state.next >= 3);
  assert.deepEqual(api.normalizeState('garbage').tiers.S, []);
});

test('the board has a size limit and the export grows with its rows', () => {
  const api = load();
  const state = api.emptyState();
  for (let i = 0; i < api.MAX_ITEMS + 5; i += 1) api.addItem(state, { title: `T${i}` }, 'S');
  assert.equal(state.tiers.S.length, api.MAX_ITEMS);
  const small = api.exportLayout(api.emptyState());
  const big = api.exportLayout(state);
  assert.ok(big.height > small.height);
  assert.equal(api.fileName({ name: 'Fall 2026: Anime!' }), 'fall-2026-anime.png');
  assert.equal(api.fileName({ name: '***' }), 'tier-list.png');
});

test('a board started from a shared list scores agreement tier by tier', () => {
  const api = load();
  const source = api.sourceFromShare({
    token: 'AAAAAAAAAAAAAAAA', name: 'Theirs', by: 'dan',
    tiers: { S: [{ title: 'Dune', kind: 'movie', year: 2021 }], A: [{ title: 'Heat', kind: 'movie', year: 1995 }], B: [],
      C: [{ title: 'Up', kind: 'movie', year: 2009 }], D: [] },
  });
  const state = api.emptyState();
  state.source = source;
  api.addItem(state, { title: 'Dune', kind: 'movie', year: 2021 }, 'S');
  api.addItem(state, { title: 'Heat', kind: 'movie', year: 1995 }, 'B');
  api.addItem(state, { title: 'Up', kind: 'movie', year: 2009 }, 'S');
  api.addItem(state, { title: 'Extra', kind: 'movie', year: 2000 }, 'S');
  const result = api.agreement(state);
  assert.equal(result.compared, 3);
  assert.equal(result.same, 1);
  assert.equal(result.close, 1);
  assert.equal(result.score, 50);
  assert.deepEqual(result.apart, [{ title: 'Up', mine: 'S', theirs: 'C', gap: 3 }]);
});

test('saved boards keep their link and source, and drop bad ones', () => {
  const api = load();
  const state = api.emptyState();
  api.addItem(state, { title: 'Dune', kind: 'manga', year: 2021, slug: 'dune-2021' }, 'S');
  state.link = 'BBBBBBBBBBBBBBBB';
  state.source = { token: 'AAAAAAAAAAAAAAAA', name: 'Theirs', by: 'x', ranks: { 'dune|movie|2021': 0, bad: 9 } };
  const back = api.normalizeState(JSON.parse(JSON.stringify(state)));
  assert.equal(back.link, 'BBBBBBBBBBBBBBBB');
  assert.deepEqual(back.source.ranks, { 'dune|movie|2021': 0 });
  assert.equal(back.items[back.tiers.S[0]].kind, 'manga');
  assert.equal(api.normalizeState({ link: '../x', source: { token: 'short' } }).link, null);
  assert.equal(api.normalizeState({ source: { token: 'short' } }).source, null);
});

test('a share payload holds only ranked titles', () => {
  const api = load();
  const state = api.emptyState();
  api.addItem(state, { title: 'Dune', kind: 'movie', year: 2021 }, 'S');
  api.addItem(state, { title: 'Waiting', kind: 'movie', year: 2000 });
  state.template = 'franchise-dune';
  const payload = api.sharePayload(state);
  assert.deepEqual(payload.tiers.S.map(item => item.title), ['Dune']);
  assert.equal(JSON.stringify(payload).includes('Waiting'), false);
  assert.equal(payload.template, 'franchise-dune');
  assert.equal(payload.source, null);
});
