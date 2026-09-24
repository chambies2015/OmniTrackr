const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../app/static/progress.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../app/templates/index.html'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const tick = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function checkpoint(overrides = {}) { return { unit: 'episode', position: 7, season: 2, note: 'Remember this detail', revision: 1, updated_at: '2026-09-22T12:00:00Z', ...overrides }; }
function result(overrides = {}, status = 200) {
  const payload = { category: 'tv-shows', item_id: 42, title: 'A private title', revision: 1, checkpoint: checkpoint(), ...overrides };
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}
function setup() {
  let focused = null, account = 'account-1', tab = 'tv-shows', allowed = true;
  const docEvents = new Map(), winEvents = new Map(), requests = [], responses = [], saved = [], confirmations = [], timers = new Map();
  let nextTimer = 1;
  class Element {
    constructor(tag = 'div') { this.tagName = tag; this.value = ''; this.children = []; this.dataset = {}; this.events = new Map(); this.hidden = false; this.disabled = false; this.isConnected = true; this._text = ''; this.attributes = {}; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set innerHTML(_) { throw new Error('Private progress must render text safely.'); }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.children.push(node); }
    replaceChildren(...nodes) { this.children = nodes; this._text = ''; }
    setAttribute(key, value) { this.attributes[key] = value; }
    removeAttribute(key) { delete this.attributes[key]; if (key === 'hidden') this.hidden = false; }
    addEventListener(name, callback) { this.events.set(name, callback); }
    focus() { focused = this; }
    showModal() { this.open = true; }
    close() { this.open = false; }
    trigger(name, extra = {}) { const event = { preventDefault() {}, ...extra }; this.events.get(name)?.(event); }
  }
  const nodes = new Map([...template.matchAll(/\bid="(progress[^"]+)"/g)].map(match => [match[1], new Element()]));
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const descendants = node => node.children.flatMap(child => [child, ...descendants(child)]);
  const context = vm.createContext({
    AbortController, Promise, console,
    document: { getElementById: get, createElement: tag => new Element(tag), activeElement: null,
      addEventListener: (name, callback) => docEvents.set(name, callback),
      querySelectorAll: () => [...nodes.values()].flatMap(node => [node, ...descendants(node)]).filter(node => node.dataset.progressSummaryCategory) },
    window: { addEventListener: (name, callback) => winEvents.set(name, callback),
      setTimeout: callback => { const id = nextTimer++; timers.set(id, callback); return id; }, clearTimeout: id => timers.delete(id),
      confirm: message => { confirmations.push(message); return true; } },
  });
  vm.runInContext(script, context);
  const api = context.window.OmniProgress;
  api.configure({ sessionKey: () => account, contextKey: () => tab, canOpen: () => allowed,
    request: async (url, options) => { requests.push({ url, options }); const response = responses.shift(); if (response instanceof Error) throw response; return response ?? result(); },
    onSaved: (payload, guard) => saved.push({ payload, guard }),
  });
  const opener = new Element('button');
  return { api, get, context, requests, responses, saved, confirmations, opener, focused: () => focused, descendants,
    setAccount: value => { account = value; }, setTab: value => { tab = value; }, setAllowed: value => { allowed = value; },
    open: async (category = 'tv-shows', id = 42) => { api.open(category, id, 'A private title', opener); await tick(); },
    submit: async () => { get('progressForm').trigger('submit'); await tick(); },
    click: async id => { get(id).trigger('click'); await tick(); },
    event: async (name, event = {}) => { (winEvents.get(name) || docEvents.get(name))?.(event); await tick(); },
    timeout: async () => { [...timers.values()].forEach(callback => callback()); await tick(); },
    tick,
  };
}

test('opening reads a checkpoint without writing and labels the last completed episode', async () => {
  const s = setup(); await s.open();
  assert.equal(s.requests.length, 1); assert.equal(s.requests[0].options.method, 'GET');
  assert.equal(s.requests[0].url, '/progress/tv-shows/42');
  assert.equal(s.get('progressPosition').value, '7'); assert.equal(s.get('progressSeason').value, '2');
  assert.equal(s.get('progressNote').value, 'Remember this detail');
  assert.equal(s.get('progressPositionLabel').textContent, 'Last watched episode');
  assert.match(s.get('progressCurrent').textContent, /Season 2, episode 7/);
  assert.equal(s.get('progressDialog').open, true);
  assert.equal(s.get('progressFields').disabled, false);
});

test('only supported own-library media are editable and active title edits are protected', async () => {
  const s = setup(); await s.open('movies'); await s.open('books', -1); await s.open('anime', 1.1);
  await s.open('anime', 2147483648);
  s.setAllowed(false); await s.open();
  assert.equal(s.requests.length, 0);
});

test('explicit save submits only checkpoint fields with the read revision and no completion mutation', async () => {
  const s = setup(); await s.open();
  s.get('progressPosition').value = '8'; s.get('progressSeason').value = '0';
  s.get('progressNote').value = '<script>private & literal</script>';
  s.responses.push(result({ revision: 2, checkpoint: checkpoint({ position: 8, season: 0, note: '<script>private & literal</script>', revision: 2 }) }));
  await s.submit();
  assert.equal(s.requests.length, 2);
  assert.equal(s.requests[1].options.method, 'PUT');
  assert.deepEqual(JSON.parse(s.requests[1].options.body), { expected_revision: 1, unit: 'episode', position: 8, season: 0, note: '<script>private & literal</script>' });
  assert.equal(s.saved.length, 1); assert.equal(s.saved[0].guard(), true);
  assert.match(s.get('progressCurrent').textContent, /Specials, episode 8/);
  assert.match(s.get('progressStatus').textContent, /finished status is unchanged/);
});

test('books support pages or chapters, and an empty tombstone retains its revision', async () => {
  const s = setup(); s.responses.push(result({ category: 'books', checkpoint: null, revision: 5 })); await s.open('books');
  assert.equal(s.get('progressSeasonField').hidden, true); assert.equal(s.get('progressUnitField').hidden, false);
  s.get('progressUnit').value = 'chapter'; s.get('progressUnit').trigger('change'); s.get('progressPosition').value = '12';
  assert.equal(s.get('progressPositionLabel').textContent, 'Last read chapter');
  s.responses.push(result({ category: 'books', revision: 6, checkpoint: checkpoint({ unit: 'chapter', season: null, position: 12, revision: 6 }) }));
  await s.submit();
  assert.deepEqual(JSON.parse(s.requests[1].options.body), { expected_revision: 5, unit: 'chapter', position: 12, season: null, note: null });
});

test('invalid positions, seasons and notes never send a write', async () => {
  const s = setup(); await s.open();
  for (const value of ['0', '-1', '1.5', '1000001', '', '1e3']) { s.get('progressPosition').value = value; await s.submit(); }
  s.get('progressPosition').value = '8'; s.get('progressSeason').value = '10001'; await s.submit();
  s.get('progressSeason').value = '2'; s.get('progressNote').value = 'x'.repeat(301); await s.submit();
  assert.equal(s.requests.length, 1);
});

test('a browser-invalid optional season is not mistaken for intentionally clearing the season', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '8';
  s.get('progressSeason').value = ''; s.get('progressSeason').validity = { badInput: true };
  await s.submit(); assert.equal(s.requests.length, 1); assert.match(s.get('progressStatus').textContent, /Enter a season/);
  s.get('progressSeason').validity.badInput = false; await s.submit();
  assert.equal(s.requests.length, 2); assert.equal(JSON.parse(s.requests[1].options.body).season, null);
});

