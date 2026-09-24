const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/app.js'), 'utf8');

for (const [name, prefix] of [['TV', 'tv'], ['Anime', 'anime']]) {
  test(`${name} edit preserves IMDb and puts privacy and save actions in the correct cells`, () => {
    const row = { cells: Array.from({length: 11}, (_, index) => ({innerHTML: `original-${index}`})) };
    const context = vm.createContext({
      window: {}, editingRowId: null, editingRowElement: null,
      document: {getElementById: () => null}, escapeHtml: String,
      reviewQualityHintHtml: () => '', disableOtherRowButtons: () => {},
    });
    const start = source.indexOf(`window.enable${name}Edit =`);
    vm.runInContext(source.slice(start, source.indexOf(`window.save${name}Edit`, start)), context);
    context.window[`enable${name}Edit`]({
      dataset: {[`${prefix}Id`]: '7', [`${prefix}Title`]: 'Test title', [`${prefix}Year`]: '2024'},
      closest: () => row,
    });
    assert.equal(row.cells[8].innerHTML, 'original-8');
    assert.match(row.cells[9].innerHTML, new RegExp(`edit-${prefix}-review-public`));
    assert.match(row.cells[10].innerHTML, /Save/);
    assert.match(row.cells[10].innerHTML, /Cancel/);
    assert.doesNotMatch(row.cells[10].innerHTML, /Delete/);
  });
}

function collapsibleHarness() {
  const classes = new Set();
  const rotated = new Set();
  const classList = values => ({ contains: key => values.has(key), add: key => values.add(key), remove: key => values.delete(key) });
  const content = { hidden: true, style: {}, classList: classList(classes) };
  const icon = { classList: classList(rotated) };
  const toggle = { dataset: { toggleCollapsible: 'movieForm' }, expanded: 'false', setAttribute(name, value) { if (name === 'aria-expanded') this.expanded = value; } };
  const otherToggle = { dataset: { toggleCollapsible: 'bookForm' }, expanded: 'false', setAttribute(name, value) { if (name === 'aria-expanded') this.expanded = value; } };
  const pending = [];
  const context = vm.createContext({
    window: {},
    document: {
      getElementById: id => id.endsWith('Content') ? content : icon,
      querySelectorAll: () => [toggle, otherToggle],
    },
    setTimeout: callback => pending.push(callback),
  });
  const start = source.indexOf('window.toggleCollapsible =');
  vm.runInContext(source.slice(start, source.indexOf('// Account Management Functions', start)), context);
  return { content, toggle, otherToggle, classes, rotated, pending, activate: () => context.window.toggleCollapsible('movieForm') };
}

test('built-in add forms have native collapsed buttons tied to their content', () => {
  const template = fs.readFileSync(require('node:path').join(__dirname, '../app/templates/index.html'), 'utf8');
  for (const id of ['movieForm', 'tvForm', 'animeForm', 'musicForm', 'bookForm', 'videoGameForm']) {
    const button = template.match(new RegExp(`<button\\b[^>]*data-toggle-collapsible="${id}"[^>]*>`));
    assert.ok(button, `${id} has a keyboard-operable button`);
    assert.match(button[0], /type="button"/);
    assert.match(button[0], /aria-expanded="false"/);
    assert.match(button[0], new RegExp(`aria-controls="${id}Content"`));
    assert.match(template, new RegExp(`<div\\b[^>]*id="${id}Content"[^>]*\\bhidden\\b`));
  }
});

test('add-form expanded state follows opening and closing only its own toggle', () => {
  const h = collapsibleHarness();
  h.activate();
  assert.equal(h.content.hidden, false);
  assert.equal(h.content.style.display, 'block');
  assert.equal(h.toggle.expanded, 'true');
  assert.equal(h.otherToggle.expanded, 'false');
  assert.equal(h.rotated.has('rotated'), true);
  h.activate();
  assert.equal(h.toggle.expanded, 'false');
  assert.equal(h.rotated.has('rotated'), false);
  h.pending.forEach(callback => callback());
  assert.equal(h.content.hidden, true);
  assert.equal(h.content.style.display, 'none');
});

test('reopening during the collapse animation keeps form and toggle expanded', () => {
  const h = collapsibleHarness();
  h.activate();
  h.activate();
  h.activate();
  h.pending.forEach(callback => callback());
  assert.equal(h.toggle.expanded, 'true');
  assert.equal(h.content.hidden, false);
  assert.equal(h.content.style.display, 'block');
  assert.equal(h.classes.has('expanded'), true);
});
