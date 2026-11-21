// The nine "Add" forms on the dashboard used to save a second copy of a title the member already had,
// without a word. confirmNotAlreadyInLibrary() asks once; pressing Add again saves the copy anyway.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

function helpers(fetch) {
  const notices = [];
  const context = vm.createContext({ API_BASE: '', authenticatedFetch: fetch, showNotice: text => notices.push(text) });
  const start = source.indexOf('function libraryTitleKey(');
  const end = source.indexOf("document.getElementById('addMovieForm').onsubmit =", start);
  assert.ok(start > 0 && end > start);
  vm.runInContext(source.slice(start, end), context);
  return { check: context.confirmNotAlreadyInLibrary, year: context.libraryItemYear, notices };
}

const library = items => async () => ({ ok: true, json: async () => items });

test('a title already in the library is flagged once, then the second press goes through', async () => {
  const urls = [];
  const h = helpers(async url => { urls.push(url); return library([{ title: 'Arrival', year: 2016 }])(); });
  const form = { dataset: {} };
  assert.equal(await h.check(form, '/movies/', '  arrival ', 2016, 'movies', null), false);
  assert.deepEqual(h.notices, ['Arrival (2016) is already in your movies. Press Add again if you want a second copy.']);
  assert.equal(urls[0], '/movies/?search=%20%20arrival%20');
  assert.equal(await h.check(form, '/movies/', 'Arrival', 2016, 'movies', null), true);
  assert.equal(urls.length, 1); // the confirmed press doesn't look again
  assert.equal(form.dataset.duplicateOk, undefined);
});

test('a different year, a different title or a lookup failure never blocks the save', async () => {
  const h = helpers(library([{ title: 'Dune', year: 1984 }, { title: 'Dune: Part Two', year: 2024 }]));
  assert.equal(await h.check({ dataset: {} }, '/movies/', 'Dune', 2021, 'movies', null), true);
  assert.equal(await h.check({ dataset: {} }, '/movies/', 'Dune Part', 2024, 'movies', null), true);
  for (const fetch of [async () => { throw new Error('Session expired. Please login again.'); },
    async () => ({ ok: false, json: async () => ({}) }), async () => ({ ok: true, json: async () => ({ detail: 'x' }) })]) {
    assert.equal(await helpers(fetch).check({ dataset: {} }, '/books/', 'Dune', 1965, 'books', null), true);
  }
  assert.deepEqual(h.notices, []);
});

test('forms with their own status line use it, and games match on the release year', async () => {
  const h = helpers(library([{ title: 'God of War', release_date: '2018-04-20T00:00:00' }]));
  const status = { textContent: 'Saving your book…' };
  assert.equal(await h.check({ dataset: {} }, '/video-games/', 'God of War', 2005, 'games', status), true);
  assert.equal(await h.check({ dataset: {} }, '/video-games/', 'God of War', null, 'games', status), false);
  assert.equal(status.textContent, 'God of War (2018) is already in your games. Press Add again if you want a second copy.');
  assert.equal(h.year({ release_date: '2018-04-20T00:00:00' }), 2018);
  assert.equal(h.year({ year: 1999 }), 1999);
  assert.equal(h.year({}), null);
});

test('all nine add forms ask before posting', () => {
  for (const [endpoint, form] of [['movies', "document.getElementById('addMovieForm')"], ['tv-shows', "document.getElementById('addTVShowForm')"],
    ['anime', "document.getElementById('addAnimeForm')"], ['video-games', "document.getElementById('addVideoGameForm')"],
    ['music', "document.getElementById('addMusicForm')"], ['books', 'form'], ['manga', 'form'], ['podcasts', 'form'], ['audiobooks', 'form']]) {
    const post = source.indexOf(`authenticatedFetch(\`\${API_BASE}/${endpoint}/\`, {\n    method: 'POST'`);
    const fallback = post > 0 ? post : source.indexOf(`authenticatedFetch(\`\${API_BASE}/${endpoint}/\`, {\n      method: 'POST'`);
    assert.ok(fallback > 0, endpoint);
    const before = source.slice(fallback - 400, fallback);
    assert.ok(before.includes(`confirmNotAlreadyInLibrary(${form}, '/${endpoint}/', title,`), endpoint);
  }
});
