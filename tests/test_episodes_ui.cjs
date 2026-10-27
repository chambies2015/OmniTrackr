const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/episodes.js'), 'utf8');

function setup() {
  const listeners = new Map();
  const requests = [];
  class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.style = {}; this.hidden = false; this._text = ''; this.className = ''; this.classList = { add: () => {} }; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(child => child.textContent ?? String(child)).join(''); }
    set innerHTML(_) { throw new Error('Episode progress must render text safely.'); }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.children.push(node); }
    replaceChildren(...nodes) { this.children = nodes; this._text = ''; }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener() {}
    closest() { return null; }
  }
  const all = [];
  const context = vm.createContext({
    Promise, console,
    document: {
      createElement: tag => { const node = new Element(tag); all.push(node); return node; },
      addEventListener: (name, callback) => listeners.set(name, callback),
      querySelectorAll: () => all.filter(node => node.dataset.episodePart),
      getElementById: () => null, body: new Element('body'),
    },
    window: { addEventListener() {}, setTimeout: () => 1, clearTimeout() {} },
  });
  vm.runInContext(script, context);
  const api = context.window.OmniEpisodes;
  api.configure({ sessionKey: () => 'account', request: async (url, options) => { requests.push({ url, options }); return { ok: true, status: 200, json: async () => ({}) }; } });
  return { api, Element, requests };
}

const progress = (overrides = {}) => ({ total: 19, watched: 13, percent: 68, season_count: 2,
  current: { season: 2, episode: 4 }, next: { season: 2, episode: 5 }, caught_up: false, revision: 3, ...overrides });

test('library rows show a labelled bar and a one-tap next episode button', () => {
  const { api, Element } = setup();
  const cell = new Element('td');
  api.appendRow(cell, { category: 'tv-shows', id: 7, title: '<b>Severance</b>', episode_progress: progress() });
  const text = cell.textContent;
  assert.match(text, /Watched S2 E4 · 13 of 19/);
  assert.match(text, /\+ S2 E5/);
  const wrap = cell.children[0];
  const bar = wrap.children[0].children[0];
  assert.equal(bar.attributes.role, 'progressbar');
  assert.equal(bar.attributes['aria-valuenow'], '68');
  const next = wrap.children[1].children[0];
  assert.equal(next.dataset.episodeSeason, '2');
  assert.equal(next.dataset.episodeNumber, '5');
  assert.equal(next.dataset.episodeRevision, '3');
  assert.equal(next.attributes['aria-label'], 'Mark S2 E5 of <b>Severance</b> watched');
});

test('finished titles without a place, other categories and missing data render nothing', () => {
  const { api, Element } = setup();
  const cell = new Element('td');
  api.appendRow(cell, { category: 'tv-shows', id: 1, title: 'Done', watched: true, episode_progress: progress({ current: null }) });
  api.appendRow(cell, { category: 'books', id: 2, title: 'Book', episode_progress: progress() });
  api.appendRow(cell, { category: 'anime', id: 3, title: 'No data' });
  assert.equal(cell.children.length, 0);
});

test('labels cover caught up, not started, continuous numbering and specials', () => {
  const { api } = setup();
  assert.equal(api.describe(progress({ caught_up: true, next: null })), 'All caught up · 19 of 19 episodes');
  assert.equal(api.describe(progress({ current: null, watched: 0 })), 'Not started · 19 episodes');
  assert.equal(api.describe(progress({ current: { season: null, episode: 16 }, watched: 16, total: 28 })), 'Watched E16 · 16 of 28');
  assert.equal(api.describe(progress(), true), '13 of 19 episodes');
  assert.equal(api.label(0, 3), 'Special 3');
  assert.equal(api.label(null, 3), 'Episode 3');
});

test('grid arithmetic matches the server', () => {
  const { api } = setup();
  const seasons = [{ number: 1, episodes: 9 }, { number: 2, episodes: 10 }];
  assert.equal(api.absolute(seasons, 2, 4), 13);
  assert.equal(api.absolute(seasons, null, 13), 13);
  assert.equal(api.absolute(seasons, 0, 2), null);
  assert.deepEqual([...api.locate(seasons, 10)], [2, 1]);
  assert.equal(api.locate(seasons, 20), null);
  assert.deepEqual([...api.previousEpisode(seasons, 2, 1)], [1, 9]);
  assert.equal(api.previousEpisode(seasons, 1, 1), null);
});
