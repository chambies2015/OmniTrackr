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