test('Escape restores focus and closing retains a dirty draft only in this tab', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '11'; s.get('progressNote').value = 'Unsaved';
  s.get('progressDialog').trigger('cancel');
  assert.equal(s.get('progressDialog').open, false); assert.equal(s.focused(), s.opener);
  await s.open();
  assert.equal(s.requests.length, 1); assert.equal(s.get('progressPosition').value, '11'); assert.equal(s.get('progressNote').value, 'Unsaved');
  assert.match(s.get('progressStatus').textContent, /draft is restored/);
  assert.doesNotMatch(script, /localStorage|sessionStorage|sendBeacon/);
});

test('a clean close reloads from the server on the next open', async () => {
  const s = setup(); await s.open(); await s.click('progressClose'); await s.open();
  assert.equal(s.requests.length, 2); assert.ok(s.requests.every(request => request.options.method === 'GET'));
});

test('closing restores focus to the refreshed queue action when its old button was replaced', async () => {
  const s = setup(); const replacement = s.get('replacement-action');
  s.opener.closest = () => ({ querySelector: selector => selector.includes('42') ? replacement : null });
  await s.open(); s.opener.isConnected = false; await s.click('progressClose');
  assert.equal(s.focused(), replacement);
});

test('an uncertain save freezes edits and retries the exact same request', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '9'; s.responses.push(new Error('network'));
  await s.submit();
  assert.equal(s.get('progressFields').disabled, true); assert.equal(s.get('progressRetry').hidden, false);
  assert.equal(s.get('progressSave').disabled, true); assert.match(s.get('progressStatus').textContent, /could not be confirmed/);
  s.responses.push(result({ revision: 2, checkpoint: checkpoint({ position: 9, revision: 2 }) }));
  await s.click('progressRetry');
  assert.equal(s.requests[1].options.body, s.requests[2].options.body);
  assert.equal(s.requests[1].options.method, s.requests[2].options.method);
  assert.equal(s.saved.length, 1); assert.equal(s.get('progressFields').disabled, false);
});

