// Streamlined home (home-layout.js): the "Do this next" title and the board's "Show more" limit.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

// A small DOM: enough selectors for home-layout.js (tag, .class, #id, [attr], [id$=...], :not([hidden]), :scope >).
class Node {
  constructor(tag = 'div', props = {}) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parent = null;
    this.dataset = {};
    this.attributes = {};
    this.hidden = false;
    this._text = '';
    this.className = '';
    this.listeners = {};
    Object.assign(this, props);
    const node = this;
    this.classList = {
      add: (...names) => { const set = new Set(node.className.split(/\s+/).filter(Boolean)); names.forEach(n => set.add(n)); node.className = [...set].join(' '); },
      remove: (...names) => { node.className = node.className.split(/\s+/).filter(n => n && !names.includes(n)).join(' '); },
      contains: name => node.className.split(/\s+/).includes(name),
      toggle: (name, force) => { const on = force === undefined ? !node.classList.contains(name) : force; if (on) node.classList.add(name); else node.classList.remove(name); return on; },
    };
  }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach(child => { child.parent = null; }); this.children = []; }
  set innerHTML(_) { throw new Error('home-layout.js must use textContent'); }
  append(...nodes) { nodes.forEach(node => { node.parent = this; this.children.push(node); }); }
  appendChild(node) { this.append(node); return node; }
  prepend(node) { node.parent = this; this.children.unshift(node); }
  replaceChildren(...nodes) { this.children.forEach(child => { child.parent = null; }); this.children = []; this._text = ''; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); this.parent = null; }
  setAttribute(key, value) { this.attributes[key] = String(value); if (key === 'hidden') this.hidden = true; if (key === 'id') this.id = String(value); }
  getAttribute(key) { return key === 'id' ? this.id : this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; if (key === 'hidden') this.hidden = false; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  descendants() { return this.children.flatMap(child => [child, ...child.descendants()]); }
  matchesOne(selector) {
    let rest = selector.trim();
    if (rest.includes(':not([hidden])')) { if (this.hidden) return false; rest = rest.replace(/:not\(\[hidden\]\)/g, ''); }
    const tag = rest.match(/^[a-z][a-z0-9]*/);
    if (tag && this.tagName !== tag[0].toUpperCase()) return false;
    for (const [, name] of rest.matchAll(/\.([\w-]+)/g)) if (!this.classList.contains(name)) return false;
    for (const [, id] of rest.matchAll(/#([\w-]+)/g)) if (this.id !== id) return false;
    for (const [, suffix] of rest.matchAll(/\[id\$="([^"]+)"\]/g)) if (!String(this.id || '').endsWith(suffix)) return false;
    if (/\[id\]/.test(rest) && !this.id) return false;
    return true;
  }
  matches(selector) { return selector.split(',').some(part => this.matchesOne(part)); }
  querySelectorAll(selector) {
    if (selector.startsWith(':scope >')) return this.children.filter(child => child.matches(selector.slice(8)));
    return this.descendants().filter(node => node.matches(selector));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { let node = this; while (node) { if (node.matches?.(selector)) return node; node = node.parent; } return null; }
}

function section(id, extra = {}) {
  const node = new Node('section', { id, ...extra });
  return node;
}

function setup() {
  const root = new Node('html');
  const byId = () => {
    const map = new Map();
    root.descendants().forEach(node => { if (node.id) map.set(node.id, node); });
    return map;
  };
  const document = {
    readyState: 'complete',
    documentElement: new Node('html'),
    body: new Node('body'),
    activeElement: null,
    createElement: tag => new Node(tag),
    getElementById: id => byId().get(id) || null,
    querySelector: selector => root.querySelector(selector),
    querySelectorAll: selector => root.querySelectorAll(selector),
    addEventListener() {},
  };
  const window = {
    location: { hash: '' }, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }),
    requestAnimationFrame: fn => { fn(); return 1; }, setTimeout: () => 0,
  };
  const storage = new Map();
  const context = vm.createContext({
    document, window, console, Date, JSON, Number, Boolean, String, Array, Set, Map, Object, Math,
    MutationObserver: undefined,
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value)), removeItem: key => storage.delete(key) },
  });
  window.OmniProgress = {
    appendSummary(container, item) { if (item.progress) container.appendChild(Object.assign(new Node('span'), { className: 'progress-checkpoint', _text: 'Last read · Page 212' })); },
    appendAction(container, item) { if (['tv-shows', 'books'].includes(item.category)) container.appendChild(Object.assign(new Node('button'), { className: 'progress-update', _text: 'Update progress' })); },
  };
  window.OmniEpisodes = {
    appendBar() {},
    appendActions(container, item) {
      if (item.category !== 'tv-shows' || !item.episode_progress) return;
      const wrap = Object.assign(new Node('span'), { className: 'episode-actions' });
      wrap.append(Object.assign(new Node('button'), { className: 'episode-next', _text: '+ S2 E6' }), Object.assign(new Node('button'), { className: 'episode-guide-open', _text: 'Episodes' }));
      container.appendChild(wrap);
    },
  };
  const code = require('node:fs').readFileSync(path.join(__dirname, '..', 'app', 'static', 'home-layout.js'), 'utf8');
  vm.runInContext(code, context);
  return { root, document, window, context, storage, api: window };
}

