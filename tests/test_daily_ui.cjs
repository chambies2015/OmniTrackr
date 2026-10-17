// OmniTrackr Daily (/daily): stored games survive bad data, results share without spoilers, streaks count days.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = undefined;
  global.window = {};
  delete require.cache[require.resolve('../app/static/daily.js')];
  return require(path.join(__dirname, '../app/static/daily.js'));
}

const ANSWER = { id: 'movie/heat-1995', kind: 'movie', slug: 'heat-1995', title: 'Heat', year: 1995, clues: [] };

function play(api, number, guesses, won, isDaily = true) {
  const game = api.newGame(number, 'Clue one', isDaily);
  guesses.forEach((text, index) => {
    const last = index === guesses.length - 1;
    const done = last && (won || guesses.length === 6);
    api.applyResult(game, text, done ? { correct: won && last, done: true, answer: ANSWER } : { correct: false, done: false, clue: `Clue ${index + 2}` });
  });
  return game;
}

test('a game reveals clues, ends with the answer and shares only squares', () => {
  const api = load();
  const game = play(api, 12, ['Ronin', '', 'Heat'], true);
  assert.deepEqual(game.clues, ['Clue one', 'Clue 2', 'Clue 3']);
  assert.ok(game.done && game.won);
  assert.equal(api.squares(game), '🟥⬛🟩');
  const text = api.shareText(game, '🎬', 'https://omnitrackr.xyz');
  assert.equal(text, 'OmniTrackr Daily #12 🎬 3/6\n🟥⬛🟩\nomnitrackr.xyz/daily');
  assert.ok(!text.includes('Heat'));
  api.applyResult(game, 'Another', { correct: false, done: false, clue: 'x' });
  assert.equal(game.guesses.length, 3, 'a finished game ignores more guesses');
  const lost = play(api, 13, ['a', 'b', 'c', 'd', 'e', 'f'], false);
  assert.ok(lost.done && !lost.won);
  assert.match(api.shareText(lost, '🎬'), /X\/6\n🟥🟥🟥🟥🟥🟥/);
});

test('repeat guesses are spotted regardless of case, accents and a leading article', () => {
  const api = load();
  const game = play(api, 1, ['The Pokémon Movie'], false);
  assert.ok(api.alreadyTried(game, 'pokemon movie'));
  assert.ok(!api.alreadyTried(game, 'Pokemon Movie 2'));
  assert.ok(!api.alreadyTried(game, ''));
});

test('stored data is cleaned and an unfinished game never claims an answer', () => {
  const api = load();
  const store = api.normalizeStore({ games: {
    abc: { guesses: [] },
    '-1': { guesses: [] },
    5: { guesses: [{ t: 'x', ok: false }, { t: 7 }, null], clues: ['a', 3], done: true },
    6: { guesses: [{ t: 'Heat', ok: true }], clues: ['a'], done: true, answer: ANSWER, daily: true },
  } });
  assert.deepEqual(Object.keys(store.games), ['5', '6']);
  assert.equal(store.games[5].done, false);
  assert.equal(store.games[5].guesses.length, 1);
  assert.deepEqual(store.games[5].clues, ['a']);
  assert.ok(store.games[6].won && store.games[6].daily);
  assert.deepEqual(api.normalizeStore('nonsense'), { v: 1, games: {} });
});

test('streaks count consecutive days played on the day; archive plays do not count', () => {
  const api = load();
  const store = { v: 1, games: {} };
  [1, 2, 3].forEach(n => { store.games[n] = play(api, n, ['Heat'], true); });
  store.games[4] = play(api, 4, ['a', 'b', 'c', 'd', 'e', 'f'], false);
  [5, 6].forEach(n => { store.games[n] = play(api, n, ['x', 'Heat'], true); });
  store.games[7] = play(api, 7, ['Heat'], true, false);
  let s = api.stats(store, 7);
  assert.equal(s.played, 6);
  assert.equal(s.wins, 5);
  assert.equal(s.winRate, 83);
  assert.equal(s.current, 2, "today is not played yet, so yesterday's streak still stands");
  assert.equal(s.best, 3);
  assert.deepEqual(s.distribution, [3, 2, 0, 0, 0, 0]);
  s = api.stats(store, 8);
  assert.equal(s.current, 0, 'missing a day breaks the streak');
  store.games[7] = play(api, 7, ['Heat'], true, true);
  assert.equal(api.stats(store, 7).current, 3);
});

test('countdown formats hours, minutes and seconds', () => {
  const api = load();
  assert.equal(api.countdown(3661), '01:01:01');
  assert.equal(api.countdown(-5), '00:00:00');
});
