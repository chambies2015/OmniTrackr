// Nov 20 2026 evening sweep (after #264-#266): the Shelf ••• menu opens clear of the
// phone dock, quick saves ask for the shelf numbers once, and an older answer never
// replaces a newer one.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const vm = require('node:vm');

const source = require('./helpers/dashboard_source.cjs');

// ---------------------------------------------------------------- row menu placement

function placeMenu({ summaryTop, dockTop = null, innerHeight = 844, panelHeight = 300 }) {
  const start = source.indexOf('function groupRowActions(cell) {');
  const end = source.indexOf("\n['scroll', 'resize']", start);
  assert.ok(start > 0 && end > start);
  class El {
    constructor(tag, className = '') {
      this.tagName = tag.toUpperCase(); this.className = className; this.children = []; this.parent = null;
      this.listeners = {}; this.style = {}; this.offsetWidth = 182; this.offsetHeight = panelHeight;
    }
    matches(selector) { return selector === 'button.action-btn' && this.className.split(' ').includes('action-btn'); }
    querySelector() { return null; }
    appendChild(child) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = this; this.children.push(child); return child; }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    insertBefore(child, ref) { child.parent = this; this.children.splice(this.children.indexOf(ref), 0, child); return child; }
    setAttribute() {}
    addEventListener(name, fn) { this.listeners[name] = fn; }
    getBoundingClientRect() { return { top: summaryTop, bottom: summaryTop + 36, right: 350, left: 314 }; }
  }
  const dock = dockTop === null ? null : { getBoundingClientRect: () => ({ top: dockTop, height: innerHeight - dockTop }) };
  const context = vm.createContext({
    document: { createElement: tag => new El(tag), getElementById: id => (id === 'appDock' ? dock : null) },
    window: { innerWidth: 390, innerHeight },
  });
  vm.runInContext(source.slice(start, end), context);
  const cell = new El('td');
  ['action-btn edit-movie-btn', 'action-btn next', 'action-btn delete-movie-btn'].forEach(cls => cell.appendChild(new El('button', cls)));
  context.groupRowActions(cell);
  const menu = cell.children[0].children[1];
  menu.open = true;
  menu.listeners.toggle();
  return { top: Number.parseFloat(menu.children[1].style.top), summaryTop };
}

test('the ••• menu opens upwards before it would slide under the phone dock', () => {
  // Below the button the 300 px menu would end at 460 + 36 + 6 + 300 = 802: on screen (844),
  // but under the dock that starts at 774.
  const phone = placeMenu({ summaryTop: 460, dockTop: 774 });
  assert.equal(phone.top, 460 - 300 - 6, 'opens above the ••• button');
  // Same spot with no dock (desktop): it fits below the button.
  assert.equal(placeMenu({ summaryTop: 460, dockTop: null }).top, 460 + 36 + 6);
  // A dock that is off screen (hidden) does not count.
  assert.equal(placeMenu({ summaryTop: 460, dockTop: 844 }).top, 460 + 36 + 6);
  // Plenty of room above the dock: still opens below.
  assert.equal(placeMenu({ summaryTop: 100, dockTop: 774 }).top, 100 + 36 + 6);
});

// ---------------------------------------------------------------- home-hero.js refreshes

function hero() {
  const pending = [];
  const section = { hidden: true };
  global.document = {
    readyState: 'loading',
    getElementById: id => (id === 'homeHero' ? section : null),
    createElement: () => ({}),
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener() {},
  };
  global.window = { addEventListener() {}, setTimeout, clearTimeout };
  global.hasStoredAuth = () => true;
  global.fetch = () => new Promise(resolve => pending.push(resolve));
  delete require.cache[require.resolve('../app/static/home-hero.js')];
  const module = require(path.join(__dirname, '../app/static/home-hero.js'));
  return { module, pending, answer: (index, data) => pending[index]({ ok: true, json: async () => data }) };
}

test('an older shelf summary arriving late never replaces a newer one', async () => {
  const { module, pending, answer } = hero();
  const shown = [];
  const first = module.refresh();
  const second = module.refresh();
  assert.equal(pending.length, 2);
  answer(1, { stamp: 'new', libraries: [] });
  await second;
  shown.push(module.state.data && module.state.data.stamp);
  answer(0, { stamp: 'old', libraries: [] });
  await first;
  shown.push(module.state.data && module.state.data.stamp);
  assert.deepEqual(shown, ['new', 'new']);
  delete global.fetch; delete global.hasStoredAuth;
});

test('refreshSoon folds several quick saves into one request', async () => {
  const { module, pending } = hero();
  module.refreshSoon();
  module.refreshSoon();
  module.refreshSoon();
  assert.equal(pending.length, 0, 'waits before asking');
  await new Promise(resolve => setTimeout(resolve, 700));
  assert.equal(pending.length, 1);
  delete global.fetch; delete global.hasStoredAuth;
});
