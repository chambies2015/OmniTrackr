// "Draw from your backlog" on the home screen (backlog-draw.js): night words, night choices, rendering states.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = '';
    this.dataset = {}; this.attributes = {}; this.listeners = {}; this.style = { setProperty() {} };
    this.classList = { add() {}, remove() {} };
  }
  appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelectorAll() { return []; }
  scrollIntoView() {}
  get text() { return [this.textContent, ...this.children.map(child => child.text)].join(' ').replace(/\s+/g, ' ').trim(); }
  find(predicate) {
    if (predicate(this)) return this;
    for (const child of this.children) { const hit = child.find(predicate); if (hit) return hit; }
    return null;
  }
}

function setup(storage = {}) {
  const ids = ['backlogDraw', 'backlogDrawEyebrow', 'backlogDrawTitle', 'backlogDrawSummary', 'backlogDrawHide',
    'backlogDrawBody', 'backlogDrawStatus', 'todaysPick'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  nodes.backlogDraw.hidden = true;
  global.document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: tag => new Node(tag),
    addEventListener() {},
  };
  global.localStorage = {
    getItem: key => (key in storage ? storage[key] : null),
    setItem: (key, value) => { storage[key] = String(value); },
  };
  global.window = { location: { hash: '' }, requestAnimationFrame: fn => fn(), setTimeout, clearTimeout };
  global.IntersectionObserver = undefined;
  global.fetch = async () => ({ ok: true, json: async () => ({}) });
  global.hasStoredAuth = () => true;
  delete require.cache[require.resolve('../app/static/backlog-draw.js')];
  const module = require(path.join(__dirname, '../app/static/backlog-draw.js'));
  return { module, nodes };
}

test('night words and choices come from the member\'s own today', () => {
  const { module } = setup();
  assert.equal(module.addDays('2026-11-30', 1), '2026-12-01');
  assert.equal(module.nightWords('2026-11-18', '2026-11-18'), 'Tonight');
  assert.equal(module.nightWords('2026-11-19', '2026-11-18'), 'Tomorrow');
  assert.equal(module.nightWords('2026-11-20', '2026-11-18'), 'Friday');
  // Wednesday: tonight, tomorrow, then the weekend.
  assert.deepEqual(module.nightChoices('2026-11-18'), ['2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22']);
  // Monday: tonight, tomorrow, and the weekend days still inside the week.
  assert.deepEqual(module.nightChoices('2026-11-16'), ['2026-11-16', '2026-11-17', '2026-11-20', '2026-11-21', '2026-11-22']);
  // Thursday: Sunday is the last day of the week ahead, and Monday fills the fourth chip.
  assert.deepEqual(module.nightChoices('2026-11-19'), ['2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22']);
  assert.equal(module.hourWords(18), '6 pm');
});

test('deal state shows card backs and hides Today\'s pick; no card hides the section', () => {
  const { module, nodes } = setup();
  module.render({ state: 'deal', today: '2026-11-18', total: 14 });
  assert.equal(nodes.backlogDraw.hidden, false);
  assert.equal(nodes.todaysPick.attributes.hidden, '');
  assert.match(nodes.backlogDrawSummary.textContent, /14 titles you saved are still waiting/);
  assert.ok(nodes.backlogDrawBody.find(node => node.textContent === 'Deal three'));
  assert.equal(module.active(), true);
  module.render(null);
  assert.equal(nodes.backlogDraw.hidden, true);
  assert.equal(module.active(), false);
});

test('a hidden card stays hidden in the deal state but a kept card always shows', () => {
  const storage = { omnitrackr_backlog_draw_hidden: JSON.stringify({ me: Date.now() + 60000 }) };
  const { module, nodes } = setup(storage);
  module.render({ state: 'deal', today: '2026-11-18', total: 5 });
  assert.equal(nodes.backlogDraw.hidden, true);
  const pick = { category: 'movies', id: 3, title: 'Dune', label: 'Movie', year: 2021, length: '2h 35m', waited: 'Waiting 5 weeks',
    verb: 'watch', finish_words: 'Watched it', url: '/titles/movie/dune-2021', image: null };
  module.render({ state: 'planned', today: '2026-11-18', pick, night: null, reminder: null, email_offer: true, remind_hour: 18 });
  assert.equal(nodes.backlogDraw.hidden, false);
  assert.equal(nodes.backlogDrawTitle.textContent, 'You kept Dune');
  assert.ok(nodes.backlogDrawBody.find(node => node.textContent === 'Tomorrow'));
  module.render({ state: 'after', today: '2026-11-19', pick, night: '2026-11-18', reminder: null });
  assert.equal(nodes.backlogDrawTitle.textContent, 'How was Dune?');
  assert.ok(nodes.backlogDrawBody.find(node => node.textContent === 'Didn’t get to it'));
  // Member-typed titles only ever go in as text.
  const sneaky = { ...pick, title: '<img src=x onerror=alert(1)>' };
  module.render({ state: 'after', today: '2026-11-19', pick: sneaky, night: '2026-11-18', reminder: null });
  assert.ok(nodes.backlogDrawBody.find(node => node.textContent === sneaky.title && node.tagName === 'a'));
});