function focusMarkup(root) {
  const focus = section('homeFocus', { hidden: true });
  focus.append(Object.assign(new Node('span'), { id: 'homeFocusCover' }));
  const copy = new Node('div');
  copy.append(Object.assign(new Node('p'), { id: 'homeFocusEyebrow' }), Object.assign(new Node('h2'), { id: 'homeFocusTitle' }),
    Object.assign(new Node('p'), { id: 'homeFocusMeta' }), Object.assign(new Node('div'), { id: 'homeFocusProgress' }));
  focus.append(copy, Object.assign(new Node('div'), { id: 'homeFocusActions' }));
  root.append(focus);
  return focus;
}

const SEVERANCE = {
  id: 7, category: 'tv-shows', category_label: 'TV show', title: 'Severance', status_label: 'Watching now',
  image: 'https://image.tmdb.org/t/p/w342/x.jpg', episode_progress: { current: { season: 2, episode: 5 }, next: { season: 2, episode: 6 } },
};

test('the first Continue title becomes "Do this next", with the next-episode button first', () => {
  const { root, api } = setup();
  const focus = focusMarkup(root);
  assert.equal(api.OmniHomeFocus.claim([SEVERANCE, { ...SEVERANCE, id: 8, title: 'The Bear' }]), true);
  assert.equal(focus.hidden, false);
  const get = id => root.querySelector(`#${id}`);
  assert.equal(get('homeFocusTitle').textContent, 'Severance');
  assert.equal(get('homeFocusEyebrow').textContent, 'Pick up where you left off');
  assert.equal(get('homeFocusMeta').textContent, 'TV show · Watching now');
  const primary = get('homeFocusActions').querySelector('.home-focus__primary');
  assert.equal(primary.textContent, '+ S2 E6');
  const open = get('homeFocusActions').querySelector('.home-focus__open');
  assert.equal(open.dataset.action, 'pulse-open-item');
  assert.equal(open.dataset.pulseItemId, '7');
  assert.equal(open.dataset.pulseTab, 'tv-shows');
  assert.equal(focus.dataset.format, 'tv-shows');
});

test('a saved title nobody started reads "Ready when you are"; a book leads with Update progress', () => {
  const { root, api } = setup();
  focusMarkup(root);
  api.OmniHomeFocus.claim([{ id: 3, category: 'movies', category_label: 'Movie', title: 'Aftersun', status_label: 'Not watched' }]);
  assert.equal(root.querySelector('#homeFocusEyebrow').textContent, 'Ready when you are');
  // A film has nothing to step through: finishing it is the one tap that moves it forward.
  assert.equal(root.querySelector('#homeFocusActions').querySelector('.home-focus__primary').textContent, 'Mark watched');
  assert.ok(root.querySelector('#homeFocusActions').querySelector('.home-focus__open'), 'Open stays next to it');
  api.OmniHomeFocus.claim([{ id: 4, category: 'books', category_label: 'Book', title: 'Dune', status_label: 'Not read', progress: { unit: 'page', position: 212 } }]);
  assert.equal(root.querySelector('#homeFocusEyebrow').textContent, 'Pick up where you left off');
  assert.equal(root.querySelector('#homeFocusActions').querySelector('.home-focus__primary').textContent, 'Update progress');
});

