// Sparse imported records and public-review saves must remain readable/editable.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const categories = [
  {name: 'Movie', loader: 'Movies', table: 'movieTable', prefix: 'movie', end: 'function displayMoviePoster(', creator: 'director', yearCell: 3, completion: 'watched'},
  {name: 'TV', loader: 'TVShows', table: 'tvShowTable', prefix: 'tv', end: '// Anime functions', yearCell: 2, completion: 'watched'},
  {name: 'Anime', loader: 'Anime', table: 'animeTable', prefix: 'anime', end: 'function displayAnimePoster(', yearCell: 2, completion: 'watched'},
  {name: 'Music', loader: 'Music', table: 'musicTable', prefix: 'music', end: 'function displayMusicPoster(', creator: 'artist', yearCell: 3, completion: 'listened'},
  {name: 'Book', loader: 'Books', table: 'bookTable', prefix: 'book', end: 'function displayBookPoster(', creator: 'author', yearCell: 3, completion: 'read'},
];
const decode = text => text.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

function setup(category, item) {
  const rows = [];
  const requests = [];
  const tbody = {innerHTML: '', appendChild: row => rows.push(row)};
  const context = vm.createContext({
    API_BASE: '', window: {}, editingRowId: null, editingRowElement: null,
    encodeURIComponent, parseFloat, parseInt,
    document: {
      getElementById: id => id.startsWith('edit-') ? null : {value: '', textContent: ''},
      querySelector: selector => selector === `#${category.table} tbody` ? tbody : null,
      createElement: () => ({innerHTML: '', cells: Array.from({length: 11}, () => ({innerHTML: ''}))}),
    },
    fetchLibraryPage: async url => {
      requests.push(url);
      return {ok: true, total: 1, json: async () => [item]};
    },
    authenticatedFetch: () => {throw Error('Rendering or starting an edit must not write');},
    getReviewCellContent: value => value || '',
    reviewQualityHintHtml: () => '', disableOtherRowButtons() {},
    displayMoviePoster() {}, displayTVPoster() {}, displayAnimePoster() {}, displayMusicPoster() {}, displayBookPoster() {},
    fetchMoviePoster() {}, fetchTVPoster() {}, fetchAnimePoster() {}, fetchMusicMetadata() {}, fetchBookMetadata() {},
  });
  context[`isLoading${category.loader}`] = false;
  vm.runInContext(source.slice(source.indexOf('function escapeHtml('), source.indexOf('function normalizeLibrarySearchText(')), context);
  const start = source.indexOf(`async function load${category.loader}(`);
  vm.runInContext(source.slice(start, source.indexOf(category.end, start)), context);
  vm.runInContext(source.slice(source.indexOf(`window.enable${category.name}Edit =`), source.indexOf(`window.save${category.name}Edit =`)), context);
  return {context, rows, requests};
}

function editButton(row, prefix) {
  const markup = row.innerHTML.match(new RegExp(`<button class="action-btn edit-${prefix}-btn"[^>]*>`))[0];
  const dataset = {};
  for (const [, key, value] of markup.matchAll(/data-([a-z-]+)="([^"]*)"/g)) {
    dataset[key.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = decode(value);
  }
  return {dataset, closest: () => row};
}

test('null or missing creator/year render blank and open blank edit fields without changing personal data', async () => {
  for (const category of categories) {
    for (const missing of [null, undefined]) {
      const item = {id: 7, title: 'My saved title', year: missing, rating: 9.2, review: 'My private opinion', review_public: false,
        [category.completion]: true, seasons: missing, episodes: missing, genre: missing};
      if (category.creator) item[category.creator] = missing;
      const before = structuredClone(item);
      const s = setup(category, item);
      await s.context[`load${category.loader}`]();
      const row = s.rows[0];
      assert.ok(row, category.name);
      assert.doesNotMatch(row.innerHTML, /\b(?:null|undefined|NaN)\b/, category.name);
      assert.match(row.innerHTML, /9\.2\/10/);
      assert.match(row.innerHTML, /My private opinion/);
      const button = editButton(row, category.prefix);
      assert.equal(button.dataset[`${category.prefix}Year`], '', category.name);
      if (category.creator) assert.equal(button.dataset[`${category.prefix}${category.creator[0].toUpperCase()}${category.creator.slice(1)}`], '', category.name);
      s.context.window[`enable${category.name}Edit`](button);
      assert.match(row.cells[category.yearCell].innerHTML, /value=""/, category.name);
      assert.doesNotMatch(row.cells.map(cell => cell.innerHTML).join(''), /\b(?:null|undefined|NaN)\b/, category.name);
      if (category.creator) assert.match(row.cells[2].innerHTML, /value=""/, category.name);
      assert.deepEqual(item, before, `${category.name}: rendering and edit prefilling preserve the source record`);
      assert.equal(s.requests.length, 1, `${category.name}: only the library read was needed`);
    }
  }
});

test('known creators and years retain their values, escaped through display, data attributes, and edit prefilling', async () => {
  for (const category of categories) {
    const item = {id: 7, title: 'Known title', year: 2024, rating: null, review: null, review_public: false, [category.completion]: false};
    if (category.creator) item[category.creator] = 'A "Creator" & Co';
    const s = setup(category, item);
    await s.context[`load${category.loader}`]();
    const row = s.rows[0];
    const button = editButton(row, category.prefix);
    assert.equal(button.dataset[`${category.prefix}Year`], '2024');
    s.context.window[`enable${category.name}Edit`](button);
    assert.match(row.cells[category.yearCell].innerHTML, /value="2024"/);
    if (category.creator) assert.match(row.cells[2].innerHTML, /value="A &quot;Creator&quot; &amp; Co"/);
  }
});
