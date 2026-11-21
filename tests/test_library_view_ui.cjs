// Library view (Nov 20 2026): drawn covers for titles without art and counts on the status chips.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');

const source = require('./helpers/dashboard_source.cjs');

function slice(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, `${startMarker} not found`);
  return source.slice(start, end);
}

function cell() {
  const props = {};
  return { dataset: {}, props, style: { setProperty: (name, value) => { props[name] = value; } } };
}

function drawn(title) {
  const context = vm.createContext({});
  vm.runInContext(slice('const DRAWN_COVER_NARROW', '// Keep Edit visible'), context);
  const target = cell();
  context.drawLibraryCover(target, title);
  return target;
}

test('a drawn cover uses the hue Discover and the title pages give the same title', () => {
  // Expected values are app/explore_art.hue() for these titles.
  for (const [title, hue] of [['Past Lives', 261], ['Perfect Days', 252], ['Neuromancer', 202],
    ['Tomorrow, and Tomorrow, and Tomorrow', 278], ["Frieren: Beyond Journey's End", 213], ['Amélie', 57]]) {
    const target = drawn(title);
    assert.equal(target.props['--x-hue'], String(hue), title);
    assert.equal(target.dataset.coverTitle, title);
  }
});

test('long words and long titles get smaller type', () => {
  const size = title => Number.parseFloat(drawn(title).props['--cover-fs']);
  assert.equal(size('Babel'), 12.5);
  // explore_art.word_width('Neuromancer') is 10.8 letters: 118 / 10.8.
  assert.ok(Math.abs(size('Neuromancer') - 118 / 10.8) < 0.02);
  assert.ok(size('A very long title that keeps going well past the usual length of one') < 9);
  assert.match(drawn('Babel').props['--cover-fs'], /cqi$/);
});

test('a drawn cover only sets attributes, and skips a missing title', () => {
  const target = drawn('   ');
  assert.equal(target.dataset.coverTitle, undefined);
  assert.deepEqual(target.props, {});
  const body = slice('function drawLibraryCover', '// Keep Edit visible');
  assert.ok(!body.includes('innerHTML') && !body.includes('appendChild'));
  const long = drawn('x'.repeat(200)).dataset.coverTitle;
  assert.equal(long.length, 118);
  assert.ok(long.endsWith('…'));
});

function chips(panelData, filters = {}, searchValue = '') {
  const buttons = ['all', 'unfinished', 'finished'].map(value => ({ dataset: { completion: value } }));
  const panel = { dataset: panelData };
  const host = { closest: () => panel, querySelectorAll: () => buttons };
  const context = vm.createContext({
    window: {},
    document: { getElementById: id => (id === 'movieTableFilters' ? host : id === 'movieSearch' ? { value: searchValue } : null) },
    LIBRARY_SEARCH_SOURCES: [{ tab: 'movies', input: 'movieSearch' }],
    libraryPageConfig: () => ['movieTable', 'movieSort', () => {}],
    getLibraryFilters: () => ({ completion: 'all', unrated: false, hasProgress: false, ...filters }),
  });
  vm.runInContext(slice('function syncLibraryFilterCounts', 'window.syncLibraryFilterCounts ='), context);
  context.syncLibraryFilterCounts('movies');
  return buttons.map(button => button.dataset.count);
}

test('status chips show the shelf totals', () => {
  assert.deepEqual(chips({ shelfTotal: '16', shelfFinished: '11' }), ['16', '5', '11']);
});

test('chip counts hide while a search or another filter narrows the view', () => {
  const totals = { shelfTotal: '16', shelfFinished: '11' };
  assert.deepEqual(chips(totals, {}, 'dune'), [undefined, undefined, undefined]);
  assert.deepEqual(chips(totals, { unrated: true }), [undefined, undefined, undefined]);
  assert.deepEqual(chips(totals, { tag: 'cozy' }), [undefined, undefined, undefined]);
  assert.deepEqual(chips(totals, { recommendedBy: 'sam' }), [undefined, undefined, undefined]);
});

test('chip counts stay off until the summary arrives or when it does not add up', () => {
  assert.deepEqual(chips({}), [undefined, undefined, undefined]);
  assert.deepEqual(chips({ shelfTotal: '0', shelfFinished: '0' }), [undefined, undefined, undefined]);
  assert.deepEqual(chips({ shelfTotal: '3', shelfFinished: '5' }), [undefined, undefined, undefined]);
});