test('"Mark watched" finishes a film in one tap and refreshes Continue; a failed save says so', async () => {
  const { root, api, context } = setup();
  focusMarkup(root);
  const calls = [], notices = [], moments = [];
  let pulses = 0, ok = true;
  context.API_BASE = '';
  context.authenticatedFetch = async (url, options) => { calls.push([url, options.method, JSON.parse(options.body)]); return { ok }; };
  context.showNotice = (message, tone) => notices.push([message, tone]);
  context.openCompletionMoment = (category, id) => moments.push([category, id]);
  context.refreshLibraryPulse = () => { pulses += 1; };
  api.OmniHomeFocus.claim([{ id: 3, category: 'movies', category_label: 'Movie', title: 'Aftersun', status_label: 'Not watched' }]);
  const done = root.querySelector('#homeFocusActions').querySelector('.home-focus__done');
  assert.equal(done.getAttribute('aria-label'), 'Mark Aftersun as watched');
  await done.listeners.click[0]();
  assert.deepEqual(calls, [['/movies/3', 'PUT', { watched: true }]]);
  assert.deepEqual(notices, [['Aftersun: marked watched.', 'success']]);
  assert.deepEqual(moments, [['movies', 3]]);
  assert.equal(pulses, 1);
  ok = false;
  await done.listeners.click[0]();
  assert.equal(notices.at(-1)[1], 'error');
  assert.equal(moments.length, 1, 'no finish moment when nothing saved');
  // An album says "listened"; a show with an episode to log keeps "+ S2 E6" first and gets no finish button.
  api.OmniHomeFocus.claim([{ id: 9, category: 'music', category_label: 'Album', title: 'Blonde', status_label: 'Not listened' }]);
  assert.equal(root.querySelector('#homeFocusActions').querySelector('.home-focus__primary').textContent, 'Mark listened');
  api.OmniHomeFocus.claim([SEVERANCE]);
  assert.equal(root.querySelector('#homeFocusActions').querySelector('.home-focus__done'), null);
});

test('with nothing on the go the top of Next Up is offered with Start; an empty home shows nothing', () => {
  const { root, api } = setup();
  const focus = focusMarkup(root);
  assert.equal(api.OmniHomeFocus.claim([]), false);
  api.OmniHomeFocus.queue([
    { id: 600, item_id: 42, category: 'movies', category_label: 'Movie', title: 'Done already', available: true, finished: true },
    { id: 601, item_id: 43, category: 'movies', category_label: 'Movie', title: 'Blade Runner 2049', available: true, now_label: 'Watching' },
  ]);
  assert.equal(focus.hidden, false);
  assert.equal(root.querySelector('#homeFocusTitle').textContent, 'Blade Runner 2049');
  assert.equal(root.querySelector('#homeFocusEyebrow').textContent, 'First in your Next Up queue');
  const start = root.querySelector('#homeFocusActions').querySelector('.home-focus__primary');
  assert.equal(start.textContent, 'Start watching');
  assert.equal(start.dataset.action, 'start-next-up');
  assert.equal(start.dataset.nextUpId, '601');
  assert.equal(root.querySelector('#homeFocusActions').querySelector('.home-focus__open').dataset.pulseItemId, '43');
  // Continue wins over the queue as soon as it has a title.
  api.OmniHomeFocus.claim([SEVERANCE]);
  assert.equal(root.querySelector('#homeFocusTitle').textContent, 'Severance');
  api.OmniHomeFocus.claim([]);
  api.OmniHomeFocus.queue([]);
  assert.equal(focus.hidden, true);
  api.OmniHomeFocus.claim([SEVERANCE]);
  api.OmniHomeFocus.reset();
  assert.equal(focus.hidden, true);
});

