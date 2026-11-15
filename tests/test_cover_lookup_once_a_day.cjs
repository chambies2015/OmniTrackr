// Rows the cover services don't know used to be looked up again on every visit and
// every re-render (up to 50 requests per library page). A row tried on an earlier
// visit now waits a day; within one visit nothing changes.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

const start = source.indexOf("const COVER_TRY_KEY = 'omnitrackr_cover_tries';");
const end = source.indexOf('function getPosterConcurrencyLimit(');
assert.ok(start > 0 && end > start);
const helpers = source.slice(start, end);

function visit(storage, now) {
  const timers = [];
  const localStorage = {
    getItem: key => (key in storage ? storage[key] : null),
    setItem: (key, value) => { storage[key] = String(value); },
  };
  const context = vm.createContext({ localStorage, setTimeout: fn => timers.push(fn), Date: { now: () => now } });
  vm.runInContext(helpers, context);
  return { ask: (...args) => context.shouldLookUpCover(...args), flush: () => timers.splice(0).forEach(fn => fn()) };
}

test('a row is looked up on the first visit and skipped on the next one that day', () => {
  const storage = {};
  const first = visit(storage, 1_000_000);
  assert.equal(first.ask('movies', 7, 'Blonde'), true);
  assert.equal(first.ask('movies', 7, 'Blonde'), true, 're-renders in the same visit behave as before');
  first.flush();
  const later = visit(storage, 1_000_000 + 60 * 60 * 1000);
  assert.equal(later.ask('movies', 7, 'Blonde'), false);
  assert.equal(later.ask('music', 7, 'Blonde'), true, 'each library keeps its own rows');
  assert.equal(later.ask('movies', 7, 'Blond'), true, 'an edited title is tried again');
});

test('a day later the row is tried again', () => {
  const storage = {};
  const first = visit(storage, 0);
  first.ask('books', 3, 'Dune');
  first.flush();
  const nextDay = visit(storage, 24 * 60 * 60 * 1000 + 1);
  assert.equal(nextDay.ask('books', 3, 'Dune'), true);
});

test('blocked or broken storage never stops a lookup', () => {
  const context = vm.createContext({
    localStorage: { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } },
    setTimeout: fn => fn(), Date,
  });
  vm.runInContext(helpers, context);
  assert.equal(context.shouldLookUpCover('anime', 1, 'Frieren'), true);
  const junk = visit({ omnitrackr_cover_tries: '[1,2,3]' }, 5);
  assert.equal(junk.ask('anime', 1, 'Frieren'), true);
});

test('every library render asks before looking a cover up', () => {
  for (const [kind, call] of [
    ['movies', 'fetchMoviePoster(movie.id'], ['tv-shows', 'fetchTVPoster(tvShow.id'], ['anime', 'fetchAnimePoster(animeItem.id'],
    ['video-games', 'fetchVideoGameMetadata(game.id'], ['music', 'fetchMusicMetadata(item.id'], ['books', 'fetchBookMetadata(book.id'],
  ]) {
    const at = source.indexOf(call);
    assert.ok(at > 0, call);
    const before = source.slice(source.lastIndexOf('} else', at), at);
    assert.match(before, new RegExp(`shouldLookUpCover\\('${kind}'`), call);
  }
});
