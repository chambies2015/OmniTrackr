// Run with: node --test tests/test_discover_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/discover.js'), 'utf8');
const now = 1900000000000;
const selectionKey = 'omnitrackr_discover_selection:quiet-curiosity';
const items = [
  { key: 'movie-pick', title: 'A quiet film', category: 'Movie', existing: true },
  { key: 'book-pick', title: 'A curious book', category: 'Book', existing: false },
  { key: 'anime-pick', title: 'An animated journey', category: 'Anime', existing: false },
];
const ok = data => ({ ok: true, status: 200, json: async () => data });
const settle = () => new Promise(resolve => setImmediate(resolve));

function setup({ browse = false, hash = '', storage = new Map(), blockedStorage = false, token = null, respond } = {}) {
  const elements = new Map();
  const requests = [];
  function makeElement(tag = 'div') {
    const handlers = new Map();
    return {
      tag, children: [], dataset: {}, attributes: {}, hidden: false, disabled: false,
      value: '', checked: false, _text: '',
      set textContent(value) { this._text = value; this.children = []; },
      get textContent() { return this._text; },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; this._text = ''; },
      setAttribute(name, value) { this.attributes[name] = value; },
      focus() { this.focused = true; },
      addEventListener(name, handler) { handlers.set(name, handler); },
      trigger(name) {
        const event = { target: this, prevented: false, preventDefault() { this.prevented = true; } };
        return handlers.get(name)?.(event);
      },
      querySelectorAll(selector) {
        if (selector !== 'input:checked') throw new Error(`Unexpected selector: ${selector}`);
        const checked = [];
        function visit(element) {
          if (element.tag === 'input' && element.checked) checked.push(element);
          element.children.forEach(visit);
        }
        visit(this);
        return checked;
      },
    };
  }
  function add(id, tag = 'div') {
    const element = makeElement(tag); elements.set(id, element); return element;
  }
  let panel = null;
  const cards = [];
  if (browse) {
    add('trail-filters').hidden = true;
    add('trail-search', 'input');
    const format = add('trail-format', 'select');
    format.options = [{ value: '', text: 'All formats' }, { value: 'books', text: 'Books' }, { value: 'anime', text: 'Anime' }];
    Object.defineProperty(format, 'selectedIndex', { get() { return this.options.findIndex(option => option.value === this.value); } });
    add('trail-reset', 'button'); add('trail-results'); add('trail-empty').hidden = true;
    for (const [search, formats] of [
      ['Café mystery, quiet film and a curious book', 'movies books'],
      ['Quiet journeys through animation', 'anime'],
      ['Curious journeys across games and books', 'video-games books'],
    ]) {
      const card = makeElement('article'); card.dataset = { search, formats }; cards.push(card);
    }
  } else {
    panel = makeElement('section'); panel.dataset.trail = 'quiet-curiosity';
    add('status');
    const form = add('saveForm', 'form'); form.hidden = true;
    const choices = add('choices', 'fieldset'); form.append(choices);
    add('preview', 'button'); add('save', 'button'); add('signin', 'a').hidden = true;
  }
  const context = vm.createContext({
    Date: { now: () => now },
    window: { location: { hash } },
    document: {
      getElementById: id => elements.get(id) || null,
      createElement: makeElement,
      querySelector: selector => selector === '[data-trail]' ? panel : null,
      querySelectorAll: selector => selector === '.trail[data-search]' ? cards : [],
    },
    sessionStorage: {
      getItem(key) { if (blockedStorage) throw new Error('Storage blocked'); return storage.get(key) ?? null; },
      setItem(key, value) { if (blockedStorage) throw new Error('Storage blocked'); storage.set(key, value); },
      removeItem(key) { if (blockedStorage) throw new Error('Storage blocked'); storage.delete(key); },
    },
    localStorage: { getItem: key => key === 'omnitrackr_token' ? token : null },
    fetch: (url, options) => {
      requests.push({ url, options });
      return Promise.resolve(respond ? respond(url, options) : ok({ items }));
    },
  });
  vm.runInContext(source, context);
  const inputs = () => (elements.get('choices')?.children || [])
    .flatMap(label => label.children).filter(element => element.tag === 'input');
  return { context, elements, requests, storage, cards, panel, inputs,
    get: id => elements.get(id),
    choose: keys => inputs().forEach(input => { input.checked = keys.includes(input.value); }),
  };
}

