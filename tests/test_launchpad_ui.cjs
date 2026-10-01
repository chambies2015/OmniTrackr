const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');

function setup(dismissed = false) {
  const elements = new Map();
  function makeElement() {
    return {
      hidden: true, children: [], dataset: {}, textContent: '',
      replaceChildren() { this.children = []; },
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); },
      removeAttribute(name) { if (name === 'hidden') this.hidden = false; },
      scrollIntoView() { this.scrolled = true; },
      focus() { this.focused = true; },
    };
  }
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  };
  let opens = 0;
  const context = vm.createContext({
    demoStartGuidance: false,
    document: { getElementById: get, createElement: makeElement },
    isLibraryLaunchpadDismissed: () => dismissed,
    window: { openAccountModal: () => { opens++; } },
  });
  vm.runInContext(source.slice(source.indexOf('function openLaunchpadImport('), source.indexOf('function renderLibraryPulseList(')), context);
  return { context, get, opens: () => opens };
}

test('empty library exposes six existing add paths and discovery/import, not empty insights', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, false);
  assert.equal(get('libraryLaunchpadStarterPaths').hidden, false);
  assert.equal(get('libraryLaunchpadInsights').hidden, true);
  assert.deepEqual(Array.from(get('libraryLaunchpadCategories').children, b => b.dataset.launchpadCategory),
    ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']);
});

test('first save transitions to useful guidance and hides starter paths', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 0 });
  context.renderLibraryLaunchpad({ total_items: 1 });
  assert.match(get('libraryLaunchpadSummary').textContent, /first title is saved/);
  assert.equal(get('libraryLaunchpadStarterPaths').hidden, true);
  assert.equal(get('libraryLaunchpadCategories').hidden, true);
  assert.equal(get('libraryLaunchpadInsights').hidden, false);
});

test('completed introductory steps retire the panel without persisting a dismissal', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 1 });
  context.renderLibraryLaunchpad({ total_items: 3, rated_items: 1, reviewed_items: 1 });
  assert.equal(get('libraryLaunchpad').hidden, true);
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, false);
});

test('dismissed guidance stays hidden on refresh', () => {
  const { context, get } = setup(true);
  get('libraryLaunchpad').hidden = false;
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, true);
});

test('import shortcut opens the existing account importer and focuses its source selector', () => {
  const { context, get, opens } = setup();
  context.openLaunchpadImport();
  assert.equal(opens(), 1);
  assert.equal(get('importStudio').scrolled, true);
  assert.equal(get('importStudioSource').focused, true);
});