test('nothing is claimed without the focus card or when the first title is unusable', () => {
  const { root, api } = setup();
  assert.equal(api.OmniHomeFocus.claim([SEVERANCE]), false);
  focusMarkup(root);
  assert.equal(api.OmniHomeFocus.claim([{ ...SEVERANCE, id: 0 }, SEVERANCE]), false);
  assert.equal(root.querySelector('#homeFocus').hidden, true);
});

function board(root, mainIds, railIds) {
  const wrap = Object.assign(new Node('div'), { className: 'home-board' });
  const main = Object.assign(new Node('div'), { className: 'home-board__main' });
  const rail = Object.assign(new Node('div'), { className: 'home-board__rail-cards' });
  mainIds.forEach(id => {
    if (id === 'daily') {
      const daily = Object.assign(new Node('div'), { className: 'daily-dashboard' });
      daily.append(section('libraryPulse'), section('todaysPick', { hidden: true }));
      main.append(daily);
    } else main.append(section(id));
  });
  railIds.forEach(id => rail.append(section(id)));
  const more = Object.assign(new Node('div'), { id: 'homeMore', hidden: true });
  more.append(Object.assign(new Node('button'), { id: 'homeMoreToggle' }), Object.assign(new Node('p'), { id: 'homeMoreNames', hidden: true }));
  wrap.append(main, rail, more);
  root.append(wrap);
  return { wrap, main, rail, more };
}

const tucked = root => root.querySelectorAll('.is-home-tucked').map(node => node.id || 'daily');

test('each column shows its first few cards; the rest wait behind one "Show more" row that names them', () => {
  const { root, api } = setup();
  const { more } = board(root, ['daily', 'homeNews', 'nextUpQueue', 'yourWeek', 'backlogDraw', 'comingUp'], ['monthlyChallenge', 'awardsBallot', 'yearSoFar', 'seasonCard']);
  // What's new and Next Up have the member's own things in them.
  const news = root.querySelector('#homeNews');
  const shows = section('homeNewsShows'); news.append(shows);
  const queueItems = Object.assign(new Node('div'), { id: 'nextUpQueueItems' }); queueItems.append(new Node('div'));
  root.querySelector('#nextUpQueue').append(queueItems);
  root.querySelector('#backlogDraw').append(Object.assign(new Node('h2'), { _text: 'Draw your next one' }));
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['backlogDraw', 'comingUp', 'seasonCard']);
  assert.equal(more.hidden, false);
  assert.equal(root.querySelector('#homeMoreToggle').textContent, 'Show 3 more on your home');
  assert.match(root.querySelector('#homeMoreNames').textContent, /^Draw your next one/);
  // Opening it shows everything and remembers the choice.
  api.OmniHomeLayout.expand(true, { announce: false });
  assert.equal(root.querySelector('.home-board').classList.contains('home-board--more'), true);
  assert.equal(root.querySelector('#homeMoreToggle').textContent, 'Show fewer cards');
});

test('cards with nothing of the member\'s own wait; cards in use, celebrating or linked to never do', () => {
  const { root, api, window } = setup();
  board(root, ['weekOne', 'daily', 'homeNews', 'nextUpQueue', 'yourWeek', 'backlogDraw', 'stayPosted', 'badgeCase'], ['yearGoals', 'supportAsk']);
  // What's new holds only the invite; Next Up is empty; no goals set.
  root.querySelector('#homeNews').append(Object.assign(section('homeNewsShows'), { hidden: true }));
  root.querySelector('#nextUpQueue').append(Object.assign(new Node('div'), { id: 'nextUpQueueItems' }));
  root.querySelector('#yearGoals').append(Object.assign(new Node('ul'), { id: 'yearGoalsList', hidden: true }));
  api.OmniHomeLayout.arrange();
  // First week, stay-posted and support notes keep their own rules; badges wait unless they're celebrating.
  assert.deepEqual(tucked(root), ['homeNews', 'nextUpQueue', 'badgeCase', 'yearGoals']);
  root.querySelector('#badgeCase').append(section('badgeCaseCelebration'));
  window.location.hash = '#next-up-nothing';
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['homeNews', 'nextUpQueue', 'yearGoals']);
  window.location.hash = '#homeNews';
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['nextUpQueue', 'yearGoals']);
  window.location.hash = '#goals';
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['homeNews', 'nextUpQueue']);
});

