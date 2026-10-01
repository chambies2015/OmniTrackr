const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');

function setup(url = 'https://omnitrackr.xyz/?start=demo', { dismissed = false } = {}) {
  const elements = new Map();
  const actions = [];
  const changes = [];
  const makeElement = () => ({
    hidden: true, children: [], dataset: {}, textContent: '', value: '',
    replaceChildren() { this.children = []; },
    append(...children) { this.children.push(...children); },
    appendChild(child) { this.children.push(child); },
    removeAttribute(name) { if (name === 'hidden') this.hidden = false; },
  });
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  };
  const context = vm.createContext({
    URLSearchParams,
    document: { getElementById: get, createElement: makeElement },
    isLibraryLaunchpadDismissed: () => dismissed,
    QUICK_CAPTURE_CATEGORIES: Object.fromEntries(['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books'].map(key => [key, {}])),
    selectQuickCaptureCategory: category => actions.push(['category', category]),
    openQuickCapture: () => actions.push(['open']),
    fetch: () => { throw new Error('Handoff must not search or save automatically'); },
    authenticatedFetch: () => { throw new Error('Handoff must not write to the library'); },
    window: {
      location: new URL(url),
      history: {
        state: { keep: true },
        replaceState(state, unused, value) {
          changes.push({ state, value });
          context.window.location = new URL(value, context.window.location);
        },
      },
    },
  });
  vm.runInContext(source.slice(source.indexOf('const LAUNCHPAD_DISMISS_KEY'), source.indexOf('function getReturnPromptContext')), context);
  vm.runInContext(source.slice(source.indexOf('function openLaunchpadQuickCapture'), source.indexOf('function openLaunchpadAddItem')), context);
  vm.runInContext(source.slice(source.indexOf('function renderLibraryLaunchpad'), source.indexOf('function renderLibraryPulseList')), context);
  return { context, get, actions, changes };
}

test('demo return adds first-title guidance to the existing launchpad without opening or saving anything', () => {
  const s = setup('https://omnitrackr.xyz/?start=demo&keep=value#other');
  s.get('movieTitle').value = 'Existing unsaved draft';
  s.context.captureDemoStartGuidance();
  s.context.renderLibraryLaunchpad({ total_items: 0 });
  assert.match(s.get('libraryLaunchpadSummary').textContent, /Add Anything.*first real title/);
  assert.match(s.get('libraryLaunchpadSummary').textContent, /demo practice stays separate/);
  assert.equal(s.get('libraryLaunchpad').hidden, false);
  assert.equal(s.get('movieTitle').value, 'Existing unsaved draft');
  assert.deepEqual(s.actions, []);
  assert.equal(s.changes[0].value, '/?keep=value#other');
  assert.equal(s.changes[0].state.keep, true);
});

test('explicit launchpad action opens Add Anything without resetting a draft or submitting a search', () => {
  const s = setup();
  s.get('quickCaptureQuery').value = 'A search draft';
  s.get('bookTitle').value = 'A private book draft';
  s.context.openLaunchpadQuickCapture();
  assert.deepEqual(s.actions, [['open']]);
  assert.equal(s.get('quickCaptureQuery').value, 'A search draft');
  assert.equal(s.get('bookTitle').value, 'A private book draft');
  s.context.openLaunchpadQuickCapture('books');
  assert.deepEqual(s.actions.slice(1), [['category', 'books'], ['open']]);
  assert.equal(s.get('bookTitle').value, 'A private book draft');
});

test('each category choice selects its source before opening Add Anything', () => {
  for (const category of ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']) {
    const s = setup();
    s.context.openLaunchpadQuickCapture(category);
    assert.deepEqual(s.actions, [['category', category], ['open']]);
  }
});

test('existing libraries and dismissed guidance retain their ordinary dashboard', () => {
  const existing = setup();
  existing.context.captureDemoStartGuidance();
  existing.context.renderLibraryLaunchpad({ total_items: 1 });
  assert.match(existing.get('libraryLaunchpadSummary').textContent, /first title is saved/);
  assert.doesNotMatch(existing.get('libraryLaunchpadSummary').textContent, /demo practice/);
  existing.context.renderLibraryLaunchpad({ total_items: 0 });
  assert.doesNotMatch(existing.get('libraryLaunchpadSummary').textContent, /demo practice/);
  const dismissed = setup(undefined, { dismissed: true });
  dismissed.context.captureDemoStartGuidance();
  dismissed.context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(dismissed.get('libraryLaunchpad').hidden, true);
  assert.deepEqual(existing.actions, []);
  assert.deepEqual(dismissed.actions, []);
});

test('review, collection, and recovery destinations take priority without losing their query parameters', () => {
  for (const query of ['next=%2Freviews%2F42%2Fsave%3Fcategory%3Dbook', 'library_category=books&library_item=42',
    'collection=42', 'reset_token=secret', 'token=secret&email_verified=true', 'email_change_token=secret&email_change=true']) {
    const s = setup(`https://omnitrackr.xyz/?start=demo&${query}#keep`);
    s.context.captureDemoStartGuidance();
    s.context.renderLibraryLaunchpad({ total_items: 0 });
    assert.doesNotMatch(s.get('libraryLaunchpadSummary').textContent, /demo practice/, query);
    assert.equal(s.context.window.location.searchParams.has('start'), false, query);
    for (const [key, value] of new URLSearchParams(query)) assert.equal(s.context.window.location.searchParams.get(key), value, query);
    assert.equal(s.context.window.location.hash, '#keep', query);
    assert.deepEqual(s.actions, [], query);
  }
});

test('ordinary, malformed, duplicate, and off-root starts never introduce demo guidance', () => {
  for (const url of ['https://omnitrackr.xyz/', 'https://omnitrackr.xyz/?start=Demo', 'https://omnitrackr.xyz/?start=demo%0A',
    'https://omnitrackr.xyz/?start=demo&start=demo', 'https://omnitrackr.xyz/?start=//evil.example', 'https://omnitrackr.xyz/other?start=demo']) {
    const s = setup(url);
    s.context.captureDemoStartGuidance();
    s.context.renderLibraryLaunchpad({ total_items: 0 });
    assert.doesNotMatch(s.get('libraryLaunchpadSummary').textContent, /demo practice/, url);
    assert.deepEqual(s.actions, [], url);
  }
});
