const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/collection-save.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const ok = data => ({ok: true, status: 200, json: async () => data});
const preview = {collection_name: 'A community collection', version: 'a'.repeat(64), items: [
  {id: 17, title: 'A new title', category: 'movies', category_label: 'Movie', existing: false},
  {id: 21, title: 'An existing title', category: 'books', category_label: 'Book', existing: true},
]};
const saved = {collection_id: 23, created: 1, reused: 1, already_saved: false};
function deferred() { let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve}; }

function setup({respond, id = '7', blockedStorage = false, token = null} = {}) {
  const elements = new Map();
  const requests = [];
  const timers = new Map();
  const events = new Map();
  let timerId = 0;
  function element(tag) {
    const listeners = new Map();
    return {
      tag, children: [], hidden: false, disabled: false, textContent: '', attributes: {},
      append(...children) {this.children.push(...children);},
      replaceChildren(...children) {this.children = children;},
      setAttribute(key, value) {this.attributes[key] = value;},
      addEventListener(key, listener) {listeners.set(key, listener);},
      trigger(key) {return listeners.get(key)?.();},
      focus() {this.focused = true;},
    };
  }
  for (const name of ['Panel', 'Title', 'Summary', 'Status', 'Confirm', 'Signin', 'Retry', 'Open', 'Choices', 'Items', 'All', 'None']) {
    const el = element('div');
    el.hidden = ['Confirm', 'Signin', 'Retry', 'Open', 'Choices'].includes(name);
    el.dataset = {collectionId: id};
    el.href = name === 'Signin' ? '/?next=%2Fcollections%2Fpublic%2F7%2Fsave#landing-auth' : '/';
    elements.set(`collectionSave${name}`, el);
  }
  const context = vm.createContext({
    AbortController,
    document: {getElementById: id => elements.get(id) || null, createElement: element},
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
  return {
    get: name => elements.get(`collectionSave${name}`), requests, timers, events,
    input: index => elements.get('collectionSaveItems').children[index].children[0],
    row: index => elements.get('collectionSaveItems').children[index],
  };
}

test('page opening only previews; selection and version are sent only on explicit confirmation', async () => {
  const s = setup({respond: (url, options) => ok(options.method === 'POST' ? {...saved, reused: 0} : preview)});
  await settle();
  assert.equal(s.requests.length, 1);
  assert.equal(s.requests[0].url, '/collections/public/7/save-preview');
  assert.equal(s.requests[0].options.method, undefined);
  assert.equal(s.requests[0].options.cache, 'no-store');
  assert.equal(s.get('Confirm').hidden, false);
  assert.match(s.get('Summary').textContent, /2 selected · 1 new.*1 already/);
  s.input(1).checked = false;
  s.input(1).trigger('change');
  assert.match(s.get('Summary').textContent, /1 selected · 1 new.*0 already/);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(s.requests[1].options.body), {version: preview.version, item_ids: [17]});
  assert.equal(s.get('Open').href, '/?collection=23');
  assert.equal(s.get('Open').focused, true);
  assert.equal(s.get('Choices').hidden, true);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.timers.size, 0);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests.length, 2, 'completed saves cannot be repeated');
});

test('select all and clear selection update counts and prevent empty saves', async () => {
  const s = setup();
  await settle();
  s.get('None').trigger('click');
  assert.equal(s.get('Confirm').disabled, true);
  assert.equal(s.input(0).checked, false);
  assert.equal(s.input(1).checked, false);
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests.length, 1);
  s.input(1).checked = true;
  s.input(1).trigger('change');
  assert.match(s.get('Summary').textContent, /1 selected · 0 new.*1 already/);
  s.get('All').trigger('click');
  assert.equal(s.get('Confirm').disabled, false);
  assert.equal(s.input(0).checked, true);
  assert.equal(s.input(1).checked, true);
});

test('anonymous preview offers the precise server-provided sign-in link without writing', async () => {
  const s = setup({respond: () => ({ok: false, status: 401})});
  await settle();
  assert.equal(s.get('Signin').hidden, false);
  assert.equal(s.get('Signin').href, '/?next=%2Fcollections%2Fpublic%2F7%2Fsave#landing-auth');
  assert.match(s.get('Status').textContent, /return to this collection/);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.get('Choices').hidden, true);
  assert.equal(s.requests.length, 1);
});

