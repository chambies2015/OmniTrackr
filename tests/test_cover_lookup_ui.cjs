// Background cover lookups for music and books: they only take a search hit that
// is confidently the member's record, and they never rewrite the member's title or
// artist/author (a coverless "Blonde" once became "Moon River - Single").
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

function part(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  assert.ok(a >= 0 && b > a, start); return source.slice(a, b);
}

const helpers = part('function normalizeCoverMatchText(', 'async function fetchMusicMetadata(');

function matcher() {
  const context = vm.createContext({});
  vm.runInContext(helpers, context);
  return context;
}

const KINDS = {
  Music: {
    path: '/music/',
    body: results => ({ results }),
    hit: (title, creator, extra = {}) => ({ collectionName: title, artistName: creator, artworkUrl100: `https://art.example/${encodeURIComponent(title)}.jpg`, ...extra }),
    save: ['async function saveMusicMetadata(', 'async function deleteMusic('],
    creatorKey: 'artist',
  },
  Book: {
    path: '/books/',
    body: docs => ({ docs }),
    hit: (title, creator, extra = {}) => ({ title, author_name: [creator], cover_i: title.length, ...extra }),
    save: ['async function saveBookMetadata(', 'async function deleteBook('],
    creatorKey: 'author',
  },
};

async function lookUp(kind, title, creator, hits, existing) {
  const spec = KINDS[kind];
  const row = {}, puts = [], shown = [], updates = [];
  const context = vm.createContext({
    API_BASE: '', AbortController, console, editingRowElement: null, encodeURIComponent,
    document: { querySelector: () => ({ closest: () => row }) },
    posterFetchQueue: new Map(), posterFetchInProgress: new Set(), setTimeout: () => 1, clearTimeout() {},
    waitForPosterSlot: async () => {}, releasePosterSlot() {},
    cachedProxyFetch: async () => ({ ok: true, json: async () => spec.body(hits) }),
    authenticatedFetch: async (url, options) => { puts.push({ url, body: JSON.parse(options.body) }); return { ok: true }; },
  });
  context['display' + kind + 'Poster'] = (...args) => shown.push(args);
  context['update' + kind + 'RowMetadata'] = (...args) => updates.push(args);
  vm.runInContext(helpers, context);
  vm.runInContext(part('async function fetch' + kind + 'Metadata(', 'function update' + kind + 'RowMetadata('), context);
  vm.runInContext(part(...spec.save), context);
  await context['fetch' + kind + 'Metadata'](7, title, creator, existing);
  return { puts, shown, updates };
}

test('a coverless album skips the wrong first hit and never rewrites title or artist', async () => {
  const { puts, shown, updates } = await lookUp('Music', 'Blonde', 'Frank Ocean', [
    KINDS.Music.hit('Moon River - Single', 'Frank Ocean'),
    KINDS.Music.hit('Blonde on Blonde', 'Bob Dylan'),
    KINDS.Music.hit('Blonde', 'Frank Ocean', { releaseDate: '2016-08-20T07:00:00Z', primaryGenreName: 'R&B/Soul' }),
  ]);
  assert.equal(puts.length, 1);
  assert.equal(puts[0].url, '/music/7');
  assert.deepEqual(puts[0].body, { cover_art_url: 'https://art.example/Blonde.jpg', year: 2016, genre: 'R&B/Soul' });
  assert.equal(shown[0][2], 'Blonde', 'the poster keeps the member\'s title for its alt text');
  assert.equal(updates[0][1], null, 'artist cell untouched');
  assert.equal(updates[0][4], null, 'title cell untouched');
});

