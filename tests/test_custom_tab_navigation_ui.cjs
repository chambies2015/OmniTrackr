const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');

function harness(customTabs) {
  const element = (name, tabName, active = false) => {
    const classes = new Set(active ? ['active'] : []);
    return {
      textContent: name, dataset: { switchTab: tabName },
      classList: { add: value => classes.add(value), remove: value => classes.delete(value), contains: value => classes.has(value) },
    };
  };
  const buttons = [
    element('Movies', 'movies', true), element('Books', 'books'), element('Statistics', 'statistics'),
    ...customTabs.map(tab => element(tab.name, `custom-${tab.id}`)),
  ];
  const contents = new Map(buttons.map(button => [
    `${button.dataset.switchTab}-tab`, element('', '', button.dataset.switchTab === 'movies'),
  ]));
  const loaded = [];
  const fallback = [];
  let navigations = 0;
  const context = vm.createContext({
    customTabs, currentTab: 'movies',
    window: { switchTab: name => { fallback.push(name); return 'built-in'; }, OmniProgress: { navigate: () => { navigations += 1; } } },
    loadCustomTabItems: tab => loaded.push(tab.id),
    document: {
      querySelectorAll: selector => {
        if (selector === '.tab') return buttons;
        if (selector === '.tab-content') return [...contents.values()];
        throw new Error(`Unexpected selector: ${selector}`);
      },
      getElementById: id => contents.get(id) || null,
    },
  });
  const lookup = source.indexOf('function getTabButton(');
  vm.runInContext(source.slice(lookup, source.indexOf('\n}', lookup) + 2), context);
  const setup = source.indexOf('function setupCustomTabSwitching(');
  vm.runInContext(source.slice(setup, source.indexOf('\n}', setup) + 2), context);
  context.setupCustomTabSwitching();
  return { context, buttons, contents, loaded, fallback, navigations: () => navigations };
}

for (const name of ['Movies', 'Books', 'Statistics']) {
  test(`custom library named ${name} activates its own tab instead of the built-in label`, () => {
    const h = harness([{ id: 7, name }]);
    h.context.window.switchTab('custom-7');
    assert.deepEqual(h.buttons.filter(button => button.classList.contains('active')).map(button => button.dataset.switchTab), ['custom-7']);
    assert.deepEqual([...h.contents].filter(([, content]) => content.classList.contains('active')).map(([id]) => id), ['custom-7-tab']);
    assert.equal(h.context.currentTab, 'custom-7');
    assert.deepEqual(h.loaded, [7]);
    assert.equal(h.navigations(), 1);
    assert.deepEqual(h.fallback, []);
  });
}

test('custom libraries with the same display name are selected by their stable ID', () => {
  const h = harness([{ id: 7, name: 'Favorites' }, { id: 8, name: 'Favorites' }]);
  h.context.window.switchTab('custom-8');
  assert.deepEqual(h.buttons.filter(button => button.classList.contains('active')).map(button => button.dataset.switchTab), ['custom-8']);
  assert.deepEqual(h.loaded, [8]);
});

test('built-in and unknown custom destinations continue through the original switcher', () => {
  const h = harness([{ id: 7, name: 'Movies' }]);
  assert.equal(h.context.window.switchTab('books'), 'built-in');
  assert.equal(h.context.window.switchTab('custom-99'), 'built-in');
  assert.deepEqual(h.fallback, ['books', 'custom-99']);
  assert.deepEqual(h.loaded, []);
});
