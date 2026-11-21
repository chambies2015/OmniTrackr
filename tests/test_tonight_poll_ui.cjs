// Group poll (tonight.js): the shortlist kept in the browser before sign-up, "Pick four for me",
// the share links, and the sign-in return that brings a new member back to their shortlist.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const poll = require('../app/static/tonight.js');
const NOW = 1900000000000;
const DAY = 86400000;
const film = (title, year, extra = {}) => ({ kind: 'movie', title, year, ...extra });

test('a stored shortlist is checked field by field', () => {
  const draft = poll.parseDraft(JSON.stringify({
    at: NOW - 1000, question: 'Friday film?', hours: 24, waiting: true,
    options: [
      film('Heat', 1995, { slug: 'heat-1995', image: 'https://img.example/heat.jpg' }),
      film('  Heat ', 1995),                                             // the same title again
      film('Arrival', 2016, { slug: '../../etc', image: 'javascript:alert(1)' }),
      { kind: 'boat', title: 'Titanic', year: 1997 },                   // not a kind we track
      film('', 2000),
      film('Old', 12),
    ],
  }), NOW);
  assert.equal(draft.question, 'Friday film?');
  assert.equal(draft.hours, 24);
  assert.equal(draft.waiting, true);
  assert.deepEqual(draft.options, [
    { kind: 'movie', label: 'Movie', title: 'Heat', year: 1995, slug: 'heat-1995', image: 'https://img.example/heat.jpg' },
    { kind: 'movie', label: 'Movie', title: 'Arrival', year: 2016, slug: null, image: null },
    { kind: 'movie', label: 'Movie', title: 'Old', year: null, slug: null, image: null },
  ]);
});

test('old, future, empty or broken shortlists are ignored', () => {
  const options = [film('Heat', 1995), film('Arrival', 2016)];
  assert.equal(poll.parseDraft('not json', NOW), null);
  assert.equal(poll.parseDraft(JSON.stringify({ at: NOW - 8 * DAY, options }), NOW), null);
  assert.equal(poll.parseDraft(JSON.stringify({ at: NOW + 60000, options }), NOW), null);
  assert.equal(poll.parseDraft(JSON.stringify({ at: NOW, options: 'Heat' }), NOW), null);
  assert.equal(poll.parseDraft(JSON.stringify({ at: NOW, question: '  ', options: [] }), NOW), null);
  // An odd closing time falls back to three hours, and a poll never holds more than eight titles.
  const many = Array.from({ length: 12 }, (_, n) => film(`Film ${n}`, 2000 + n));
  const draft = poll.parseDraft(JSON.stringify({ at: NOW, hours: 5, options: many }), NOW);
  assert.equal(draft.hours, 3);
  assert.equal(draft.options.length, 8);
  assert.equal(draft.waiting, false);
});

test('pick four for me stays with one kind and tops up what is already picked', () => {
  const pool = [film('A', 2001), { kind: 'tv', title: 'Show', year: 2020 }, film('B', 2002), film('C', 2003),
    film('D', 2004), film('E', 2005)];
  assert.deepEqual(poll.fillChoice(pool, [], 8).map(item => item.title), ['A', 'B', 'C', 'D']);
  // One film picked already: three more films, never the one already there.
  const picked = [film('B', 2002)];
  assert.deepEqual(poll.fillChoice(pool, picked, 8).map(item => item.title), ['A', 'C', 'D']);
  // A series on the shortlist asks for series first, and falls back when there are none left.
  assert.deepEqual(poll.fillChoice(pool, [{ kind: 'tv', title: 'Other show', year: 2019 }], 8).map(item => item.title), ['Show']);
  assert.deepEqual(poll.fillChoice(pool, [{ kind: 'tv', title: 'Show', year: 2020 }], 8).map(item => item.title), ['A', 'B', 'C']);
  assert.deepEqual(poll.fillChoice([], [], 8), []);
  assert.deepEqual(poll.fillChoice(pool, pool.slice(0, 4), 4), []);
});

test('share links carry the question and the poll link, encoded', () => {
  const links = new Map(poll.shareLinks('https://omnitrackr.xyz/tonight/abc', 'Film & snacks?'));
  assert.equal(links.get('WhatsApp'),
    'https://wa.me/?text=Film%20%26%20snacks%3F%20Vote%20here%3A%20https%3A%2F%2Fomnitrackr.xyz%2Ftonight%2Fabc');
  assert.ok(links.get('Text message').startsWith('sms:?&body=Film%20%26%20snacks%3F'));
  assert.ok(links.get('Email').startsWith('mailto:?subject=Film%20%26%20snacks%3F&body='));
});

// ---------------------------------------------------------------- sign-in return (auth.js)

function auth(draft, storage = new Map()) {
  const local = new Map(draft === undefined ? [] : [[poll.DRAFT_KEY, typeof draft === 'string' ? draft : JSON.stringify(draft)]]);
  const location = { pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz', assign() {}, reload() {} };
  const context = vm.createContext({
    URLSearchParams, AbortController, Date: { now: () => NOW }, location,
    window: { location, history: { replaceState() {} } },
    document: { readyState: 'loading', documentElement: { dataset: {} }, addEventListener() {}, querySelector: () => null,
      getElementById: () => null },
    sessionStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key) },
    localStorage: { getItem: key => local.get(key) ?? null, setItem: (key, value) => local.set(key, value),
      removeItem: key => local.delete(key) },
    fetch: async () => ({ ok: false, status: 401, json: async () => null }),
    setTimeout: () => 0, clearTimeout() {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8'), context);
  return context;
}

test('a shortlist waiting for sign-up brings the new member back to the poll page', () => {
  const options = [film('Heat', 1995), film('Arrival', 2016)];
  assert.equal(auth({ at: NOW - 60000, waiting: true, options }).consumeDiscoverAuthReturn(), '/tonight');
  // Not asked for, too short, a day old, unreadable, or absent: the library as usual.
  assert.equal(auth({ at: NOW - 60000, waiting: false, options }).consumeDiscoverAuthReturn(), '/');
  assert.equal(auth({ at: NOW - 60000, waiting: true, options: options.slice(0, 1) }).consumeDiscoverAuthReturn(), '/');
  assert.equal(auth({ at: NOW - 2 * DAY, waiting: true, options }).consumeDiscoverAuthReturn(), '/');
  assert.equal(auth('{broken').consumeDiscoverAuthReturn(), '/');
  assert.equal(auth().consumeDiscoverAuthReturn(), '/');
});

test('a return the visitor chose still wins over a waiting shortlist', () => {
  const storage = new Map([['omnitrackr_discover_auth_return', JSON.stringify({ path: '/pick', created_at: NOW - 1000 })]]);
  const context = auth({ at: NOW - 60000, waiting: true, options: [film('Heat', 1995), film('Arrival', 2016)] }, storage);
  assert.equal(context.consumeDiscoverAuthReturn(), '/pick');
});