test('trail filters combine every search term with format and reset without any network request', () => {
  const s = setup({ browse: true });
  assert.equal(s.get('trail-filters').hidden, false);
  assert.equal(s.get('trail-results').textContent, '3 of 3 trails');
  s.get('trail-search').value = '  CAFE   quiet  ';
  s.get('trail-search').trigger('input');
  assert.deepEqual(s.cards.map(card => card.hidden), [false, true, true]);
  s.get('trail-search').value = 'curious';
  s.get('trail-search').trigger('input');
  s.get('trail-format').value = 'books';
  s.get('trail-format').trigger('change');
  assert.deepEqual(s.cards.map(card => card.hidden), [false, true, false]);
  assert.equal(s.get('trail-results').textContent, '2 of 3 trails including Books');
  s.get('trail-format').value = 'anime';
  s.get('trail-format').trigger('change');
  assert.deepEqual(s.cards.map(card => card.hidden), [true, true, true]);
  assert.equal(s.get('trail-empty').hidden, false);
  assert.equal(s.get('trail-results').textContent, '0 of 3 trails including Anime');
  s.get('trail-reset').trigger('click');
  assert.equal(s.get('trail-search').value, '');
  assert.equal(s.get('trail-format').value, '');
  assert.equal(s.get('trail-search').focused, true);
  assert.equal(s.get('trail-empty').hidden, true);
  assert.deepEqual(s.cards.map(card => card.hidden), [false, false, false]);
  assert.equal(s.requests.length, 0);
});

test('return anchor automatically previews matches but never saves them', async () => {
  const s = setup({ hash: '#save-picks' });
  await settle();
  assert.equal(s.requests.length, 1);
  assert.equal(s.requests[0].url, '/api/discover/quiet-curiosity/preview');
  assert.equal(s.requests[0].options.method, undefined);
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.equal(s.get('saveForm').hidden, false);
  assert.deepEqual(s.inputs().map(input => input.value), items.map(item => item.key));
  assert.equal(s.inputs().every(input => input.checked), true);
  assert.match(s.get('choices').children[1].children[1].textContent, /Reuse existing title match/);
  assert.match(s.get('choices').children[2].children[1].textContent, /unfinished and unrated/);
  assert.match(s.get('status').textContent, /Nothing has been added/);
  assert.equal(s.panel.attributes['aria-busy'], 'false');
  assert.equal(s.storage.size, 0);
});

test('ordinary detail visit waits for preview and an explicit subset save leads to that collection', async () => {
  const s = setup({ respond: url => url.endsWith('/save') ? ok({ created: 1, reused: 1, collection_id: 42 }) : ok({ items }) });
  assert.equal(s.requests.length, 0);
  await s.get('preview').trigger('click');
  s.choose(['movie-pick', 'anime-pick']);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 2);
  assert.equal(s.requests[1].url, '/api/discover/quiet-curiosity/save');
  assert.equal(s.requests[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(s.requests[1].options.body), { keys: ['movie-pick', 'anime-pick'] });
  assert.match(s.get('status').textContent, /1 new titles; 1 existing titles reused/);
  const link = s.get('status').children[0];
  assert.equal(link.href, '/?collection=42');
  assert.equal(link.focused, true);
  assert.equal(s.get('saveForm').hidden, true);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 2, 'submitting a hidden success form must not save again');
});

test('empty selection stays visible and submits nothing', async () => {
  const s = setup();
  await s.get('preview').trigger('click');
  s.choose([]);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 1);
  assert.match(s.get('status').textContent, /Select at least one/);
  assert.equal(s.get('saveForm').hidden, false);
  assert.equal(s.get('save').disabled, false);
});

test('preview and save lock both controls and ignore overlapping requests', async () => {
  const pending = [];
  const s = setup({ respond: () => new Promise(resolve => pending.push(resolve)) });
  const firstPreview = s.get('preview').trigger('click');
  assert.equal(s.get('preview').disabled, true);
  assert.equal(s.get('save').disabled, true);
  assert.equal(s.get('choices').disabled, true);
  await s.get('preview').trigger('click');
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 1);
  pending.shift()(ok({ items }));
  await firstPreview;
  s.choose(['book-pick']);
  const firstSave = s.get('saveForm').trigger('submit');
  assert.equal(s.panel.attributes['aria-busy'], 'true');
  await s.get('preview').trigger('click');
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 2);
  pending.shift()(ok({ created: 1, reused: 0, collection_id: 8 }));
  await firstSave;
  assert.equal(s.get('preview').disabled, false);
  assert.equal(s.get('save').disabled, false);
  assert.equal(s.get('choices').disabled, false);
  assert.equal(s.panel.attributes['aria-busy'], 'false');
});

