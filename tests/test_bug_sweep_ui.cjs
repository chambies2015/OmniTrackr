// UI regressions from the September 2026 bug sweep: safe RAWG links, Escape for
// every dialog, computed visibility checks, and the friend music/books shelves.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');

function slice(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0 && end > start, `${startMarker} is present`);
  return source.slice(start, end);
}

const escapeSource = slice('function escapeHtml(str) {', 'function normalizeLibrarySearchText(');
const shownSource = slice('function isElementShown(element) {', 'function isCurrentQuickCaptureSearch(');
const escapeKeySource = slice('function closeTopmostModalOverlay(event) {', '// ====');
const shelfSource = slice('function renderFriendShelf(', 'window.loadFriendStatistics = ');
const errorSource = slice('function showFriendListError(', 'window.openFriendProfile = ');

function makeElement(id, { display = '', hidden = false } = {}) {
  return {
    id, hidden, innerHTML: '', value: '', clicks: 0, children: [],
    style: { display }, computedDisplay: display || 'block',
    querySelector(selector) {
      return this.children.find(child => selector === '[data-action^="close-"]' && child.action?.startsWith('close-')) || null;
    },
    click() { this.clicks += 1; },
  };
}

function context(elements = []) {
  const byId = new Map(elements.map(element => [element.id, element]));
  const ctx = vm.createContext({
    URL,
    console,
    window: {
      location: { origin: 'https://omnitrackr.xyz' },
      getComputedStyle: element => ({ display: element.computedDisplay }),
    },
    document: {
      getElementById: id => byId.get(id) || null,
      querySelectorAll: selector => (selector === '.modal-overlay' ? elements.filter(element => element.overlay) : []),
    },
  });
  vm.runInContext(`${escapeSource}\n${shownSource}\n${escapeKeySource}\n${errorSource}\n${shelfSource}`, ctx);
  return ctx;
}

test('safeHttpUrl keeps http(s) links and drops script or data URLs', () => {
  const ctx = context();
  assert.equal(ctx.safeHttpUrl('https://rawg.io/games/hades'), 'https://rawg.io/games/hades');
  assert.equal(ctx.safeHttpUrl('http://example.com/a?b=1'), 'http://example.com/a?b=1');
  assert.equal(ctx.safeHttpUrl('javascript:alert(1)'), '');
  assert.equal(ctx.safeHttpUrl('data:text/html,<b>x</b>'), '');
  assert.equal(ctx.safeHttpUrl(''), '');
  assert.equal(ctx.safeHttpUrl(null), '');
  // Quotes are percent-encoded, so the value cannot break out of an attribute.
  assert.ok(!ctx.safeHttpUrl('https://rawg.io/games/x"><b>').includes('"'));
});

test('isElementShown trusts computed style because template display styles become CSP classes', () => {
  const ctx = context();
  const closedByClass = makeElement('a');
  closedByClass.computedDisplay = 'none';
  const openByScript = makeElement('b', { display: 'flex' });
  const hiddenAttr = makeElement('c', { hidden: true });
  assert.equal(closedByClass.style.display, '', 'inline style is empty even though it is hidden');
  assert.equal(ctx.isElementShown(closedByClass), false);
  assert.equal(ctx.isElementShown(openByScript), true);
  assert.equal(ctx.isElementShown(hiddenAttr), false);
  assert.equal(ctx.isElementShown(null), false);
});

test('Escape closes the topmost open dialog through its own close control', () => {
  const closed = makeElement('closedModal');
  closed.overlay = true;
  closed.computedDisplay = 'none';
  closed.children.push(makeElement('closedX'));
  closed.children[0].action = 'close-closed';
  const lower = makeElement('accountModal', { display: 'flex' });
  lower.overlay = true;
  const lowerClose = makeElement('accountX');
  lowerClose.action = 'close-account-modal';
  lower.children.push(lowerClose);
  const top = makeElement('collectionPickerModal', { display: 'flex' });
  top.overlay = true;
  const topClose = makeElement('pickerX');
  topClose.action = 'close-collection-picker';
  top.children.push(topClose);
  const ctx = context([closed, lower, top]);

  let prevented = 0;
  ctx.closeTopmostModalOverlay({ preventDefault() { prevented += 1; } });
  assert.equal(topClose.clicks, 1);
  assert.equal(lowerClose.clicks, 0);
  assert.equal(closed.children[0].clicks, 0);
  assert.equal(prevented, 1);
});

test('Escape does nothing when no dialog is open', () => {
  const closed = makeElement('m');
  closed.overlay = true;
  closed.computedDisplay = 'none';
  const ctx = context([closed]);
  let prevented = false;
  ctx.closeTopmostModalOverlay({ preventDefault() { prevented = true; } });
  assert.equal(prevented, false);
});

test('friend music and book shelves render escaped cards and filter by creator', () => {
  const container = makeElement('friendMusicListContainer');
  const search = makeElement('friendMusicSearch');
  const ctx = context([container, search]);
  const albums = [
    { title: 'Kid A <img src=x>', artist: 'Radiohead', year: 2000, genre: 'Rock', rating: 9.5, listened: true, review: '<b>wow</b>' },
    { title: 'Blue', artist: 'Joni Mitchell', year: 1971, listened: false },
  ];
  ctx.renderFriendShelf('friendMusicListContainer', albums, 'No music yet', vm.runInContext('describeFriendAlbum', ctx));
  assert.match(container.innerHTML, /Kid A &lt;img src=x&gt;/);
  assert.match(container.innerHTML, /&lt;b&gt;wow&lt;\/b&gt;/);
  assert.match(container.innerHTML, /Artist: Radiohead/);
  assert.match(container.innerHTML, /9\.5\/10/);
  assert.match(container.innerHTML, /Not Listened/);
  assert.doesNotMatch(container.innerHTML, /<img/);

  search.value = 'JONI';
  const filtered = ctx.filterFriendShelf(albums, 'friendMusicSearch', ['title', 'artist']);
  assert.deepEqual(filtered.map(album => album.title), ['Blue']);
  search.value = '';
  assert.equal(ctx.filterFriendShelf(albums, 'friendMusicSearch', ['title']).length, 2);

  ctx.renderFriendShelf('friendMusicListContainer', [], 'No music found', vm.runInContext('describeFriendAlbum', ctx));
  assert.match(container.innerHTML, /No music found/);
});

test('book shelf labels authors and read status', () => {
  const container = makeElement('friendBooksListContainer');
  const ctx = context([container]);
  ctx.renderFriendShelf('friendBooksListContainer', [{ title: 'Dune', author: 'Frank Herbert', read: true }], 'No books yet', vm.runInContext('describeFriendBook', ctx));
  assert.match(container.innerHTML, /Author: Frank Herbert/);
  assert.match(container.innerHTML, />Read</);
});

test('friend list errors are escaped and keep the search box by writing to the list container', () => {
  const container = makeElement('friendMoviesListContainer');
  const ctx = context([container]);
  ctx.showFriendListError('friendMoviesListContainer', '<i>private</i>', 'Failed');
  assert.equal(container.innerHTML, '<p class="error-message">&lt;i&gt;private&lt;/i&gt;</p>');
  ctx.showFriendListError('friendMoviesListContainer', '', 'Failed to load movies');
  assert.match(container.innerHTML, /Failed to load movies/);
  assert.doesNotThrow(() => ctx.showFriendListError('missing', 'x', 'y'));
  // The old code replaced the whole list (search box included) with the error.
  assert.ok(!source.includes("document.getElementById('moviesList').innerHTML"));
});