for (const kind of Object.keys(KINDS)) {
  test(kind + ' lookups with no confident hit save nothing', async () => {
    const { puts, shown } = await lookUp(kind, 'Blonde', 'Frank Ocean', [
      KINDS[kind].hit('Moon River - Single', 'Frank Ocean'),
      KINDS[kind].hit('Blonde', 'Someone Else'),
    ]);
    assert.deepEqual(puts, []);
    assert.deepEqual(shown, []);
  });

  test(kind + ' lookups keep the member\'s year and genre and never send a title or creator', async () => {
    const { puts } = await lookUp(kind, 'Title', 'Creator', [
      KINDS[kind].hit('Title', 'Creator', { releaseDate: '1999-01-01', primaryGenreName: 'Pop', first_publish_year: 1999, subject: ['Fiction'] }),
    ], { year: 2001, genre: 'Mine' });
    assert.equal(puts.length, 1);
    assert.deepEqual(Object.keys(puts[0].body), ['cover_art_url']);
    assert.ok(!('title' in puts[0].body) && !(KINDS[kind].creatorKey in puts[0].body));
  });
}

test('a book matches its subtitled edition only when the author agrees', async () => {
  const hits = [KINDS.Book.hit('Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', { cover_i: 42 })];
  const withAuthor = await lookUp('Book', 'Sapiens', 'Yuval Noah Harari', hits);
  assert.deepEqual(withAuthor.puts[0].body, { cover_art_url: 'https://covers.openlibrary.org/b/id/42-L.jpg' });
  const withoutAuthor = await lookUp('Book', 'Sapiens', '', hits);
  assert.deepEqual(withoutAuthor.puts, []);
});

test('a book edition with only an ISBN gets an ISBN cover link', async () => {
  const { puts } = await lookUp('Book', 'Dune', 'Frank Herbert', [
    { title: 'Dune', author_name: ['Frank Herbert'], isbn: ['9780441172719'] },
  ]);
  assert.equal(puts[0].body.cover_art_url, 'https://covers.openlibrary.org/b/isbn/9780441172719-L.jpg');
});

test('title and creator matching tolerates spelling noise but not different records', () => {
  const m = matcher();
  const music = entry => ({ title: entry.collectionName, creators: [entry.artistName] });
  const pick = (hits, title, artist) => m.pickConfidentCoverMatch(hits, title, artist, music)?.collectionName ?? null;
  const hit = (collectionName, artistName) => ({ collectionName, artistName });

  assert.equal(pick([hit('Rumours (Super Deluxe)', 'Fleetwood Mac')], 'Rumours', 'Fleetwood Mac'), 'Rumours (Super Deluxe)');
  assert.equal(pick([hit('Lemonade', 'Beyoncé')], 'lemonade', 'Beyonce'), 'Lemonade');
  assert.equal(pick([hit('Everything Is Love', 'Beyoncé & JAY-Z')], 'Everything Is Love', 'Beyonce'), 'Everything Is Love');
  assert.equal(pick([hit('Abbey Road', 'The Beatles')], 'abbey road', 'Beatles'), 'Abbey Road');
  assert.equal(pick([hit('÷ (Deluxe)', 'Ed Sheeran')], '÷', 'Ed Sheeran'), '÷ (Deluxe)');
  assert.equal(pick([hit('Blonde - Single', 'Frank Ocean'), hit('Blonde', 'Frank Ocean')], 'Blonde', 'Frank Ocean'), 'Blonde',
    'a full album beats a single of the same name');
  assert.equal(pick([hit('Blonde on Blonde', 'Bob Dylan')], 'Blonde', ''), null);
  assert.equal(pick([hit('Blonde', 'Frank Ocean')], 'Blonde', 'Frank'), 'Blonde');
  assert.equal(pick([hit('Blonde', 'Frank Ocean')], 'Blonde', 'Ocean Grove'), null);
  assert.equal(pick([], 'Blonde', 'Frank Ocean'), null);
  assert.equal(pick(undefined, 'Blonde', 'Frank Ocean'), null);

  assert.equal(m.coverCreatorsMatch('J.R.R. Tolkien', ['J. R. R. Tolkien']), true);
  assert.equal(m.coverCreatorsMatch('Tolkien', ['J.R.R. Tolkien']), true);
  assert.equal(m.coverCreatorsMatch('Jo', ['Jo Nesbø', 'Someone']), false, 'very short names are not enough');
});