test('failed saves preserve checked choices and let the reader retry', async () => {
  for (const failure of ['http', 'network']) {
    let saveAttempts = 0;
    const s = setup({ respond: url => {
      if (url.endsWith('/preview')) return ok({ items });
      saveAttempts++;
      if (saveAttempts > 1) return ok({ created: 1, reused: 0, collection_id: 12 });
      if (failure === 'network') return Promise.reject(new Error('Connection lost'));
      return { ok: false, status: 503 };
    } });
    await s.get('preview').trigger('click');
    s.choose(['book-pick']);
    await s.get('saveForm').trigger('submit');
    assert.equal(s.get('saveForm').hidden, false, failure);
    assert.deepEqual(s.inputs().filter(input => input.checked).map(input => input.value), ['book-pick']);
    assert.equal(s.get('save').disabled, false);
    assert.match(s.get('status').textContent, failure === 'network' ? /Connection lost/ : /Please try again/);
    await s.get('saveForm').trigger('submit');
    assert.deepEqual(JSON.parse(s.requests.at(-1).options.body), { keys: ['book-pick'] });
    assert.equal(s.get('status').children[0].href, '/?collection=12');
  }
});

test('session expiration retains only public selection keys, then restores them in a read-only return preview', async () => {
  const s = setup({ token: 'legacy-session-token', respond: url => url.endsWith('/save') ? { ok: false, status: 401 } : ok({ items }) });
  await s.get('preview').trigger('click');
  s.choose(['book-pick']);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.get('signin').hidden, false);
  assert.equal(s.get('saveForm').hidden, true);
  assert.equal(s.get('save').disabled, false);
  assert.match(s.get('status').textContent, /Sign in to continue/);
  assert.equal(s.storage.size, 1);
  assert.deepEqual(JSON.parse(s.storage.get(selectionKey)), { at: now, keys: ['book-pick'] });
  assert.equal(s.requests[0].options.headers.Authorization, 'Bearer legacy-session-token');
  const returning = setup({ hash: '#save-picks', storage: s.storage });
  await settle();
  assert.deepEqual(returning.inputs().filter(input => input.checked).map(input => input.value), ['book-pick']);
  assert.equal(returning.requests.length, 1);
  assert.equal(returning.requests[0].options.method, undefined);
  assert.equal(returning.get('signin').hidden, true);
  assert.equal(returning.storage.size, 0);
});

test('an unauthenticated initial preview exposes sign-in without storing account or library information', async () => {
  const s = setup({ hash: '#save-picks', respond: () => ({ ok: false, status: 401 }) });
  await settle();
  assert.equal(s.get('signin').hidden, false);
  assert.equal(s.get('saveForm').hidden, true);
  assert.equal(s.storage.size, 0);
  assert.equal(s.inputs().length, 0);
  assert.equal(s.requests.length, 1);
});

test('expired, future, and malformed stored selections are ignored', async () => {
  const invalidValues = [
    'not json', 'null', '{}',
    JSON.stringify({ at: now - 86400000, keys: ['book-pick'] }),
    JSON.stringify({ at: now + 1, keys: ['book-pick'] }),
    JSON.stringify({ at: String(now), keys: ['book-pick'] }),
    JSON.stringify({ at: now, keys: 'book-pick' }),
    JSON.stringify({ at: now, keys: [3] }),
    JSON.stringify({ at: now, keys: Array(7).fill('book-pick') }),
  ];
  for (const value of invalidValues) {
    const s = setup({ hash: '#save-picks', storage: new Map([[selectionKey, value]]) });
    await settle();
    assert.equal(s.inputs().every(input => input.checked), true, value);
    assert.equal(s.requests.length, 1, value);
    assert.equal(s.get('saveForm').hidden, false, value);
  }
});

test('saved selection is scoped to its trail and cannot introduce nonexistent picks', async () => {
  const otherKey = 'omnitrackr_discover_selection:another-trail';
  const storage = new Map([
    [selectionKey, JSON.stringify({ at: now, keys: ['missing-pick'] })],
    [otherKey, JSON.stringify({ at: now, keys: ['book-pick'] })],
  ]);
  const s = setup({ hash: '#save-picks', storage });
  await settle();
  assert.equal(s.inputs().some(input => input.checked), false);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 1);
  assert.equal(storage.has(otherKey), true);
});

test('blocked browser storage still permits read-only preview and explicit save', async () => {
  const s = setup({ blockedStorage: true, hash: '#save-picks', respond: url => url.endsWith('/save') ? ok({ created: 1, reused: 0, collection_id: 9 }) : ok({ items }) });
  await settle();
  s.choose(['anime-pick']);
  await s.get('saveForm').trigger('submit');
  assert.equal(s.requests.length, 2);
  assert.equal(s.get('status').children[0].href, '/?collection=9');
});
