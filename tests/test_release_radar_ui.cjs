const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const radarScript = fs.readFileSync(path.join(__dirname, '../app/static/release-radar.js'), 'utf8');
const authScript = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

// ---------------------------------------------------------------------------
// A deliberately small DOM: enough selectors for release-radar.js.
// ---------------------------------------------------------------------------
class Element {
  constructor(tag, attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.attributes = {};
    this.dataset = {};
    this.children = [];
    this.parent = null;
    this.listeners = {};
    this.classList = {
      set: new Set(),
      add: (...names) => names.forEach(name => this.classList.set.add(name)),
      remove: (...names) => names.forEach(name => this.classList.set.delete(name)),
      contains: name => this.classList.set.has(name),
    };
    this.value = '';
    this.checked = false;
    this._text = '';
    for (const [key, value] of Object.entries(attrs)) this.setAttribute(key, value);
  }
  setAttribute(key, value) {
    value = String(value);
    if (key === 'class') value.split(/\s+/).filter(Boolean).forEach(name => this.classList.add(name));
    else if (key.startsWith('data-')) this.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
    if (key === 'hidden') this.hidden = true;
    this.attributes[key] = value;
  }
  getAttribute(key) {
    if (key.startsWith('data-')) {
      const name = key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      return name in this.dataset ? this.dataset[name] : null;
    }
    return key in this.attributes ? this.attributes[key] : null;
  }
  hasAttribute(key) { return key === 'hidden' ? Boolean(this.hidden) : this.getAttribute(key) !== null; }
  append(...nodes) { for (const node of nodes) { node.parent = this; this.children.push(node); } return this; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('release-radar.js must not assign innerHTML'); }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  dispatch(name, props = {}) {
    const event = {defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, target: this, ...props};
    let node = this;
    while (node) { (node.listeners[name] || []).forEach(handler => handler(event)); node = node.parent; }
    return event;
  }
  focus() { this.ownerDocument && (this.ownerDocument.activeElement = this); }
  descendants() { return this.children.flatMap(child => [child, ...child.descendants()]); }
  matches(selector) { return selector.split(',').some(part => matchSimple(this, part.trim())); }
  querySelectorAll(selector) { return this.descendants().filter(node => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { let node = this; while (node) { if (node.matches && node.matches(selector)) return node; node = node.parent; } return null; }
}

function matchSimple(node, selector) {
  let rest = selector;
  let negateHidden = false;
  if (rest.endsWith(':not([hidden])')) { negateHidden = true; rest = rest.slice(0, -':not([hidden])'.length); }
  const tag = rest.match(/^[a-z]+/i);
  if (tag) { if (node.tagName !== tag[0].toUpperCase()) return false; rest = rest.slice(tag[0].length); }
  for (const cls of rest.matchAll(/\.([\w-]+)/g)) if (!node.classList.contains(cls[1])) return false;
  for (const attr of rest.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)) {
    const value = attr[1] === 'type' ? node.attributes.type : node.getAttribute(attr[1]);
    if (value === null || value === undefined) return false;
    if (attr[2] !== undefined && String(value) !== attr[2]) return false;
  }
  if (negateHidden && node.hidden) return false;
  return true;
}

function card({key, category = 'games', window = '2026-10', search, genres = '', platforms = ''}) {
  const article = new Element('article', {class: 'radar-card', 'data-key': key, 'data-category': category,
    'data-window': window, 'data-search': search, 'data-genres': genres, 'data-platforms': platforms});
  const link = new Element('a', {class: 'radar-add', 'data-radar-add': key, href: '/?next=/release-radar/games#landing-auth'});
  link.textContent = '+ Track this';
  article.append(link);
  return {article, link};
}

function setup({status = 200, owned = [], saveStatus = 200, saveState = 'created'} = {}) {
  const body = new Element('body');
  const filters = new Element('section', {id: 'radar-filters', hidden: ''});
  const search = new Element('input', {type: 'search', 'data-radar-filter': 'search'});
  const genre = new Element('select', {'data-radar-filter': 'genre'});
  const platform = new Element('select', {'data-radar-filter': 'platform'});
  const mineWrap = new Element('div', {'data-radar-mine-wrap': '', hidden: ''});
  const mine = new Element('input', {type: 'checkbox', 'data-radar-filter': 'hide-mine'});
  mineWrap.append(mine);
  const reset = new Element('button', {'data-radar-reset': ''});
  const results = new Element('p', {id: 'radar-results'});
  filters.append(search, genre, platform, mineWrap, reset, results);
  const list = new Element('div', {id: 'radar-list'});
  const week1 = new Element('section', {class: 'radar-week'});
  const week2 = new Element('section', {class: 'radar-week'});
  const a = card({key: 'rawg-a', search: 'starfall odyssey action rpg pc', genres: 'Action|RPG', platforms: 'PC|PlayStation 5'});
  const b = card({key: 'rawg-b', search: 'pocket farm simulation', genres: 'Simulation', platforms: 'Nintendo Switch 2'});
  const c = card({key: 'rawg-c', search: 'night terrors horror', genres: 'Horror|Action', platforms: 'PC'});
  week1.append(a.article, b.article);
  week2.append(c.article);
  list.append(week1, week2);
  const empty = new Element('p', {id: 'radar-empty', hidden: ''});
  const jump = new Element('select', {'data-radar-jump': ''});
  body.append(jump, filters, list, empty);

  const requests = [];
  const assigned = [];
  const document = {
    body,
    createElement: tag => new Element(tag),
    getElementById: id => body.descendants().find(node => node.attributes.id === id) || null,
    querySelector: selector => body.querySelector(selector),
    querySelectorAll: selector => body.querySelectorAll(selector),
  };
  const context = vm.createContext({
    document,
    window: {location: {assign: url => assigned.push(url)}},
    localStorage: {getItem: () => 'token-123'},
    fetch: async (url, options = {}) => {
      requests.push({url, options});
      if (url.endsWith('/library')) return {status, ok: status === 200, json: async () => ({keys: owned})};
      const payload = JSON.parse(options.body);
      return {status: saveStatus, ok: saveStatus === 200, json: async () => ({state: saveState, title: `Title ${payload.key}`, collection_id: 7})};
    },
  });
  vm.runInContext(radarScript, context);
  return {filters, search, genre, platform, mine, mineWrap, reset, results, list, week1, week2, a, b, c, empty, jump, requests, assigned, body};
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('filters reveal themselves and narrow the list without hiding content by default', async () => {
  const ui = setup({status: 401});
  assert.equal(ui.filters.hidden, false);
  assert.equal(ui.results.textContent, '3 of 3 titles');
  ui.search.value = 'Horror';
  ui.search.dispatch('input');
  assert.equal(ui.a.article.hidden, true);
  assert.equal(ui.c.article.hidden, false);
  assert.equal(ui.week1.hidden, true, 'weeks without visible titles are hidden');
  assert.equal(ui.results.textContent, '1 of 3 titles');
  ui.search.value = '';
  ui.platform.value = 'PC';
  ui.platform.dispatch('change');
  assert.deepEqual([ui.a.article.hidden, ui.b.article.hidden, ui.c.article.hidden], [false, true, false]);
  ui.genre.value = 'RPG';
  ui.genre.dispatch('change');
  assert.deepEqual([ui.a.article.hidden, ui.b.article.hidden, ui.c.article.hidden], [false, true, true]);
  ui.search.value = 'nothing-matches';
  ui.search.dispatch('input');
  assert.equal(ui.empty.hidden, false);
  ui.reset.dispatch('click');
  assert.equal(ui.results.textContent, '3 of 3 titles');
  assert.equal(ui.empty.hidden, true);
});

test('guests keep their sign-in links', async () => {
  const ui = setup({status: 401});
  await flush();
  assert.equal(ui.a.link.getAttribute('href'), '/?next=/release-radar/games#landing-auth');
  assert.equal(ui.mineWrap.hidden, true);
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.requests[0].url, '/api/release-radar/games/2026-10/library');
});

test('members see owned titles and can track new ones exactly once', async () => {
  const ui = setup({owned: ['rawg-b']});
  await flush(); await flush();
  assert.equal(ui.mineWrap.hidden, false);
  assert.equal(ui.b.link.textContent, '✓ In your library');
  assert.equal(ui.a.link.getAttribute('href'), '#');
  assert.equal(ui.requests[0].options.headers.Authorization, 'Bearer token-123');

  const event = ui.a.link.dispatch('click');
  assert.equal(event.defaultPrevented, true);
  await flush(); await flush();
  const save = ui.requests.find(request => request.url === '/api/release-radar/save');
  assert.deepEqual(JSON.parse(save.options.body), {category: 'games', window: '2026-10', key: 'rawg-a'});
  assert.equal(save.options.method, 'POST');
  assert.equal(ui.a.link.textContent, '✓ In your library');
  assert.match(ui.body.textContent, /Title rawg-a added to your library/);

  ui.a.link.dispatch('click');
  await flush();
  assert.equal(ui.requests.filter(request => request.url === '/api/release-radar/save').length, 1, 'saved titles are not re-sent');

  ui.mine.checked = true;
  ui.mine.dispatch('change');
  assert.deepEqual([ui.a.article.hidden, ui.b.article.hidden, ui.c.article.hidden], [true, true, false]);
});

test('an expired session sends the member to sign in instead of failing silently', async () => {
  const ui = setup({saveStatus: 401});
  await flush(); await flush();
  ui.c.link.dispatch('click');
  await flush(); await flush();
  assert.deepEqual(ui.assigned, ['/?next=/release-radar/games#landing-auth']);
});

test('save failures are announced and can be retried', async () => {
  const ui = setup({saveStatus: 500});
  await flush(); await flush();
  ui.c.link.dispatch('click');
  await flush(); await flush();
  assert.match(ui.body.textContent, /Could not save that title/);
  assert.equal(ui.c.link.classList.contains('is-saved'), false);
});

test('period picker only navigates to radar paths', () => {
  const ui = setup({status: 401});
  for (const value of ['/release-radar/games/2026-11', '/release-radar/anime/winter-2027', '/release-radar/tv']) {
    ui.jump.value = value; ui.jump.dispatch('change');
  }
  for (const value of ['https://evil.example', '//evil.example/release-radar/tv', '/release-radar/podcasts']) {
    ui.jump.value = value; ui.jump.dispatch('change');
  }
  assert.deepEqual(ui.assigned, ['/release-radar/games/2026-11', '/release-radar/anime/winter-2027', '/release-radar/tv']);
});

test('sign-in return allowlist accepts radar pages only in their exact forms', () => {
  const context = vm.createContext({
    URLSearchParams, location: {pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz'},
    window: {location: {pathname: '/', search: ''}, history: {replaceState() {}}},
    document: {readyState: 'loading', documentElement: {dataset: {}}, addEventListener() {}, getElementById: () => ({style: {}, dataset: {}})},
    sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
    localStorage: {getItem: () => null, setItem() {}, removeItem() {}},
  });
  vm.runInContext(authScript, context);
  const allowed = ['/release-radar', '/release-radar/movies', '/release-radar/tv/2026-11', '/release-radar/anime/fall-2026'];
  for (const value of allowed) assert.equal(context.validateDiscoverAuthReturn(value), value);
  const rejected = ['/release-radar/', '/release-radar/podcasts', '/release-radar/tv/2026-11/x', '//evil.example',
    '/release-radar/anime/autumn-2026', '/release-radar\n', 'https://omnitrackr.xyz/release-radar'];
  for (const value of rejected) assert.equal(context.validateDiscoverAuthReturn(value), null, value);
  // Existing destinations keep working.
  assert.equal(context.validateDiscoverAuthReturn('/discover/finding-your-feet#save-picks'), '/discover/finding-your-feet#save-picks');
});
