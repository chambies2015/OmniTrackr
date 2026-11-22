// A shared top ten (ranked-share.js): ranking the same titles in the page, how close two orders are,
// and the ranking kept in the browser until sign-up.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  const store = new Map();
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  global.document = undefined;
  global.window = {};
  const file = path.join(__dirname, '..', 'app', 'static', 'ranked-share.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const items = places => places.map(position => ({ position, title: `Title ${position}` }));

function play(share, list, better) {
  let game = share.start(list);
  let asked = 0;
  while (!share.done(game)) {
    const ask = share.current(game);
    game = share.answer(game, better(ask.placing, ask.against) ? 'placing' : 'against');
    asked += 1;
    assert.ok(asked < 100, 'never stops asking');
  }
  return { game, asked };
}

test('answering from a known order rebuilds that order', () => {
  const share = load();
  for (let round = 0; round < 25; round += 1) {
    const list = share.shuffled(items([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]));
    const { game, asked } = play(share, list, (a, b) => a.position < b.position);
    assert.deepEqual(game.order.map(item => item.position), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    assert.ok(asked <= 25, `ten titles took ${asked} picks`);
    assert.equal(share.agreement(game.order), 100);
  }
});

test('a reversed order agrees on nothing, and a tie puts the new title right below', () => {
  const share = load();
  const { game } = play(share, items([1, 2, 3, 4]), (a, b) => a.position > b.position);
  assert.deepEqual(game.order.map(item => item.position), [4, 3, 2, 1]);
  assert.equal(share.agreement(game.order), 0);
  let tie = share.start(items([7, 3]));
  tie = share.answer(tie, 'tie');
  assert.ok(share.done(tie));
  assert.deepEqual(tie.order.map(item => item.position), [7, 3]);
});

test('the estimate of picks left goes down to zero', () => {
  const share = load();
  let game = share.start(items([1, 2, 3, 4, 5]));
  let before = share.left(game);
  assert.ok(before >= 4);
  while (!share.done(game)) {
    game = share.answer(game, 'placing');
    const now = share.left(game);
    assert.ok(now <= before + 1);
    before = now;
  }
  assert.equal(share.left(game), 0);
});

test('the verdict follows the agreement', () => {
  const share = load();
  assert.match(share.verdict(95), /swap lists/);
  assert.match(share.verdict(75), /Mostly/);
  assert.match(share.verdict(50), /some/);
  assert.match(share.verdict(10), /opposite/);
});

test('a ranking kept before sign-up belongs to one link and expires', () => {
  const share = load();
  const token = 'abcdefghijklmnop';
  assert.equal(share.readTake(token), null);
  assert.ok(share.storeTake(token, ['Jaws', 'Alien', 'Heat'], true));
  assert.deepEqual(share.readTake(token), { token, titles: ['Jaws', 'Alien', 'Heat'], pending: true });
  assert.equal(share.readTake('qrstuvwxyzabcdef'), null);
  assert.equal(share.readTake(token, Date.now() + 4 * 24 * 60 * 60 * 1000), null);
  localStorage.setItem(share.KEY, JSON.stringify({ v: 1, token, titles: ['Only one'], at: Date.now(), pending: true }));
  assert.equal(share.readTake(token), null);
  localStorage.setItem(share.KEY, '{broken');
  assert.equal(share.readTake(token), null);
  share.storeTake(token, ['A', 'B'], false);
  share.clearTake();
  assert.equal(share.readTake(token), null);
});
