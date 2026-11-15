// Homepage tour tabs and binge calculator demo (public-landing.js, Nov 2026).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/public-landing.js'), 'utf8');

function el(props = {}) {
  const listeners = {};
  const node = {
    attrs: {}, children: [], hidden: false, textContent: '', classes: new Set(), focused: false,
    classList: {add: c => node.classes.add(c), remove: c => node.classes.delete(c)},
    setAttribute(k, v) { node.attrs[k] = String(v); },
    getAttribute(k) { return k in node.attrs ? node.attrs[k] : null; },
    addEventListener(name, fn) { listeners[name] = fn; },
    fire(name, extra = {}) { return listeners[name] && listeners[name]({preventDefault() {}, ...extra}); },
    appendChild(child) { node.children.push(child); node.textContent += child.textContent; return child; },
    focus() { node.focused = true; },
    get offsetWidth() { return 1; },
    ...props,
  };
  return node;
}

function setup() {
  const reported = [];
  const panels = {};
  const tabRow = {scrollWidth: 100, clientWidth: 100};
  const tabs = ['home', 'shelf', 'diary'].map((key, i) => {
    panels['tour-' + key] = el({hidden: i !== 0});
    return el({attrs: {'aria-controls': 'tour-' + key, 'aria-selected': String(i === 0)}, parentNode: tabRow, tabIndex: i ? -1 : 0});
  });
  const tour = el({querySelectorAll: s => (s === '[data-tour-tab]' ? tabs : [])});
  const options = [
    el({value: 'breaking-bad', attrs: {'data-minutes': '2914', 'data-episodes': '62'}}),
    el({value: 'one-piece', attrs: {'data-minutes': '28320', 'data-episodes': '1180'}}),
  ];
  const select = el({options, selectedIndex: 0});
  const paces = [1, 2, 4].map(h => el({attrs: {'data-hours': String(h), 'aria-pressed': String(h === 2)}}));
  const parts = {
    '[data-binge-days]': el(), '[data-binge-days-word]': el(), '[data-binge-detail]': el(),
    '[data-binge-finish]': el({hidden: true}), '[data-binge-link]': el({attrs: {href: '/binge-calculator/breaking-bad'}}),
  };
  const binge = el({
    querySelector: s => (s === 'select' ? select : parts[s] || null),
    querySelectorAll: s => (s === '[data-hours]' ? paces : []),
  });
  const document = {
    addEventListener() {},
    querySelector: s => (s === '[data-tour]' ? tour : s === '[data-binge-demo]' ? binge : null),
    querySelectorAll: () => [],
    getElementById: id => panels[id] || null,
    createTextNode: text => ({textContent: text}),
    createElement: () => el(),
    body: {style: {}},
  };
  const window = {reportFunnelEvent: event => reported.push(event)};
  vm.runInContext(script, vm.createContext({document, window}));
  return {tabs, panels, select, paces, parts, reported};
}

test('the demo fills in days, hours and a finish date on load without counting a use', () => {
  const ui = setup();
  assert.equal(ui.parts['[data-binge-days]'].textContent, '25');
  assert.equal(ui.parts['[data-binge-days-word]'].textContent, 'days');
  assert.equal(ui.parts['[data-binge-detail]'].textContent, '62 episodes, about 48 hours 34 min in all.');
  assert.equal(ui.parts['[data-binge-finish]'].hidden, false);
  assert.match(ui.parts['[data-binge-finish]'].textContent, /^Start today and you finish on .+\.$/);
  assert.deepEqual(ui.reported, []);
});

test('changing the pace or series updates the result, link and counts once', () => {
  const ui = setup();
  ui.paces[2].fire('click');
  assert.equal(ui.paces[2].getAttribute('aria-pressed'), 'true');
  assert.equal(ui.paces[1].getAttribute('aria-pressed'), 'false');
  assert.equal(ui.parts['[data-binge-days]'].textContent, '13');
  ui.select.selectedIndex = 1;
  ui.select.fire('change');
  assert.equal(ui.parts['[data-binge-days]'].textContent, '118');
  assert.equal(ui.parts['[data-binge-detail]'].textContent, '1,180 episodes, about 472 hours in all.');
  assert.equal(ui.parts['[data-binge-link]'].getAttribute('href'), '/binge-calculator/one-piece');
  assert.deepEqual(ui.reported, ['home_binge_demo_used']);
});

test('tour tabs show one panel at a time and arrow keys move between them', () => {
  const ui = setup();
  ui.tabs[1].fire('click');
  assert.equal(ui.panels['tour-shelf'].hidden, false);
  assert.equal(ui.panels['tour-home'].hidden, true);
  assert.equal(ui.tabs[1].getAttribute('aria-selected'), 'true');
  assert.equal(ui.tabs[1].tabIndex, 0);
  assert.equal(ui.tabs[0].tabIndex, -1);
  ui.tabs[1].fire('keydown', {key: 'ArrowRight'});
  assert.equal(ui.panels['tour-diary'].hidden, false);
  assert.equal(ui.tabs[2].focused, true);
  ui.tabs[2].fire('keydown', {key: 'ArrowRight'});
  assert.equal(ui.panels['tour-home'].hidden, false);
  assert.deepEqual(ui.reported, ['home_tour_opened']);
});

test('the guide link only ever takes a guide slug', () => {
  const ui = setup();
  ui.select.options[1].value = 'javascript:alert(1)';
  ui.select.selectedIndex = 1;
  ui.select.fire('change');
  assert.equal(ui.parts['[data-binge-link]'].getAttribute('href'), '/binge-calculator/breaking-bad');
});
