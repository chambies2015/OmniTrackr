// Nov 21 sweep of #276 and #278: getting back to an Essential 100 list after signing up.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = path.join(__dirname, '../app/static');
const FORMATS = ['movies', 'tv', 'anime', 'games', 'books', 'music', 'manga', 'podcasts', 'audiobooks'];

function memoryStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: key => map.delete(key),
  };
}

function loadAuth() {
  const location = { pathname: '/', search: '', protocol: 'https:', origin: 'https://omnitrackr.xyz', assign() {}, reload() {} };
  const context = vm.createContext({
    URLSearchParams, AbortController, location,
    window: { location, history: { replaceState() {} } },
    document: { readyState: 'loading', documentElement: { dataset: {} }, addEventListener() {}, querySelector: () => null, getElementById: () => null },
    sessionStorage: memoryStorage(), localStorage: memoryStorage(),
    fetch: async () => ({ ok: false, status: 401, json: async () => null }),
    setTimeout() {}, clearTimeout() {},
  });
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'auth.js'), 'utf8'), context);
  return context;
}

test('sign-in can come back to the Essential 100 hub, a list, or its count', () => {
  const auth = loadAuth();
  for (const destination of ['/essentials', ...FORMATS.map(fmt => `/essentials/${fmt}`), ...FORMATS.map(fmt => `/essentials/${fmt}#your-count`)]) {
    assert.equal(auth.validateDiscoverAuthReturn(destination), destination, destination);
  }
});

test('anything else under /essentials is refused', () => {
  const auth = loadAuth();
  for (const destination of ['/essentials/', '/essentials/films', '/essentials/movies/', '/essentials/movies#start-here',
    '/essentials#your-count', '/essentials/movies/score/37', '/essentials/movies?x=1', '/essentials/movies#your-count\n',
    '//essentials/movies', '/Essentials/movies', 'https://example.com/essentials/movies']) {
    assert.equal(auth.validateDiscoverAuthReturn(destination), null, JSON.stringify(destination));
  }
});

function withBrowser(pathname, storage, run) {
  const saved = { window: global.window, localStorage: global.localStorage, document: global.document };
  global.window = { location: { pathname } };
  global.localStorage = storage;
  delete global.document;
  try {
    return run();
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete global[key]; else global[key] = value;
    }
  }
}

function freshRequire(file) {
  const resolved = require.resolve(path.join(STATIC, file));
  delete require.cache[resolved];
  return require(resolved);
}

test('ticks remember which list they came from, and only real list paths', () => {
  const storage = memoryStorage();
  withBrowser('/essentials/anime', storage, () => {
    const list = freshRequire('essentials.js');
    assert.equal(list.writeTicks(['anime/akira-1988']), true);
    assert.deepEqual(JSON.parse(storage.getItem(list.KEY)), { v: 1, seen: ['anime/akira-1988'], from: '/essentials/anime' });
  });
  withBrowser('/essentials', storage, () => {
    const list = freshRequire('essentials.js');
    list.writeTicks(['anime/akira-1988', 'movie/jaws-1975']);
    assert.equal(JSON.parse(storage.getItem(list.KEY)).from, undefined);
  });
});

test('the importer reads the list back and ignores a tampered path', () => {
  const key = 'omnitrackr_essentials';
  for (const [from, expected] of [['/essentials/books', '/essentials/books'], ['/essentials/books#x', null],
    ['https://example.com/', null], ['/essentials/../admin', null], [42, null]]) {
    const storage = memoryStorage({ [key]: JSON.stringify({ v: 1, seen: ['book/beloved-1987'], from }) });
    withBrowser('/', storage, () => {
      const importer = freshRequire('essentials-import.js');
      assert.equal(importer.readFrom(), expected, String(from));
    });
  }
});

test('empty sections are worked out again for the filter in use', () => {
  const list = freshRequire('essentials.js');
  const section = (items) => {
    const node = {
      classes: new Set(),
      classList: { toggle(name, on) { if (on) node.classes.add(name); else node.classes.delete(name); } },
      querySelectorAll: () => items.map(dataset => ({ dataset })),
    };
    return node;
  };
  const allDone = section([{ esState: 'done', esStarter: '0' }, { esState: 'done', esStarter: '1' }]);
  const someLeft = section([{ esState: 'done', esStarter: '0' }, { esState: '', esStarter: '0' }]);
  const root = { dataset: { esFilter: 'todo' }, querySelectorAll: () => [allDone, someLeft] };
  list.markEmpty(root);
  assert.equal(allDone.classes.has('es-section--empty'), true);
  assert.equal(someLeft.classes.has('es-section--empty'), false);
  root.dataset.esFilter = 'all';
  list.markEmpty(root);
  assert.equal(allDone.classes.has('es-section--empty'), false);
  root.dataset.esFilter = 'starter';
  list.markEmpty(root);
  assert.equal(allDone.classes.has('es-section--empty'), false);
  assert.equal(someLeft.classes.has('es-section--empty'), true);
});

test('focus follows a save to its undo, and back again', () => {
  const js = fs.readFileSync(path.join(STATIC, 'essentials.js'), 'utf8');
  assert.match(js, /const hadFocus = document\.activeElement === button;/);
  assert.match(js, /\(undo \|\| link\)\.focus\(\)/);
  assert.ok(js.includes("undo.setAttribute('aria-label', `Undo adding ${data.title}`);"));
  assert.match(js, /if \(hadFocus\) seen\.focus\(\);/);
});

test('the dashboard toast links back to the list that was ticked', async () => {
  const key = 'omnitrackr_essentials';
  const storage = memoryStorage({ [key]: JSON.stringify({ v: 1, seen: ['movie/jaws-1975'], from: '/essentials/movies' }) });
  const appended = [];
  const make = tag => ({
    tag, children: [], attributes: {}, className: '', textContent: '', href: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); },
    remove() {},
  });
  const saved = { window: global.window, localStorage: global.localStorage, document: global.document, fetch: global.fetch,
    sessionStorage: global.sessionStorage, setTimeout: global.setTimeout };
  const timers = [];
  global.window = { location: { pathname: '/' } };
  global.localStorage = storage;
  global.sessionStorage = memoryStorage();
  global.document = {
    documentElement: { dataset: { publicShell: 'false' } },
    querySelector: () => null,
    getElementById: id => (id === 'startFlow' ? {} : null),
    createElement: make,
    body: { appendChild: node => appended.push(node) },
  };
  global.fetch = async () => ({ ok: true, status: 200, json: async () => ({ added: 1, existing: 0, missing: 0 }) });
  global.setTimeout = (callback, ms) => { timers.push(ms); return 0; };
  try {
    const importer = freshRequire('essentials-import.js');
    const result = await importer.importTicks();
    assert.equal(result.added, 1);
    assert.equal(storage.getItem(key), null);
    const toastNode = appended.find(node => node.className === 'guest-import-toast');
    assert.ok(toastNode, 'a toast was shown');
    const link = toastNode.children.find(node => node.className === 'guest-import-toast__back');
    assert.equal(link.href, '/essentials/movies#your-count');
    assert.equal(link.textContent, 'See your count on the list →');
    assert.ok(timers.includes(15000), 'the toast with a link stays up longer');
  } finally {
    for (const [name, value] of Object.entries(saved)) {
      if (value === undefined) delete global[name]; else global[name] = value;
    }
  }
});

test('ticks left for later keep their list', () => {
  const js = fs.readFileSync(path.join(STATIC, 'essentials-import.js'), 'utf8');
  assert.match(js, /from \? \{ v: 1, seen: left, from \} : \{ v: 1, seen: left \}/);
});
