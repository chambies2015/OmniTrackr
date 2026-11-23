// Break plan share links: the "plan these days" note kept across signing up, the tick meter, and
// which of a shared plan's titles the planner ticks for a member.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const share = require(path.join(__dirname, '../app/static/break-share.js'));
const page = require(path.join(__dirname, '../app/static/break-plan.js'));

function memoryStorage() {
  const values = new Map();
  return {
    getItem: key => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

test('the note from "Plan these days" lasts three days and only holds a real token', () => {
  const storage = memoryStorage();
  const now = Date.UTC(2026, 10, 24, 12);
  assert.equal(share.storePending('<script>alert(1)</script>', now, storage), false);
  assert.equal(share.readPending(now, storage), null);
  assert.equal(share.storePending('abcdefghijklmnopqrstuv', now, storage), true);
  assert.equal(share.readPending(now + 1000, storage).token, 'abcdefghijklmnopqrstuv');
  assert.equal(share.readPending(now + share.KEEP_MS + 1, storage), null);
  assert.equal(share.readPending(now - 120000, storage), null); // written in the future: a changed clock
  storage.setItem(share.PENDING, '{"v":1,"token":"short","at":1}');
  assert.equal(share.readPending(now, storage), null);
  storage.setItem(share.PENDING, 'not json');
  assert.equal(share.readPending(now, storage), null);
  share.storePending('abcdefghijklmnopqrstuv', now, storage);
  share.clearPending(storage);
  assert.equal(share.readPending(now, storage), null);
});

test('the tick meter never runs past full', () => {
  assert.equal(share.meterShare(5, 14), 36);
  assert.equal(share.meterShare(20, 14), 100);
  assert.equal(share.meterShare(1, 0), 0);
  assert.equal(share.meterShare('x', 4), 0);
});

test('titles saved before signing up and ones already on the list start ticked', () => {
  const titles = [
    { kind: 'tv', slug: 'severance-2022', mine: 'open' },
    { kind: 'movie', slug: 'paddington-2-2017', mine: 'finished' },
    { kind: 'album', slug: 'rumours-1977', mine: null },
    { kind: 'book', slug: 'piranesi-2020', mine: null },
  ];
  const guest = [{ kind: 'album', slug: 'rumours-1977', title: 'Rumours' }, { kind: 'movie', slug: 'paddington-2-2017' }, null, 'junk'];
  assert.deepEqual(page.defaultPicks(titles, guest), ['tv/severance-2022', 'album/rumours-1977']);
  assert.deepEqual(page.defaultPicks(titles, 'nope'), ['tv/severance-2022']);
  assert.deepEqual(page.defaultPicks(undefined, []), []);
});

test('the line after planning says how many of the picked titles fit', () => {
  assert.equal(page.takenLine({ picked: 3, placed: 3 }, 'nova'), " All 3 from nova's plan are on it.");
  assert.equal(page.takenLine({ picked: 1, placed: 1 }, null), ' The one from the shared plan is on it.');
  assert.equal(page.takenLine({ picked: 4, placed: 2 }, null), ' 2 of the 4 from the shared plan fit. The rest wait on your list.');
  assert.equal(page.takenLine({ picked: 2, placed: 0 }, 'nova'), " None of the ones from nova's plan fit the time you have, so they wait on your list.");
  assert.equal(page.takenLine({ picked: 0, placed: 0 }, 'nova'), '');
  assert.equal(page.takenLine(undefined, 'nova'), '');
});