test('conflict preserves the draft and requires explicit reload before saving again', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '9'; s.responses.push(result({}, 409)); await s.submit();
  assert.equal(s.get('progressPosition').value, '9'); assert.equal(s.get('progressSave').disabled, true);
  assert.equal(s.get('progressReload').hidden, false); assert.equal(s.get('progressRetry').hidden, true);
  await s.submit(); assert.equal(s.requests.length, 2);
  s.responses.push(result({ revision: 3, checkpoint: checkpoint({ position: 10, revision: 3 }) }));
  await s.click('progressReload');
  assert.equal(s.confirmations.length, 1); assert.equal(s.get('progressPosition').value, '10');
  assert.equal(s.get('progressSave').disabled, false); assert.equal(s.requests[2].options.method, 'GET');
  assert.equal(s.saved.length, 0);
});

test('explicit clear submits only the revision and keeps all title metadata untouched', async () => {
  const s = setup(); await s.open(); s.responses.push(result({ revision: 2, checkpoint: null })); await s.click('progressClear');
  assert.equal(s.confirmations.length, 1); assert.equal(s.requests[1].options.method, 'DELETE');
  assert.deepEqual(JSON.parse(s.requests[1].options.body), { expected_revision: 1 });
  assert.equal(s.get('progressPosition').value, ''); assert.equal(s.get('progressClear').hidden, true);
  assert.match(s.get('progressStatus').textContent, /ratings, reviews and finished status are unchanged/);
});

test('closing during an explicit conflict reload cannot strand a locked draft on reopening', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '9'; s.responses.push(result({}, 409)); await s.submit();
  await s.click('progressClose'); await s.open();
  const delayed = deferred(); s.responses.push(delayed.promise); await s.click('progressReload'); await s.click('progressClose');
  s.responses.push(result({ revision: 3, checkpoint: checkpoint({ position: 12, revision: 3 }) })); await s.open();
  delayed.resolve(result()); await tick();
  assert.equal(s.get('progressFields').disabled, false); assert.equal(s.get('progressPosition').value, '12');
  assert.equal(s.requests.length, 4);
});

test('late reads cannot overwrite another title and page navigation preserves the old draft', async () => {
  const s = setup(); const delayed = deferred(); s.responses.push(delayed.promise); await s.open();
  s.responses.push(result({ category: 'books', item_id: 99, title: 'Second book', checkpoint: checkpoint({ unit: 'page', position: 51 }) }));
  await s.open('books', 99); delayed.resolve(result()); await tick();
  assert.equal(s.get('progressTitle').textContent, 'Second book'); assert.equal(s.get('progressPosition').value, '51');
  s.get('progressPosition').value = '52'; s.api.navigate(); s.setTab('anime'); await s.open('books', 99);
  assert.equal(s.get('progressPosition').value, '52'); assert.equal(s.requests.length, 2);
});

test('closing an in-flight save retains a retry without applying a late response', async () => {
  const s = setup(); await s.open(); s.get('progressPosition').value = '9'; const delayed = deferred(); s.responses.push(delayed.promise);
  await s.submit(); await s.click('progressClose'); delayed.resolve(result({ revision: 2 })); await tick();
  assert.equal(s.saved.length, 0); await s.open();
  assert.equal(s.get('progressRetry').hidden, false); assert.equal(s.get('progressPosition').value, '9');
  assert.equal(s.requests.length, 2);
});

test('deadline covers stalled requests and permits a bounded explicit retry', async () => {
  const s = setup(); s.responses.push(deferred().promise); await s.open(); await s.timeout();
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.get('progressReload').hidden, false); assert.equal(s.get('progressReload').disabled, false);
  await s.click('progressReload'); assert.equal(s.requests.length, 2); assert.equal(s.get('progressFields').disabled, false);
});

test('account changes and pagehide erase drafts and reject late private results', async () => {
  const s = setup(); await s.open(); s.get('progressNote').value = 'Account one draft'; s.api.close();
  s.setAccount('account-2'); await s.event('storage', { key: 'omnitrackr_user' });
  assert.equal(s.get('progressNote').value, '');
  const delayed = deferred(); s.responses.push(delayed.promise); await s.open(); await s.event('pagehide'); delayed.resolve(result()); await tick();
  assert.equal(s.get('progressTitle').textContent, ''); assert.equal(s.get('progressDialog').open, false); assert.equal(s.saved.length, 0);
  await s.open(); assert.equal(s.requests.length, 3);
});

