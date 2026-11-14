// Episode scores and notes in the episode guide (episodes.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/episodes.js'), 'utf8');

const camel = name => name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

function setup({ mode = 'watch', payload }) {
  const listeners = new Map();
  const requests = [];
  const all = [];
  const storage = new Map([['omnitrackr.episodeGuideMode', mode]]);
  class Element {
    constructor(tag) {
      this.tagName = tag; this.children = []; this.parent = null; this.dataset = {}; this.attributes = {}; this.style = {};
      this.hidden = false; this._text = ''; this.className = ''; this.listeners = {}; this.value = ''; this.checked = false;
      const classes = new Set();
      this.classList = { add: name => classes.add(name), contains: name => classes.has(name) || this.className.split(' ').includes(name) };
    }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(child => (typeof child === 'string' ? child : child.textContent)).join(''); }
    set innerHTML(_) { throw new Error('Episode notes must render text safely.'); }
    adopt(nodes) { nodes.forEach(node => { if (node && typeof node === 'object') node.parent = this; }); }
    append(...nodes) { this.adopt(nodes); this.children.push(...nodes); }
    appendChild(node) { this.adopt([node]); this.children.push(node); return node; }
    replaceChildren(...nodes) { this.adopt(nodes); this.children = nodes; this._text = ''; }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    showModal() { this.open = true; }
    close() { this.open = false; }
    focus() {}
    matches(selector) {
      const match = selector.match(/^\[data-([a-z-]+)\]$/);
      return Boolean(match) && this.dataset[camel(match[1])] !== undefined;
    }
    closest(selector) { for (let node = this; node; node = node.parent) if (node.matches?.(selector)) return node; return null; }
    find(test) { const out = []; const walk = node => { if (!node || typeof node !== 'object') return; if (test(node)) out.push(node); node.children.forEach(walk); }; walk(this); return out; }
  }
  const body = new Element('body');
  const context = vm.createContext({
    Promise, console, Number, Math, Set, Map,
    document: {
      createElement: tag => { const node = new Element(tag); all.push(node); return node; },
      addEventListener: (name, callback) => listeners.set(name, callback),
      querySelectorAll: () => all.filter(node => node.dataset.episodePart),
      getElementById: id => body.find(node => node.id === id)[0] || null,
      body, activeElement: null,
    },
    window: {
      addEventListener() {}, setTimeout: () => 1, clearTimeout() {},
      localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    },
  });
  vm.runInContext(script, context);
  const api = context.window.OmniEpisodes;
  let reply = payload;
  api.configure({
    sessionKey: () => 'account',
    request: async (url, options = {}) => {
      requests.push({ url, method: options.method, body: options.body ? JSON.parse(options.body) : null });
      return { ok: true, status: 200, json: async () => reply };
    },
  });
  const dialog = () => body.find(node => node.id === 'episodeDialog')[0];
  const click = async target => { dialog().listeners.click({ target }); await new Promise(resolve => setImmediate(resolve)); await new Promise(resolve => setImmediate(resolve)); };
  return { api, body, requests, dialog, click, storage, listeners, setReply: next => { reply = next; } };
}

const guidePayload = (notes = []) => ({
  category: 'tv-shows', item_id: 7, title: 'Severance', revision: 3, checkpoint: null,
  layout: { seasons: [{ number: 1, episodes: 9 }, { number: 2, episodes: 10 }], source: null },
  episodes: { total: 19, watched: 13, percent: 68, season_count: 2, current: { season: 2, episode: 4 }, next: { season: 2, episode: 5 }, caught_up: false, revision: 3 },
  episode_notes: notes,
  episode_note_summary: { rated: notes.filter(n => n.rating).length, noted: notes.filter(n => n.note).length, average: 9.5 },
});
const flush = () => new Promise(resolve => setImmediate(resolve));

