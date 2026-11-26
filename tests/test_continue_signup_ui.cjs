// /continue (Nov 26 2026): the link that carries a visitor's saved titles out of an app's browser.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  delete global.document;
  delete global.window;
  delete require.cache[require.resolve('../app/static/continue.js')];
  return require(path.join(__dirname, '../app/static/continue.js'));
}

const LIST = [
  { kind: 'movie', slug: 'star-wars-episode-iv-a-new-hope-1977', title: 'Star Wars: Episode IV - A New Hope', image: 'https://image.tmdb.org/t/p/w342/a.jpg' },
  { kind: 'anime', slug: 'frieren-beyond-journey-s-end-2023', title: 'Frieren: Beyond Journey’s End' },
  { kind: 'book', slug: 'la-sombra-del-viento-2001', title: 'La sombra del viento — Zafón' },
];

test('a packed list comes back the same, accents and all', () => {
  const api = load();
  const packed = api.pack(LIST, { path: '/in-order/star-wars', title: 'Star Wars in order' });
  assert.match(packed, /^[A-Za-z0-9_-]+$/);
  const back = api.unpack(packed);
  assert.deepEqual(back.items.map(item => item.title), LIST.map(item => item.title));
  assert.equal(back.items[0].image, LIST[0].image);
  assert.equal(back.items[1].image, undefined);
  assert.deepEqual(back.back, { path: '/in-order/star-wars', title: 'Star Wars in order' });
});

test('Chrome links leave the covers out to keep the link short', () => {
  const api = load();
  const packed = api.pack(LIST, null, { images: false });
  assert.equal(api.unpack(packed).items[0].image, undefined);
  const link = api.chromeLink('omnitrackr.xyz', LIST, null, 'https://omnitrackr.xyz/continue?via=app');
  assert.match(link, /^intent:\/\/omnitrackr\.xyz\/continue\?via=app&carry=[A-Za-z0-9_-]+#Intent;scheme=https;package=com\.android\.chrome;S\.browser_fallback_url=https%3A%2F%2Fomnitrackr\.xyz%2Fcontinue%3Fvia%3Dapp;end$/);
});

test('anything odd in a carried link is dropped', () => {
  const api = load();
  const forged = Buffer.from(JSON.stringify({
    v: 1,
    l: [
      { k: 'movie', s: 'ok-1999', t: 'Fine', i: 'javascript:alert(1)' },
      { k: 'script', s: 'x', t: 'Bad kind' },
      { k: 'tv', s: '../../etc', t: 'Bad slug' },
      { k: 'tv', s: 'no-title' },
    ],
    r: { p: '//evil.example/x', t: 'Elsewhere' },
  })).toString('base64url');
  const back = api.unpack(forged);
  assert.deepEqual(back.items, [{ kind: 'movie', slug: 'ok-1999', title: 'Fine' }]);
  assert.equal(back.back, null);
  assert.equal(api.unpack('not base64 !'), null);
  assert.equal(api.unpack(Buffer.from('{"v":2,"l":[]}').toString('base64url')), null);
  assert.equal(api.unpack('a'.repeat(20000)), null);
});

test('the carried text is read from the # or from ?carry=', () => {
  const api = load();
  assert.equal(api.carriedText({ hash: '#ot-carry=abc', search: '' }), 'abc');
  assert.equal(api.carriedText({ hash: '', search: '?via=app&carry=xyz' }), 'xyz');
  assert.equal(api.carriedText({ hash: '#signup', search: '' }), null);
});

test('carried titles join the list without repeats and without passing 30', () => {
  const api = load();
  let saved = [{ kind: 'movie', slug: 'star-wars-episode-iv-a-new-hope-1977', title: 'Star Wars: Episode IV - A New Hope' }];
  const list = { MAX: 30, read: () => saved.slice(), write: next => { saved = next; return true; } };
  const carried = api.unpack(api.pack(LIST, null));
  assert.equal(api.mergeCarried(list, carried), 2);
  assert.equal(saved.length, 3);
  assert.equal(api.mergeCarried(list, carried), 0);
  saved = Array.from({ length: 30 }, (_, index) => ({ kind: 'game', slug: `g-${index}`, title: `Game ${index}` }));
  assert.equal(api.mergeCarried(list, carried), 0);
  assert.equal(saved.length, 30);
});

test('the note under the heading counts the titles', () => {
  const api = load();
  assert.equal(api.titlesNote(1), 'The title you saved comes with you.');
  assert.equal(api.titlesNote(4), 'The 4 titles you saved come with you.');
});