test('a double confirmation and selection changes cannot race a pending save', async () => {
  const pending = deferred();
  const s = setup({respond: (url, options) => options.method === 'POST' ? pending.promise : ok(preview)});
  await settle();
  const saving = s.get('Confirm').trigger('click');
  await s.get('Confirm').trigger('click');
  s.get('None').trigger('click');
  assert.equal(s.requests.length, 2);
  assert.equal(s.input(0).disabled, true);
  assert.equal(s.get('All').disabled, true);
  pending.resolve(ok(saved));
  await saving;
  assert.equal(s.get('Open').href, '/?collection=23');
});

test('uncertain saves retain the identical selection for an explicit safe retry', async () => {
  const s = setup({respond: (url, options, number) => {
    if (number === 2) throw Error('Network disconnected after commit');
    return ok(options.method === 'POST' ? {...saved, already_saved: true, created: 0, reused: 1} : preview);
  }});
  await settle();
  s.input(0).checked = false;
  s.input(0).trigger('change');
  await s.get('Confirm').trigger('click');
  assert.match(s.get('Status').textContent, /couldn’t confirm/);
  assert.equal(s.get('Confirm').textContent, 'Retry save safely');
  assert.equal(s.get('Confirm').hidden, false);
  assert.equal(s.get('Confirm').disabled, false);
  assert.equal(s.get('Retry').hidden, true);
  assert.equal(s.input(0).disabled, true);
  s.get('All').trigger('click');
  await s.get('Retry').trigger('click');
  assert.equal(s.requests.length, 2, 'retrying a preview cannot discard an uncertain save');
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests[2].options.body, s.requests[1].options.body);
  assert.deepEqual(JSON.parse(s.requests[2].options.body).item_ids, [21]);
  assert.match(s.get('Summary').textContent, /already saved this selection.*edits preserved/);
  assert.equal(s.get('Open').href, '/?collection=23');
});

test('a server error after saving preserves the request just like a network failure', async () => {
  const s = setup({respond: (url, options) => options.method === 'POST' ? {ok: false, status: 503} : ok(preview)});
  await settle();
  await s.get('Confirm').trigger('click');
  assert.equal(s.get('Confirm').textContent, 'Retry save safely');
  assert.equal(s.input(0).disabled, true);
  assert.equal(s.get('Retry').hidden, true);
});

test('changed source requires a fresh preview and explicit confirmation; expired sessions require sign-in', async () => {
  for (const code of [401, 409, 422]) {
    const s = setup({respond: (url, options, number) => options.method === 'POST' ? {ok: false, status: code} : ok(number > 2 ? {...preview, version: 'b'.repeat(64)} : preview)});
    await settle();
    await s.get('Confirm').trigger('click');
    assert.equal(s.get('Confirm').hidden, true);
    assert.equal(s.input(0).disabled, true);
    await s.get('Confirm').trigger('click');
    assert.equal(s.requests.length, 2);
    if (code === 401) assert.equal(s.get('Signin').hidden, false);
    else {
      if (code === 409) assert.match(s.get('Status').textContent, /changed since your preview/);
      await s.get('Retry').trigger('click');
      assert.equal(s.requests[2].options.method, undefined);
      assert.equal(s.get('Confirm').hidden, false);
      assert.equal(s.requests.filter(request => request.options.method === 'POST').length, 1);
    }
  }
});

test('removed collections stop both preview and confirmation without restoring stale data', async () => {
  for (const saving of [false, true]) {
    const s = setup({respond: (url, options) => !saving || options.method === 'POST' ? {ok: false, status: 404} : ok(preview)});
    await settle();
    if (saving) await s.get('Confirm').trigger('click');
    assert.match(s.get('Status').textContent, /no longer available/);
    assert.equal(s.get('Choices').hidden, true);
    assert.equal(s.get('Retry').hidden, true);
    assert.equal(s.get('Open').hidden, true);
    assert.equal(s.get('Confirm').hidden, true);
  }
});

test('preview deadline covers fetch and response parsing; late results cannot enable confirmation', async () => {
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
    assert.equal(s.timers.size, 0);
    pending.resolve(body ? preview : ok(preview));
    await settle();
    assert.equal(s.get('Confirm').hidden, true);
  }
});

test('a save deadline preserves its payload and ignores a late successful response', async () => {
  const pending = deferred();
  const s = setup({respond: (url, options) => options.method === 'POST' ? pending.promise : ok(preview)});
  await settle();
  const saving = s.get('Confirm').trigger('click');
  [...s.timers.values()][0].fn();
  await saving;
  assert.equal(s.requests[1].options.signal.aborted, true);
  assert.equal(s.get('Confirm').textContent, 'Retry save safely');
  pending.resolve(ok(saved));
  await settle();
  assert.equal(s.get('Open').hidden, true);
  assert.equal(s.input(0).disabled, true);
  assert.equal(s.get('Confirm').disabled, false);
});

