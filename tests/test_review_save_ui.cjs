const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/review-save.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const ok = data => ({ok: true, status: 200, json: async () => data});
const preview = {title: 'A community find', category: 'movie', library_category: 'movies', version: 'public-metadata-version', existing: false};
const saved = {created: true, reused: false, item_id: 23, category: 'movies', title: preview.title};
function deferred() { let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve}; }

function setup({respond, category = 'movie', id = '7', blockedStorage = false, token = null} = {}) {
  const elements = new Map();
  const requests = [];
  const timers = new Map();
  const events = new Map();
  let timerId = 0;
  for (const name of ['Panel', 'Title', 'Summary', 'Status', 'Confirm', 'Signin', 'Retry', 'Open']) {
    const listeners = new Map();
    elements.set(`reviewSave${name}`, {
      hidden: ['Confirm', 'Signin', 'Retry', 'Open'].includes(name), disabled: false,
      textContent: '', href: name === 'Signin' ? '/?next=%2Freviews%2F7%2Fsave%3Fcategory%3Dmovie#landing-auth' : '/',
      dataset: {category, reviewId: id}, attributes: {},
      setAttribute(key, value) {this.attributes[key] = value;},
      addEventListener(key, listener) {listeners.set(key, listener);},
      trigger(key) {return listeners.get(key)?.();},
      focus() {this.focused = true;},
    });
  }
  const context = vm.createContext({
    AbortController, encodeURIComponent,
    document: {getElementById: id => elements.get(id) || null},
    window: {addEventListener: (name, listener) => events.set(name, listener)},
    localStorage: {getItem() {if (blockedStorage) throw Error('Blocked'); return token;}},
    setTimeout: (fn, delay) => {const id = ++timerId; timers.set(id, {fn, delay}); return id;},
    clearTimeout: id => timers.delete(id),
    fetch: (url, options) => {
      requests.push({url, options});
      return Promise.resolve(respond ? respond(url, options, requests.length) : ok(preview));
    },
  });
  vm.runInContext(source, context);
  return {get: name => elements.get(`reviewSave${name}`), requests, timers, events};
}

test('opening a save page only previews; an explicit confirmation sends the metadata version', async () => {
  const s = setup({respond: (url, options) => ok(options.method === 'POST' ? saved : preview)});
  await settle();
  assert.equal(s.requests.length, 1);
  assert.equal(s.requests[0].url, '/api/public/reviews/7/save-preview?category=movie');
  assert.equal(s.requests[0].options.method, undefined);
  assert.equal(s.get('Confirm').hidden, false);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(s.requests[1].options.body), {version: preview.version});
  assert.equal(s.get('Open').href, '/?library_category=movies&library_item=23');
  assert.equal(s.get('Open').focused, true);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.timers.size, 0);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests.length, 2, 'a completed save cannot be resubmitted');
});

test('existing library match offers its exact item without a save or copied personal fields', async () => {
  const s = setup({respond: () => ok({...preview, existing: true, item_id: 91})});
  await settle();
  assert.equal(s.get('Open').href, '/?library_category=movies&library_item=91');
  assert.match(s.get('Summary').textContent, /notes, rating and progress are preserved/);
  assert.equal(s.get('Confirm').hidden, true);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests.length, 1);
});

test('anonymous preview offers the server-provided login return link and performs no write', async () => {
  const s = setup({respond: () => ({ok: false, status: 401})});
  await settle();
  assert.equal(s.get('Signin').hidden, false);
  assert.match(s.get('Signin').href, /next=/);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.requests.length, 1);
});

test('a double confirmation cannot race two saves', async () => {
  const response = deferred();
  const s = setup({respond: (url, options) => options.method === 'POST' ? response.promise : ok(preview)});
  await settle();
  const saving = s.get('Confirm').trigger('click');
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests.length, 2);
  response.resolve(ok(saved));
  await saving;
});

test('an uncertain save requires a new read-only preview before any retry', async () => {
  let calls = 0;
  const s = setup({respond: () => {
    calls++;
    if (calls === 2) throw Error('Network disconnected after commit');
    return ok(calls === 3 ? {...preview, existing: true, item_id: 23} : preview);
  }});
  await settle();
  await s.get('Confirm').trigger('click');
  assert.match(s.get('Status').textContent, /couldn’t confirm/);
  assert.equal(s.get('Confirm').hidden, true);
  await s.get('Retry').trigger('click');
  assert.equal(s.requests[2].options.method, undefined);
  assert.equal(s.get('Open').href, '/?library_category=movies&library_item=23');
  assert.equal(s.requests.filter(r => r.options.method === 'POST').length, 1);
});