test('a column never empties itself, and a planned backlog night or a set pace always shows', () => {
  const { root, api } = setup();
  board(root, ['nextUpQueue', 'comingUp'], []);
  root.querySelector('#nextUpQueue').append(Object.assign(new Node('div'), { id: 'nextUpQueueItems' }));
  root.querySelector('#comingUp').dataset.source = 'popular';
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['comingUp']);

  const second = setup();
  board(second.root, ['daily', 'homeNews', 'nextUpQueue', 'yourWeek', 'backlogDraw'], []);
  second.root.querySelector('#homeNews').append(section('homeNewsShows'));
  const items = Object.assign(new Node('div'), { id: 'nextUpQueueItems' }); items.append(new Node('div'));
  second.root.querySelector('#nextUpQueue').append(items);
  second.root.querySelector('#yourWeek').dataset.status = 'open';
  second.root.querySelector('#backlogDraw').append(Object.assign(new Node('div'), { className: 'backlog-draw__plan' }));
  second.window.matchMedia = () => ({ matches: true, addEventListener() {} });
  second.api.OmniHomeLayout.start();
  assert.deepEqual(tucked(second.root), []);
});

test('Continue skips the title shown in "Do this next" and keeps ratings when nothing else is on the go', () => {
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Node(id === 'libraryPulse' ? 'section' : 'div', { id })); return nodes.get(id); };
  let claimed = null;
  const context = vm.createContext({
    window: { OmniHomeFocus: { claim: items => { claimed = items; return items.length > 0; } } },
    document: { getElementById: get, createElement: tag => new Node(tag), querySelectorAll: () => [] },
    returnDeckActive: false, todaysPickCandidateCount: 0, todaysPickSelection: null, todaysPickSkips: 0,
  });
  vm.runInContext(source.slice(source.indexOf('function renderLibraryPulseList('), source.indexOf('function renderTodaysPick(')), context);
  vm.runInContext(source.slice(source.indexOf("const SHOWN_PULSE_ITEMS"), source.indexOf('async function refreshTodaysPick(')), context);
  const items = [1, 2, 3, 4, 5, 6].map(id => ({ id, category: 'books', category_label: 'Book', title: `Book ${id}`, status_label: 'Not read' }));
  const pulseHeader = Object.assign(new Node('p'), { className: 'library-pulse__eyebrow' });
  get('libraryPulse').append(pulseHeader);
  context.renderLibraryPulse({ continue_items: items, reflection_items: [] });
  assert.equal(claimed.length, 6);
  assert.deepEqual(get('libraryPulseContinue').children.map(child => child.dataset.pulseItemId), ['2', '3', '4', '5']);
  assert.equal(get('libraryPulseTitle').textContent, 'Continue');
  assert.equal(pulseHeader.textContent, 'Also on the go');
  context.renderLibraryPulse({ continue_items: items.slice(0, 1), reflection_items: items.slice(1, 3) });
  assert.equal(get('libraryPulse').hidden, false);
  assert.equal(get('libraryPulseContinue').hidden, true);
  assert.equal(get('libraryPulseReflections').open, true);
  assert.equal(get('libraryPulseTitle').textContent, 'Make it memorable');
  context.renderLibraryPulse({ continue_items: items.slice(0, 1), reflection_items: [] });
  assert.equal(get('libraryPulse').hidden, true);
});