test('browser back during preview rechecks without writing and ignores the old response', async () => {
  const pending = deferred();
  const s = setup({respond: (url, options, number) => number === 1 ? pending.promise : ok(preview)});
  s.events.get('pagehide')();
  await settle();
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.timers.size, 0);
  s.events.get('pageshow')({persisted: true});
  await settle();
  pending.resolve(ok({...preview, collection_name: 'Stale collection'}));
  await settle();
  assert.equal(s.requests.length, 2);
  assert.equal(s.get('Title').textContent, preview.collection_name);
  assert.ok(s.requests.every(r => !r.options.method));
});

test('browser back after an interrupted save keeps exact retry; after success keeps the result', async () => {
  const pending = deferred();
  const s = setup({respond: (url, options, number) => number === 2 ? pending.promise : ok(options.method === 'POST' ? saved : preview)});
  await settle();
  const saving = s.get('Confirm').trigger('click');
  s.events.get('pagehide')();
  await saving;
  s.events.get('pageshow')({persisted: true});
  await settle();
  assert.equal(s.requests.length, 2, 'browser return must not automatically write or forget pending save');
  assert.equal(s.get('Confirm').textContent, 'Retry save safely');
  await s.get('Confirm').trigger('click');
  assert.equal(s.requests[2].options.body, s.requests[1].options.body);
  s.events.get('pagehide')();
  s.events.get('pageshow')({persisted: true});
  assert.equal(s.requests.length, 3);
  assert.equal(s.get('Open').href, '/?collection=23');
});

test('invalid source IDs and malformed preview records cannot enable saving', async () => {
  for (const id of ['0', '7/8', '2147483648', 'javascript:alert(1)']) {
    const s = setup({id});
    assert.equal(s.requests.length, 0);
  }
  const invalid = [null, {...preview, version: 'short'}, {...preview, items: []},
    {...preview, items: [preview.items[0], preview.items[0]]},
    ...[{id: 0}, {category: '//evil.example'}, {existing: 'yes'}, {category_label: 1}, {title: null}].map(change => ({...preview, items: [{...preview.items[0], ...change}]})),
  ];
  for (const data of invalid) {
    const s = setup({respond: () => ok(data)});
    await settle();
    assert.equal(s.get('Confirm').hidden, true);
    assert.equal(s.get('Retry').hidden, false);
  }
});

test('untrusted text uses textContent and malformed save responses cannot create unsafe library links', async () => {
  const text = '<img src=x onerror=alert(1)>';
  const s = setup({respond: () => ok({...preview, collection_name: text, items: [{...preview.items[0], title: text, category_label: text}]})});
  await settle();
  assert.equal(s.get('Title').textContent, text);
  assert.equal(s.row(0).children[1].children[0].textContent, text);
  assert.equal(s.row(0).children[1].children[1].children[0].textContent, text);
  assert.equal(source.includes('innerHTML'), false);
  for (const result of [null, {...saved, collection_id: '//evil.example'}, {...saved, collection_id: 0}, {...saved, already_saved: 'yes'}, {...saved, created: -1}, {...saved, reused: 1.5}]) {
    const s = setup({respond: (url, options) => ok(options.method === 'POST' ? result : preview)});
    await settle();
    await s.get('Confirm').trigger('click');
    assert.equal(s.get('Open').hidden, true);
    assert.equal(s.get('Confirm').textContent, 'Retry save safely');
  }
});

test('cookie authentication works with blocked storage and existing token sessions are supported', async () => {
  const s = setup({blockedStorage: true});
  await settle();
  assert.equal(s.requests[0].options.credentials, 'same-origin');
  assert.equal(s.requests[0].options.headers.Authorization, undefined);
  assert.equal(s.get('Confirm').hidden, false);
  const token = setup({token: 'legacy-session'});
  await settle();
  assert.equal(token.requests[0].options.headers.Authorization, 'Bearer legacy-session');
});

test('public detail offers a real preview link with no automatic copy POST', () => {
  const template = fs.readFileSync(path.join(__dirname, '../app/templates/public_collection.html'), 'utf8');
  const actions = fs.readFileSync(path.join(__dirname, '../app/static/public-collections.js'), 'utf8');
  assert.match(template, /<a href="\/collections\/public\/\{\{COLLECTION_ID\}\}\/save">Save a private copy<\/a>/);
  assert.doesNotMatch(template, /data-collection-action="copy"/);
  assert.doesNotMatch(actions, /\/copy|window\.location/);
  assert.match(actions, /\/helpful/);
  assert.match(actions, /\/report/);
});