test('changed metadata and expired sessions invalidate the previous confirmation', async () => {
  for (const code of [401, 409]) {
    const s = setup({respond: (url, options) => options.method === 'POST' ? {ok: false, status: code} : ok(preview)});
    await settle();
    await s.get('Confirm').trigger('click');
    assert.equal(s.get('Confirm').hidden, true);
    await s.get('Confirm').trigger('click');
    assert.equal(s.requests.length, 2);
    if (code === 401) assert.equal(s.get('Signin').hidden, false);
    else assert.match(s.get('Status').textContent, /changed since your preview/);
  }
});

test('a removed public review stops saving and offers no retry that could restore old data', async () => {
  const s = setup({respond: () => ({ok: false, status: 404})});
  await settle();
  assert.match(s.get('Status').textContent, /no longer available/);
  assert.equal(s.get('Retry').hidden, true);
  assert.equal(s.get('Open').hidden, true);
});

test('deadline covers fetch and body parsing even when transport ignores cancellation', async () => {
  for (const body of [false, true]) {
    const pending = deferred();
    const s = setup({respond: () => body ? {ok: true, json: () => pending.promise} : pending.promise});
    await settle();
    const timer = [...s.timers.values()][0];
    assert.equal(timer.delay, 15000);
    timer.fn();
    await settle();
    assert.equal(s.requests[0].options.signal.aborted, true);
    assert.equal(s.get('Retry').hidden, false);
    assert.equal(s.get('Confirm').disabled, false);
    assert.equal(s.timers.size, 0);
    pending.resolve(body ? preview : ok(preview));
    await settle();
    assert.equal(s.get('Confirm').hidden, true, 'late data cannot restore timed-out preview');
  }
});

test('page departure cancels work; browser back checks library again without an automatic save', async () => {
  const pending = deferred();
  const s = setup({respond: (url, options, number) => number === 1 ? pending.promise : ok(preview)});
  s.events.get('pagehide')();
  await settle();
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.timers.size, 0);
  s.events.get('pageshow')({persisted: true});
  await settle();
  pending.resolve(ok({...preview, existing: true, item_id: 99}));
  await settle();
  assert.equal(s.requests.length, 2);
  assert.equal(s.get('Confirm').hidden, false);
  assert.equal(s.get('Open').hidden, true);
  assert.ok(s.requests.every(r => !r.options.method));
});

test('untrusted identifiers or mismatched response categories cannot produce library links', async () => {
  for (const options of [{category: 'constructor'}, {category: '../account'}, {id: '0'}, {id: '7/8'}, {id: '2147483648'}]) {
    const s = setup(options);
    assert.equal(s.requests.length, 0);
  }
  for (const data of [{...preview, existing: true, item_id: -1}, {...preview, category: 'book'}, {...preview, library_category: '//evil.example'}, {...preview, existing: 'yes'}]) {
    const s = setup({respond: () => ok(data)});
    await settle();
    assert.equal(s.get('Open').hidden, true);
    assert.equal(s.get('Confirm').hidden, true);
    assert.equal(s.get('Retry').hidden, false);
  }
});

test('all categories produce their correct library target and cookie authentication works with blocked storage', async () => {
  for (const [category, library_category] of Object.entries({movie: 'movies', tv_show: 'tv-shows', anime: 'anime', video_game: 'video-games', music: 'music', book: 'books'})) {
    const s = setup({category, blockedStorage: true, respond: () => ok({...preview, category, library_category, existing: true, item_id: 3})});
    await settle();
    assert.equal(s.get('Open').href, `/?library_category=${library_category}&library_item=3`);
    assert.equal(s.requests[0].options.credentials, 'same-origin');
    assert.equal(s.requests[0].options.headers.Authorization, undefined);
  }
  const s = setup({token: 'legacy-session'});
  assert.equal(s.requests[0].options.headers.Authorization, 'Bearer legacy-session');
  await settle();
});