test('rate mode shows scores on cells, season averages and hides spoiler notes', async () => {
  const notes = [
    { season: 1, episode: 7, rating: 10, note: 'Defiant Jazz', spoiler: false },
    { season: 1, episode: 9, rating: 9, note: '<b>Helly is Helena</b>', spoiler: true },
    { season: 0, episode: 1, rating: 8, note: null, spoiler: false },
  ];
  const { api, body } = setup({ mode: 'rate', payload: guidePayload(notes) });
  api.open('tv-shows', 7, 'Severance');
  await flush(); await flush();
  const text = body.textContent;
  assert.match(text, /You've rated 3 episodes, 9\.5\/10 on average · 2 notes\./);
  assert.match(text, /Your top episodes/);
  assert.match(text, /9\.5 avg/);
  assert.match(text, /Defiant Jazz/);
  assert.doesNotMatch(text, /Helly is Helena/, 'spoiler notes stay hidden until tapped');
  assert.match(text, /Spoiler note · show it/);
  assert.match(text, /Specials and other episodes you rated/);
  const cell = body.find(node => node.dataset.guideSeason === '1' && node.dataset.guideEpisode === '7')[0];
  assert.equal(cell.attributes['aria-label'], 'Rate Season 1, episode 7, watched, you rated it 10 out of 10, has a note');
  assert.equal(cell.attributes['aria-pressed'], undefined, 'rate mode cells are not watched toggles');
});

test('tapping a spoiler note reveals it as text', async () => {
  const notes = [{ season: 1, episode: 9, rating: 9, note: 'Helly is Helena', spoiler: true }];
  const harness = setup({ mode: 'rate', payload: guidePayload(notes) });
  harness.api.open('tv-shows', 7, 'Severance');
  await flush(); await flush();
  const reveal = harness.body.find(node => node.dataset.guideReveal === 's1e9')[0];
  await harness.click(reveal);
  assert.match(harness.body.textContent, /Helly is Helena/);
});

test('in rate mode a cell opens the editor and a score saves straight away', async () => {
  const harness = setup({ mode: 'rate', payload: guidePayload() });
  harness.api.open('tv-shows', 7, 'Severance');
  await flush(); await flush();
  const cell = harness.body.find(node => node.dataset.guideSeason === '2' && node.dataset.guideEpisode === '3')[0];
  await harness.click(cell);
  assert.match(harness.body.textContent, /S2 E3/);
  assert.match(harness.body.textContent, /You've watched this one\./);
  const steps = harness.body.find(node => node.dataset.guideStep);
  assert.deepEqual(steps.map(node => node.textContent), ['‹ S2 E2', 'S2 E4 ›']);
  harness.setReply(guidePayload([{ season: 2, episode: 3, rating: 8, note: null, spoiler: false }]));
  const eight = harness.body.find(node => node.dataset.guideRate === '8')[0];
  await harness.click(eight);
  const put = harness.requests.at(-1);
  assert.equal(put.method, 'PUT');
  assert.match(put.url, /\/progress\/tv-shows\/7\/episode-notes$/);
  assert.deepEqual(put.body, { season: 2, episode: 3, rating: 8, note: null, spoiler: false });
  const pressed = harness.body.find(node => node.dataset.guideRate === '8')[0];
  assert.equal(pressed.attributes['aria-pressed'], 'true');
  assert.match(harness.body.find(node => node.id === 'episodeDialogStatus')[0].textContent, /Gave S2 E3 8\/10\./);
});

test('the first and last episodes have nowhere to step', async () => {
  const harness = setup({ mode: 'rate', payload: guidePayload() });
  harness.api.rate('tv-shows', 7, 'Severance', 1, 1);
  await flush(); await flush();
  const steps = harness.body.find(node => node.dataset.guideStep);
  assert.equal(steps[0].disabled, true);
  assert.equal(steps[1].textContent, 'S1 E2 ›');
  // Season 1 ends at 9, so the next one is the start of season 2.
  harness.api.rate('tv-shows', 7, 'Severance', 1, 9);
  await flush(); await flush();
  assert.equal(harness.body.find(node => node.dataset.guideStep === '1')[0].textContent, 'S2 E1 ›');
});

test('watch mode stays the default and taps still mark episodes watched', async () => {
  const harness = setup({ mode: 'other', payload: guidePayload() });
  harness.api.open('tv-shows', 7, 'Severance');
  await flush(); await flush();
  const cell = harness.body.find(node => node.dataset.guideSeason === '1' && node.dataset.guideEpisode === '2')[0];
  assert.equal(cell.attributes['aria-pressed'], 'true');
  await harness.click(cell);
  assert.ok(harness.requests.some(request => request.method === 'PUT' && /\/episode$/.test(request.url)));
  const toggle = harness.body.find(node => node.dataset.guideMode === 'rate')[0];
  await harness.click(toggle);
  assert.equal(harness.storage.get('omnitrackr.episodeGuideMode'), 'rate');
});

test('the one-tap next episode toast offers to rate it', async () => {
  const harness = setup({ payload: guidePayload() });
  const holder = harness.body.appendChild(new (Object.getPrototypeOf(harness.body).constructor)('td'));
  harness.api.appendRow(holder, { category: 'tv-shows', id: 7, title: 'Severance', episode_progress: guidePayload().episodes });
  const next = holder.find(node => node.dataset.episodeNext)[0];
  await harness.listeners.get('click')({ target: next, preventDefault() {} });
  await flush(); await flush();
  const toast = harness.body.find(node => node.id === 'episodeToast')[0];
  assert.match(toast.textContent, /Marked S2 E5 of Severance watched\.Rate itUndo/);
});
