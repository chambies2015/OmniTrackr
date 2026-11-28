// Background cover lookups for every built-in library: they only take a search hit
// that is confidently the member's record, and they never rewrite the member's title
// or artist/author (a coverless "Blonde" once became "Moon River - Single").
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
  assert.deepEqual([...updates[0]], [7, null, 2016, 'R&B/Soul'], 'only year and genre reach the row; title and artist stay');
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

// Movies, TV, anime and games.
const POSTERS = {
  Movie: { fn: 'fetchMoviePoster', slice: ['async function fetchMoviePoster(', 'async function deleteMovie('], display: 'displayMoviePoster' },
  TV: { fn: 'fetchTVPoster', slice: ['async function fetchTVPoster(', 'async function fetchAnimePoster('], display: 'displayTVPoster' },
  Anime: { fn: 'fetchAnimePoster', slice: ['async function fetchAnimePoster(', '// Video Game functions'], display: 'displayAnimePoster' },
  VideoGame: { fn: 'fetchVideoGameMetadata', slice: ['async function fetchVideoGameMetadata(', 'async function deleteVideoGame('], display: 'displayVideoGamePoster' },
};

async function posterLookup(kind, body, ...args) {
  const spec = POSTERS[kind];
  const puts = [], shown = [], updates = [];
  const context = vm.createContext({
    API_BASE: '', AbortController, console, editingRowElement: null, encodeURIComponent,
    posterFetchQueue: new Map(), posterFetchInProgress: new Set(), setTimeout: () => 1, clearTimeout() {},
    waitForPosterSlot: async () => {}, releasePosterSlot() {},
    cachedProxyFetch: async () => ({ ok: true, json: async () => body }),
    authenticatedFetch: async (url, options) => { puts.push({ url, body: JSON.parse(options.body) }); return { ok: true }; },
    updateVideoGameRowMetadata: (...a) => updates.push(a),
  });
  context[spec.display] = (...a) => shown.push(a);
  vm.runInContext(helpers, context);
  vm.runInContext(part(...spec.slice), context);
  await context[spec.fn](7, ...args);
  return { puts, shown, updates };
}

for (const [kind, path] of [['Movie', '/movies/7'], ['TV', '/tv-shows/7']]) {
  test(kind + ' poster lookups keep the poster but never save OMDb\'s spelling of the title', async () => {
    const { puts, shown } = await posterLookup(kind, { Title: 'Star Wars: Episode IV - A New Hope', Poster: 'https://img.example/sw.jpg' }, 'star wars', 1977);
    assert.deepEqual(puts, [{ url: path, body: { poster_url: 'https://img.example/sw.jpg' } }]);
    assert.equal(shown[0][2], 'star wars');
  });
}

const jikan = (title, extra = {}) => ({ title, images: { jpg: { image_url: `https://cdn.example/${encodeURIComponent(title)}.jpg` } }, ...extra });

test('anime poster lookups skip a different show and never rename', async () => {
  const { puts, shown } = await posterLookup('Anime', { data: [
    jikan('Sousou no Frieren 2nd Season', { title_english: "Frieren: Beyond Journey's End Season 2", year: 2026 }),
    jikan('Sousou no Frieren', { title_english: "Frieren: Beyond Journey's End", year: 2023 }),
  ] }, 'Sousou no Frieren', 2023);
  assert.deepEqual(puts, [{ url: '/anime/7', body: { poster_url: 'https://cdn.example/Sousou%20no%20Frieren.jpg' } }]);
  assert.equal(shown[0][2], 'Sousou no Frieren');
});

test('anime poster lookups match English names, synonyms and the member\'s year', async () => {
  const twoVersions = { data: [
    jikan('Hunter x Hunter', { year: 1999 }),
    jikan('Hunter x Hunter (2011)', { title_english: 'Hunter x Hunter', aired: { prop: { from: { year: 2011 } } } }),
  ] };
  const remake = await posterLookup('Anime', twoVersions, 'Hunter x Hunter', 2011);
  assert.equal(remake.puts[0].body.poster_url, 'https://cdn.example/Hunter%20x%20Hunter%20(2011).jpg');
  const english = await posterLookup('Anime', { data: [jikan('Shingeki no Kyojin', { title_english: 'Attack on Titan' })] }, 'attack on titan', null);
  assert.equal(english.puts.length, 1);
  const synonym = await posterLookup('Anime', { data: [jikan('Kimetsu no Yaiba', { title_synonyms: ['KnY'] })] }, 'KnY', null);
  assert.equal(synonym.puts.length, 1);
  const unrelated = await posterLookup('Anime', { data: [jikan('Moon River')] }, 'Blonde', null);
  assert.deepEqual(unrelated.puts, []);
});

test('game lookups skip a different game, keep the member\'s title, and only fill blanks', async () => {
  const body = { results: [
    { name: 'Hades II', background_image: 'https://media.example/h2.jpg', slug: 'hades-2', released: '2025-09-25', genres: [{ name: 'Action' }] },
    { name: 'Hades', background_image: 'https://media.example/h1.jpg', slug: 'hades', released: '2020-09-17', genres: [{ name: 'Roguelike' }, { name: 'Action' }] },
  ] };
  const blank = await posterLookup('VideoGame', body, 'Hades');
  assert.deepEqual(blank.puts, [{ url: '/video-games/7', body: {
    cover_art_url: 'https://media.example/h1.jpg', genres: 'Roguelike, Action', rawg_link: 'https://rawg.io/games/hades', release_date: '2020-09-17',
  } }]);
  assert.equal(blank.shown[0][2], 'Hades');
  assert.deepEqual([...blank.updates[0]], [7, 'Roguelike, Action', 'https://rawg.io/games/hades', '2020-09-17']);

  const filled = await posterLookup('VideoGame', body, 'Hades', { genres: 'Mine', release_date: '2020-01-01', rawg_link: 'https://rawg.io/games/mine' });
  assert.deepEqual(filled.puts[0].body, { cover_art_url: 'https://media.example/h1.jpg' });

  const none = await posterLookup('VideoGame', { results: [body.results[0]] }, 'Hades');
  assert.deepEqual(none.puts, [], 'Hades II is a different game');
});

test('no lookup can send a title: every save helper drops it', () => {
  for (const name of ['saveMoviePosterUrl', 'saveTVPosterUrl', 'saveAnimePosterUrl', 'saveVideoGameMetadata', 'saveMusicMetadata', 'saveBookMetadata']) {
    const a = source.indexOf(`async function ${name}(`);
    const body = source.slice(a, source.indexOf('\n}\n', a));
    assert.ok(a >= 0, name);
    assert.doesNotMatch(body, /\.(title|artist|author)\s*=/, name + ' must not write a title or creator');
  }
});