test('a card a link asked for stays out after its own script clears the hash (Nov 21 sweep)', () => {
  const { root, api, window, storage } = setup();
  board(root, ['daily', 'homeNews', 'nextUpQueue', 'badgeCase'], ['monthlyChallenge', 'yearGoals']);
  root.querySelector('#yearGoals').append(Object.assign(new Node('ul'), { id: 'yearGoalsList', hidden: true }));
  const listeners = {};
  window.addEventListener = (type, fn) => { (listeners[type] ||= []).push(fn); };
  // Opened from /#goals (the goals page, a goal email or a notification); goals.js then clears the hash.
  window.location.hash = '#goals';
  api.OmniHomeLayout.start();
  window.location.hash = '';
  api.OmniHomeLayout.arrange();
  assert.equal(tucked(root).includes('yearGoals'), false);
  assert.equal(tucked(root).includes('badgeCase'), true);

  // Later, a same-page link to the badge case: the hash may already be gone when this listener runs.
  listeners.hashchange.forEach(fn => fn({ newURL: 'https://omnitrackr.xyz/#badges' }));
  assert.equal(tucked(root).includes('badgeCase'), false);
  // Only the linked card comes out; Show more stays the member's own choice.
  assert.equal(root.querySelector('.home-board').classList.contains('home-board--more'), false);
  assert.equal(storage.has('omnitrackr_home_more'), false);

  // Signing out forgets it.
  api.OmniHomeLayout.reset();
  api.OmniHomeLayout.arrange();
  assert.equal(tucked(root).includes('badgeCase'), true);
});

test('after "Mark watched" from the keyboard, focus waits on the card heading for the finish moment to hand back', async () => {
  const { root, api, context, document } = setup();
  focusMarkup(root);
  context.API_BASE = '';
  let focusAtMoment = null;
  context.authenticatedFetch = async () => ({ ok: true });
  context.showNotice = () => {};
  context.openCompletionMoment = () => { focusAtMoment = document.activeElement; };
  api.OmniHomeFocus.claim([{ id: 3, category: 'movies', category_label: 'Movie', title: 'Aftersun', status_label: 'Not watched' }]);
  const heading = root.querySelector('#homeFocusTitle');
  heading.focus = () => { document.activeElement = heading; };
  const done = root.querySelector('#homeFocusActions').querySelector('.home-focus__done');
  document.activeElement = done;
  await done.listeners.click[0]();
  // The button is redrawn away with the next title; the heading stays, so the dialog's opener is still there.
  assert.equal(focusAtMoment, heading);
  assert.equal(heading.getAttribute('tabindex'), '-1');
  // A tap that left focus elsewhere (another script moved it) is left alone.
  const other = new Node('button');
  document.activeElement = other;
  await done.listeners.click[0]();
  assert.equal(focusAtMoment, other);
});

test('another card can bring a tucked card out before scrolling to it, without opening Show more (Nov 21 sweep f)', () => {
  const { root, api, storage } = setup();
  board(root, ['daily', 'homeNews', 'nextUpQueue', 'yourWeek', 'backlogDraw', 'comingUp'], ['monthlyChallenge']);
  root.querySelector('#homeNews').append(section('homeNewsShows'));
  const items = Object.assign(new Node('div'), { id: 'nextUpQueueItems' }); items.append(new Node('div'));
  root.querySelector('#nextUpQueue').append(items);
  api.OmniHomeLayout.arrange();
  assert.deepEqual(tucked(root), ['backlogDraw', 'comingUp']);
  // The October challenge's "Deal me in" asks for the backlog draw.
  assert.equal(typeof api.OmniHomeLayout.reveal, 'function');
  api.OmniHomeLayout.reveal(root.querySelector('#backlogDraw'));
  // A card asked for doesn't take another card's place.
  assert.deepEqual(tucked(root), ['comingUp']);
  // It stays out on the next arrange; Show more stays the member's own choice.
  api.OmniHomeLayout.arrange();
  assert.equal(tucked(root).includes('backlogDraw'), false);
  assert.equal(root.querySelector('.home-board').classList.contains('home-board--more'), false);
  assert.equal(storage.has('omnitrackr_home_more'), false);
});