test('same-tab authentication expiry immediately closes the progress editor and erases its draft', async () => {
  const s = setup(); await s.open(); s.get('progressNote').value = 'Private unsaved reminder';
  s.api.close(); await s.open();
  assert.equal(s.get('progressNote').value, 'Private unsaved reminder');
  const auth = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
  const clearAuth = auth.slice(auth.indexOf('function clearAuth('), auth.indexOf('function isAuthenticated('));
  Object.assign(s.context, {
    TOKEN_KEY: 'omnitrackr_token', USER_KEY: 'omnitrackr_user', RETURN_PROMPT_KEY: 'return-prompt',
    localStorage: { removeItem: () => s.setAccount(null) },
    sessionStorage: { removeItem: () => {} },
    clearDiscoverAuthReturn: () => { throw new Error('Expired sessions must retain their chosen return destination.'); },
    clearDemoStartIntent: () => {},
  });
  vm.runInContext(clearAuth + '\nclearAuth({ preserveReturn: true });', s.context);
  // A localStorage mutation in the originating tab emits no storage event.
  assert.equal(s.get('progressDialog').open, false);
  assert.equal(s.get('progressNote').value, '');
  assert.equal(s.get('progressTitle').textContent, '');
  s.setAccount('account-1'); await s.open();
  assert.equal(s.requests.length, 2);
  assert.equal(s.get('progressNote').value, 'Remember this detail');
});

test('saved refresh guards become false on navigation, logout or pagehide', async () => {
  for (const invalidate of [s => s.api.navigate(), s => s.setAccount(null), s => s.event('pagehide')]) {
    const s = setup(); await s.open(); s.get('progressPosition').value = '8'; await s.submit();
    assert.equal(s.saved[0].guard(), true); await invalidate(s); assert.equal(s.saved[0].guard(), false);
  }
});

test('summary cards expose location without private reminders and queue actions use the media item id', () => {
  const s = setup(); const root = s.get('summary-test');
  const item = { id: 100, item_id: 42, category: 'tv-shows', title: '<script>literal title</script>', progress: checkpoint({ note: 'Never show this reminder in cards' }) };
  s.api.appendSummary(root, item); s.api.appendAction(root, item);
  assert.match(root.textContent, /Last watched/); assert.doesNotMatch(root.textContent, /Never show/);
  assert.equal(root.children[1].dataset.progressItemId, '42');
  assert.equal(root.children[1].attributes['aria-label'], 'Update progress for <script>literal title</script>');
  const blank = s.get('blank-summary'); s.api.appendSummary(blank, { ...item, progress: null }); assert.equal(blank.children[0].hidden, true);
  s.api.appendAction(root, { ...item, category: 'movies' }); assert.equal(root.children.length, 2);
});

test('Continue, Next Up and Welcome Back integrate checkpoint actions without nesting buttons', () => {
  const s = setup();
  vm.runInContext(app.slice(app.indexOf('function renderLibraryPulseList('), app.indexOf('function renderLibraryPulse(')), s.context);
  vm.runInContext(app.slice(app.indexOf('function renderNextUpQueue('), app.indexOf('async function refreshNextUpQueue(')), s.context);
  vm.runInContext('let returnDeckItems = [];\n' + app.slice(app.indexOf('function makeReturnDeckItem('), app.indexOf('function renderReturnDeck(')), s.context);
  const item = { id: 42, category: 'tv-shows', category_label: 'TV show', title: 'A title', status_label: 'In progress', progress: checkpoint() };
  const pulse = s.get('pulse'); s.context.renderLibraryPulseList(pulse, [item], 'Nothing here');
  assert.equal(pulse.children[0].children[1].dataset.progressItemId, '42');
  assert.equal(pulse.children[0].children[0].children.some(node => node.tagName === 'button'), false);
  s.context.renderNextUpQueue([{ ...item, id: 600, item_id: 42, available: true }]);
  assert.ok(s.descendants(s.get('nextUpQueueItems')).some(node => node.dataset.progressItemId === '42'));
  const card = s.context.makeReturnDeckItem(item, 'Start here', 'Continue');
  assert.ok(card.children.some(node => node.dataset.progressItemId === '42'));
});

test('private library has only three supported action entry points and versioned assets', () => {
  assert.equal([...app.matchAll(/data-progress-category=/g)].length, 3);
  for (const category of ['tv-shows', 'anime', 'books']) assert.ok(app.includes(`data-progress-category="${category}"`));
  assert.match(template, /progress\.js\?v=20260922-progress/);
  assert.match(template, /progress\.css\?v=20260922-progress/);
  assert.match(template, /<dialog id="progressDialog"[^>]*aria-labelledby="progressTitle"/);
});
