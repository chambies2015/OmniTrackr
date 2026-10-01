// Run with: node --test tests/test_import_studio_ui.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/import-studio.js'), 'utf8');
const authSource = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const appSource = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const ok = data => ({ok: true, status: 200, json: async () => data});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => {resolve = res; reject = rej;});
  return {promise, resolve, reject};
};
const file = (name = 'library.csv', text = 'title,rating,read,review\nA book,0,false,Private note') => ({
  name, size: text.length, lastModified: 42, text: async () => text,
  slice() {return {text: () => this.text()};},
});
const row = (overrides = {}) => ({row: 2, title: 'A book', category: 'books', status: 'ready', reason: null,
  values: {creator: 'An author', year: 2024, release_date: null, rating: 0, completed: false,
    review: 'Private note', genre: 'Fiction', seasons: null, episodes: null}, ...overrides});
const preview = (overrides = {}) => ({fingerprint: 'a'.repeat(64), detected_source: 'generic', total_rows: 1,
  ready_count: 1, duplicate_count: 0, invalid_count: 0, by_category: {books: 1}, preview_total: 1,
  preview_offset: 0, preview_limit: 25, status_filter: 'all', preview: [row()], ...overrides});
const saved = {created_count: 1, duplicate_count: 2, invalid_count: 1, by_category: {books: 1}, detected_source: 'generic'};

function setup() {
  const events = new Map();
  let document;
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attributes = {};
      this.style = {}; this._value = ''; this._text = ''; this.hidden = false; this.disabled = false;
      this.checked = false; this.className = ''; this.listeners = new Map(); this.files = [];
      this.classList = {
        add: name => {this.className = [...new Set([...this.className.split(' ').filter(Boolean), name])].join(' ');},
        remove: name => {this.className = this.className.split(' ').filter(item => item !== name).join(' ');},
        toggle: (name, enabled) => enabled ? this.classList.add(name) : this.classList.remove(name),
      };
    }
    set value(value) {this._value = String(value); if (this.type === 'file' && value === '') this.files = [];}
    get value() {
      if (this.tagName === 'SELECT' && this._value === '') return this.children.find(child => child.selected)?.value || '';
      return this._value;
    }
    set textContent(value) {this.replaceChildren(); this._text = String(value);}
    get textContent() {return this._text + this.children.map(child => child.textContent).join('');}
    set innerHTML(value) {assert.equal(value, '', 'private imported text must never be inserted as HTML'); this.replaceChildren();}
    appendChild(child) {this.children.push(child); child.parentElement = this; return child;}
    append(...children) {children.forEach(child => this.appendChild(child));}
    replaceChildren(...children) {this.children.forEach(child => {child.parentElement = null;}); this.children = []; this._text = ''; this.append(...children);}
    remove() {if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(child => child !== this);}
    setAttribute(name, value) {this.attributes[name] = String(value);}
    getAttribute(name) {return this.attributes[name] ?? null;}
    removeAttribute(name) {delete this.attributes[name];}
    focus() {document.activeElement = this; this.focused = true;}
    scrollIntoView() {this.scrolled = true;}
    addEventListener(name, callback) {this.listeners.set(name, callback);}
    trigger(name, values = {}) {return this.listeners.get(name)?.({target: this, currentTarget: this, preventDefault() {}, ...values});}
    click() {return this.trigger('click');}
    querySelectorAll(selector) {
      const matchesSimple = (element, query) => {
        const data = query.match(/^\[data-([a-z-]+)(?:="([^"]*)")?\]$/);
        if (data) {
          const key = data[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
          return Object.hasOwn(element.dataset, key) && (data[2] === undefined || element.dataset[key] === data[2]);
        }
        if (query.startsWith('#')) return element.id === query.slice(1);
        if (query.startsWith('.')) return element.className.split(' ').includes(query.slice(1));
        return element.tagName.toLowerCase() === query;
      };
      const matches = element => selector.split(',').some(part => {
        const pieces = part.trim().split(/\s+/);
        if (!matchesSimple(element, pieces.pop())) return false;
        let ancestor = element.parentElement;
        while (pieces.length) {
          const next = pieces.pop();
          while (ancestor && !matchesSimple(ancestor, next)) ancestor = ancestor.parentElement;
          if (!ancestor) return false;
          ancestor = ancestor.parentElement;
        }
        return true;
      });
      return this.children.flatMap(child => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
    }
    querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  }
  const elements = new Map();
  const add = (name, tag = 'div') => {
    const element = new Element(tag); element.id = `importStudio${name}`; elements.set(element.id, element); return element;
  };
  document = {
    body: new Element('body'), activeElement: null, createElement: tag => new Element(tag),
    getElementById: id => elements.get(id) || document.body.querySelector(`#${id}`),
    querySelectorAll: selector => document.body.querySelectorAll(selector),
    querySelector: selector => document.body.querySelector(selector),
    addEventListener: (name, callback) => events.set(`document:${name}`, callback),
  };
  const studio = add(''); document.body.append(studio);
  const form = add('Form', 'form'); studio.append(form);
  for (const [name, tag] of [['Source', 'select'], ['Category', 'select'], ['File', 'input'], ['Mapping', 'div'],
    ['PreviewButton', 'button'], ['ApplyButton', 'button'], ['TemplateCategory', 'select']]) form.append(add(name, tag));
  form.elements = form.querySelectorAll('select,input,button');
  for (const name of ['Status', 'Results', 'Confirm']) studio.append(add(name));
  const get = name => document.getElementById(`importStudio${name}`);
  get('Confirm').append(add('ConfirmSummary'), add('ConfirmButton', 'button'), add('CancelButton', 'button'));
  get('Results').hidden = true; get('Confirm').hidden = true; get('ApplyButton').disabled = true;
  get('Source').value = 'auto'; get('TemplateCategory').value = 'movies';
  get('File').type = 'file'; get('File').files = [file()];
  const requests = [], timers = new Map(), refreshed = [], opened = [];
  let timerId = 0, user = {id: 7, username: 'owner'}, token = 'session-one';
  class FormData {
    constructor() {this.values = new Map();}
    append(key, value) {this.values.set(key, value);}
    get(key) {return this.values.get(key) ?? null;}
  }
  const window = {
    addEventListener: (name, callback) => events.set(name, callback),
    location: {pathname: '/', hash: '', origin: 'http://localhost'},
  };
  window.setTimeout = (callback, delay) => {const id = ++timerId; timers.set(id, {callback, delay}); return id;};
  window.clearTimeout = id => timers.delete(id);
  const context = vm.createContext({
    document, window, FormData, AbortController, API_BASE: '', console,
    getUser: () => user, getToken: () => token,
    setTimeout: window.setTimeout, clearTimeout: window.clearTimeout,
    authenticatedFetch: (url, options = {}) => {const pending = deferred(); requests.push({url, options, ...pending}); return pending.promise;},
    URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}},
  });
  vm.runInContext(source, context);
  window.OmniImportStudio.refresh = async categories => {refreshed.push(categories);};
  window.OmniImportStudio.openCategory = category => {opened.push(category);};
  window.OmniImportStudio.canOpenCategory = () => true;
  return {
    context, window, document, get, requests, timers, refreshed, opened, events,
    startPreview: () => context.previewLibraryImport({preventDefault() {}}),
    async preview(data = preview()) {const operation = this.startPreview(); requests.at(-1).resolve(ok(data)); await operation;},
    session(nextUser, nextToken = 'session-two') {user = nextUser; token = nextToken;},
  };
}

test('preview is read-only until the inline confirmation is accepted, and duplicate clicks cannot write twice', async () => {
  const s = setup();
  await s.preview();
  assert.equal(s.requests.length, 1);
  assert.match(s.requests[0].url, /\/preview\/$/);
  assert.equal(s.get('ApplyButton').disabled, false);
  s.context.applyLibraryImport();
  assert.equal(s.requests.length, 1);
  assert.equal(s.get('Confirm').hidden, false);
  s.context.cancelLibraryImport();
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.requests.length, 1);
  s.context.applyLibraryImport();
  const saving = s.context.confirmLibraryImport();
  s.context.confirmLibraryImport();
  assert.equal(s.requests.length, 2);
  assert.equal(s.get('File').disabled, true);
  assert.equal(s.get('Category').disabled, true);
  assert.equal(s.get('CancelButton').disabled, true);
  assert.equal(s.requests[1].options.body.get('fingerprint_confirmation'), 'a'.repeat(64));
  s.requests[1].resolve(ok(saved));
  await saving;
  assert.equal(s.get('File').disabled, false);
  s.context.applyLibraryImport();
  s.context.confirmLibraryImport();
  assert.equal(s.requests.length, 2, 'a completed import cannot be submitted again');
});

test('normalized preview distinguishes zero from unrated and false from completed, with literal private notes', () => {
  const s = setup();
  const note = '<img src=x onerror=alert(1)> & my private note';
  s.context.renderImportStudioPreview(preview({preview: [
    row({title: 'Zero rating', values: {...row().values, review: note}}),
    row({row: 3, title: 'Unrated', values: {...row().values, rating: null, completed: true}}),
  ]}));
  const text = s.get('Results').textContent;
  assert.ok(text.includes(note));
  assert.match(text, /0\s*(?:\/\s*10|out of 10)/);
  assert.match(text, /unrated|not rated|no rating|—/i);
  assert.match(text, /not completed|unfinished|not read|saved|not yet/i);
  assert.match(text, /completed|finished|read/i);
  assert.equal(s.get('Results').querySelectorAll('img').length, 0);
});

test('changing file or options invalidates an in-flight preview even after response JSON has started', async () => {
  for (const changed of ['file', 'options', 'json']) {
    const s = setup();
    const operation = s.startPreview();
    const body = deferred();
    if (changed === 'json') {s.requests[0].resolve({ok: true, status: 200, json: () => body.promise}); await settle();}
    if (changed === 'file') s.get('File').files = [file('different.csv')];
    else s.get('Category').value = 'music';
    s.context.resetImportStudioPreview();
    if (changed === 'json') body.resolve(preview()); else s.requests[0].resolve(ok(preview()));
    await operation;
    assert.equal(s.get('ApplyButton').disabled, true);
    assert.equal(s.get('Results').hidden, true);
    assert.equal(s.get('Confirm').hidden, true);
  }
});

test('a slower old preview cannot replace a newer preview or re-enable its controls', async () => {
  const s = setup();
  const old = s.startPreview();
  s.get('Category').value = 'music';
  s.context.resetImportStudioPreview();
  const latest = s.startPreview();
  s.requests[1].resolve(ok(preview({ready_count: 0, preview: [row({title: 'Current file', status: 'invalid'})]})));
  await latest;
  s.requests[0].resolve(ok(preview({preview: [row({title: 'Outdated file'})]})));
  await old;
  assert.match(s.get('Results').textContent, /Current file/);
  assert.doesNotMatch(s.get('Results').textContent, /Outdated file/);
  assert.equal(s.get('ApplyButton').disabled, true);
});

test('late file inspection cannot restore old column mappings', async () => {
  const s = setup();
  const slow = deferred();
  s.get('File').files = [{...file('old.csv'), text: () => slow.promise}];
  const old = s.context.inspectImportStudioFile();
  s.get('File').files = [file('new.csv', 'new_title,new_rating\nLatest,8')];
  await s.context.inspectImportStudioFile();
  slow.resolve('old_title,old_rating\nOutdated,9');
  await old;
  assert.match(s.get('Mapping').textContent, /new_title/);
  assert.doesNotMatch(s.get('Mapping').textContent, /old_title/);
});

test('failed preview retains the chosen file and options for an explicit retry', async () => {
  const s = setup();
  const selected = s.get('File').files[0];
  s.get('Source').value = 'goodreads'; s.get('Category').value = 'books';
  const pending = s.startPreview();
  s.requests[0].reject(Error('Connection lost'));
  await pending;
  assert.equal(s.get('File').files[0], selected);
  assert.equal(s.get('Source').value, 'goodreads');
  assert.equal(s.get('Category').value, 'books');
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.get('PreviewButton').disabled, false);
  assert.match(s.get('Status').textContent, /connection|preview|try again/i);
  await s.preview();
  assert.equal(s.get('ApplyButton').disabled, false);
});

test('preview deadline covers response parsing and ignores success delivered after timeout', async () => {
  for (const parsing of [false, true]) {
    const s = setup();
    const body = deferred();
    const operation = s.startPreview();
    if (parsing) {s.requests[0].resolve({ok: true, status: 200, json: () => body.promise}); await settle();}
    assert.equal(s.timers.size, 1);
    const timer = [...s.timers.values()][0];
    assert.ok(timer.delay > 0 && timer.delay <= 60000);
    timer.callback();
    await operation;
    assert.equal(s.requests[0].options.signal.aborted, true);
    assert.equal(s.timers.size, 0);
    assert.equal(s.get('PreviewButton').disabled, false);
    assert.equal(s.get('File').files.length, 1);
    assert.match(s.get('Status').textContent, /timed out/i);
    if (parsing) body.resolve(preview()); else s.requests[0].resolve(ok(preview()));
    await settle();
    assert.equal(s.get('ApplyButton').disabled, true);
    assert.equal(s.get('Results').hidden, true);
  }
});

test('paging and outcome filters can inspect rows beyond the old first-100 cutoff', async () => {
  const s = setup();
  await s.preview(preview({total_rows: 180, ready_count: 178, invalid_count: 2, preview_total: 180}));
  const paging = s.context.changeImportStudioPage(100);
  assert.equal(Number(s.requests[1].options.body.get('offset')), 100);
  assert.equal(Number(s.requests[1].options.body.get('limit')), 25);
  assert.equal(s.get('ApplyButton').disabled, true);
  s.requests[1].resolve(ok(preview({total_rows: 180, preview_total: 180, preview_offset: 100, preview: [row({row: 102, title: 'Beyond one hundred'})]})));
  await paging;
  assert.match(s.get('Results').textContent, /Beyond one hundred/);
  const filtering = s.context.filterImportStudioPreview('invalid');
  assert.equal(s.requests[2].options.body.get('status_filter'), 'invalid');
  assert.equal(Number(s.requests[2].options.body.get('offset')), 0);
  s.requests[2].resolve(ok(preview({total_rows: 180, preview_total: 2, status_filter: 'invalid', invalid_count: 2,
    preview: [row({row: 171, title: 'Needs fixing', status: 'invalid', reason: 'Rating is outside 0–10.', values: null})]})));
  await filtering;
  assert.match(s.get('Results').textContent, /171.*Needs fixing/);
});

test('failed page request preserves the prior preview instead of losing the inspection context', async () => {
  const s = setup();
  await s.preview(preview({total_rows: 50, preview_total: 50}));
  const prior = s.get('Results').textContent;
  const paging = s.context.changeImportStudioPage(25);
  s.requests[1].resolve({ok: false, status: 503, json: async () => ({detail: 'Please retry this page.'})});
  await paging;
  assert.equal(s.get('Results').textContent, prior);
  assert.equal(s.get('File').files.length, 1);
  assert.match(s.get('Status').textContent, /retry/i);
});

test('changing an option after opening confirmation requires a fresh preview', async () => {
  const s = setup(); await s.preview();
  s.context.applyLibraryImport();
  s.get('Category').value = 'music'; s.context.resetImportStudioPreview();
  await s.context.confirmLibraryImport();
  assert.equal(s.requests.length, 1);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.get('ApplyButton').disabled, true);
});

test('confirmation checks the actual current file even if its change handler has not run', async () => {
  const s = setup(); await s.preview();
  s.context.applyLibraryImport();
  s.get('File').files = [file('library.csv', 'title,rating\nChanged rows,9')];
  await s.context.confirmLibraryImport();
  assert.equal(s.requests.length, 1, 'the old fingerprint must not authorize a different selected file');
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.get('Confirm').hidden, true);
});

test('server rejection keeps the file and options without claiming any rows were imported', async () => {
  const s = setup(); await s.preview();
  const selected = s.get('File').files[0];
  s.context.applyLibraryImport(); const operation = s.context.confirmLibraryImport();
  s.requests[1].resolve({ok: false, status: 500, json: async () => ({detail: 'Nothing was imported because the batch could not be saved.'})});
  await operation;
  assert.equal(s.get('File').files[0], selected);
  assert.match(s.get('Status').textContent, /nothing was imported/i);
  assert.equal(s.refreshed.length, 0);
});

test('successful import retains results, refreshes the library, and opens only an affected category', async () => {
  const s = setup(); await s.preview();
  s.context.applyLibraryImport(); const operation = s.context.confirmLibraryImport();
  s.requests[1].resolve(ok(saved)); await operation;
  assert.equal(s.get('Results').hidden, false);
  assert.match(s.get('Status').textContent + s.get('Results').textContent, /1.*added|1.*imported/i);
  assert.match(s.get('Status').textContent + s.get('Results').textContent, /2.*duplicate/i);
  assert.match(s.get('Status').textContent + s.get('Results').textContent, /1.*(?:unchanged|attention|invalid)/i);
  assert.equal(s.refreshed.length, 1);
  const open = s.get('Results').querySelectorAll('button').find(button => /open.*books/i.test(button.textContent));
  assert.ok(open, 'the result offers a direct route to the imported category');
  await open.click();
  assert.deepEqual(s.opened, ['books']);
  assert.equal(s.get('ApplyButton').disabled, true);
});

test('successful saves stay successful when a library refresh fails', async () => {
  const s = setup(); await s.preview();
  s.window.OmniImportStudio.refresh = async () => {throw Error('Library refresh failed');};
  s.context.applyLibraryImport(); const saving = s.context.confirmLibraryImport();
  s.requests.at(-1).resolve(ok(saved)); await saving; await settle();
  assert.match(s.get('Status').textContent, /import complete/i);
  assert.equal(s.get('Results').hidden, false);
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.get('File').disabled, false);
});

test('an imported category hidden by the user offers tab guidance instead of an unusable open action', async () => {
  const s = setup(); await s.preview();
  s.window.OmniImportStudio.canOpenCategory = () => false;
  s.context.applyLibraryImport(); const saving = s.context.confirmLibraryImport();
  s.requests.at(-1).resolve(ok(saved)); await saving;
  assert.match(s.get('Results').textContent, /books.*hidden.*tab visibility/i);
  assert.equal(s.get('Results').querySelectorAll('button').filter(button => /open.*books/i.test(button.textContent)).length, 0);
});

test('an uncertain write requires a new preview and never offers the old batch for direct resubmission', async () => {
  const s = setup(); await s.preview();
  s.context.applyLibraryImport(); const saving = s.context.confirmLibraryImport();
  s.requests.at(-1).reject(Error('Connection lost after submission')); await saving;
  assert.equal(s.get('File').files.length, 1);
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.get('Confirm').hidden, true);
  assert.match(s.get('Status').textContent, /preview again.*saved matches.*skipped/i);
  s.context.applyLibraryImport(); await s.context.confirmLibraryImport();
  assert.equal(s.requests.length, 2);
  await s.preview(preview({ready_count: 0, duplicate_count: 1, preview: [row({status: 'duplicate'})]}));
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.requests.filter(request => request.url.endsWith('/apply/')).length, 1);
});

test('an import deadline unlocks controls, requires a new preview, and ignores a late successful response', async () => {
  for (const parsing of [false, true]) {
    const s = setup(); await s.preview();
    const body = deferred();
    s.context.applyLibraryImport(); const operation = s.context.confirmLibraryImport();
    if (parsing) {s.requests[1].resolve({ok: true, status: 200, json: () => body.promise}); await settle();}
    [...s.timers.values()][0].callback(); await operation;
    assert.equal(s.requests[1].options.signal.aborted, true);
    assert.equal(s.get('File').disabled, false);
    assert.equal(s.get('PreviewButton').disabled, false);
    assert.equal(s.get('ApplyButton').disabled, true);
    assert.equal(s.get('Confirm').hidden, true);
    assert.match(s.get('Status').textContent, /timed out.*preview again/i);
    if (parsing) body.resolve(saved); else s.requests[1].resolve(ok(saved));
    await settle();
    assert.equal(s.refreshed.length, 0);
    assert.equal(s.timers.size, 0);
    assert.doesNotMatch(s.get('Status').textContent, /import complete/i);
  }
});

test('session cleanup removes selected files, mappings, and private preview text and rejects late results', async () => {
  const s = setup(); await s.context.inspectImportStudioFile(); await s.preview();
  assert.match(s.get('Results').textContent, /Private note/);
  const pending = s.startPreview();
  s.context.clearImportStudioSession();
  s.session(null, null);
  s.requests.at(-1).resolve(ok(preview())); await pending;
  assert.equal(s.get('File').files.length, 0);
  assert.doesNotMatch(s.get('Results').textContent, /Private note/);
  assert.equal(s.get('Results').hidden, true);
  assert.equal(s.get('Confirm').hidden, true);
  assert.equal(s.get('ApplyButton').disabled, true);
  assert.equal(s.get('Mapping').querySelectorAll('select').length, 0);
});

test('a changed signed-in identity cannot accept the old account preview or save result', async () => {
  for (const saving of [false, true]) {
    const s = setup();
    if (saving) await s.preview();
    let operation;
    if (saving) {s.context.applyLibraryImport(); operation = s.context.confirmLibraryImport();}
    else operation = s.startPreview();
    s.session({id: 8, username: 'other'});
    s.requests.at(-1).resolve(ok(saving ? saved : preview()));
    await operation;
    assert.equal(s.refreshed.length, 0);
    assert.equal(s.opened.length, 0);
    assert.equal(s.get('ApplyButton').disabled, true);
    assert.doesNotMatch(s.get('Status').textContent, /import complete/i);
  }
});

test('file inspection that finishes after session cleanup cannot reveal the previous file headers', async () => {
  const s = setup();
  const text = deferred();
  s.get('File').files = [{...file(), text: () => text.promise}];
  const inspecting = s.context.inspectImportStudioFile();
  s.context.clearImportStudioSession();
  text.resolve('private_old_title,private_old_note\nA book,A note');
  await inspecting;
  assert.doesNotMatch(s.get('Mapping').textContent, /private_old/);
  assert.equal(s.get('File').files.length, 0);
  assert.equal(s.get('Mapping').querySelectorAll('select').length, 0);
});

test('the real authentication cleanup clears Import Studio for logout and expired-session recovery', async () => {
  for (const preserveReturn of [false, true]) {
    const s = setup(); await s.preview();
    const pending = s.startPreview();
    Object.assign(s.context, {
      TOKEN_KEY: 'token', USER_KEY: 'user', RETURN_PROMPT_KEY: 'return-prompt',
      localStorage: {removeItem() {}}, sessionStorage: {removeItem() {}},
      clearDiscoverAuthReturn() {}, clearDemoStartIntent() {},
    });
    vm.runInContext(authSource.slice(authSource.indexOf('function clearAuth('), authSource.indexOf('function isAuthenticated(')), s.context);
    s.context.clearAuth({preserveReturn});
    s.requests.at(-1).resolve(ok(preview())); await pending;
    assert.equal(s.get('File').files.length, 0);
    assert.equal(s.get('ApplyButton').disabled, true);
    assert.equal(s.get('Results').hidden, true);
    assert.doesNotMatch(s.get('Results').textContent, /Private note/);
  }
});

test('the application refresh bridge invalidates imported library pages and respects active edits and hidden tabs', () => {
  const s = setup();
  const tabs = new Map(['books', 'music'].map(category => [category, s.document.createElement('button')]));
  const search = s.document.createElement('input'); search.id = 'bookSearchInput'; search.value = 'Old search'; s.document.body.append(search);
  const pages = new Map([['books', {offset: 25}], ['music', {offset: 75}]]);
  const stats = {books: {}, music: {}, 'library-insights': {}};
  const opened = [], loaded = [];
  let invalidated = 0, scheduled = 0, closed = 0;
  Object.assign(s.context, {
    getTabButton: category => tabs.get(category),
    invalidateLibrarySearchIndex: () => {invalidated++;},
    categoryStatsCache: stats, libraryPages: pages, libraryFilters: new Map(),
    scheduleLibraryLaunchpadRefresh: () => {scheduled++;},
    currentTab: 'books', editingRowId: null,
    loadMovies: async () => {}, loadTVShows: async () => {}, loadAnime: async () => {},
    loadVideoGames: async () => {}, loadMusic: async () => {}, loadBooks: async () => {},
    libraryPageConfig: category => [null, null, () => {loaded.push(category);}],
    LIBRARY_SEARCH_SOURCES: [{tab: 'books', input: 'bookSearchInput'}],
    switchTab: category => {opened.push(category);},
  });
  s.window.closeAccountModal = () => {closed++;};
  vm.runInContext(appSource.slice(appSource.indexOf('// Import completion reuses'), appSource.indexOf('// Load initial data')), s.context);
  s.window.OmniImportStudio.refresh({books: 1, music: 0});
  assert.equal(invalidated, 1); assert.equal(scheduled, 1);
  assert.equal(pages.has('books'), false);
  assert.equal(pages.has('music'), true);
  assert.equal(Object.keys(stats).length, 0);
  assert.deepEqual(loaded, ['books']);
  s.context.editingRowId = 42;
  s.window.OmniImportStudio.refresh({books: 1});
  assert.deepEqual(loaded, ['books'], 'refresh must not replace an active row edit');
  s.window.OmniImportStudio.openCategory('books');
  assert.equal(closed, 0);
  assert.match(s.get('Status').textContent, /save or cancel.*edit/i);
  s.context.editingRowId = null;
  tabs.get('books').style.display = 'none';
  s.window.OmniImportStudio.openCategory('books');
  assert.equal(closed, 0);
  tabs.get('books').style.display = '';
  s.window.OmniImportStudio.openCategory('books');
  assert.deepEqual(opened, ['books']);
  assert.equal(closed, 1); assert.equal(search.value, '');
  assert.equal(tabs.get('books').focused, true);
});

function setupImportRefreshRace(category = 'books', bindControls = false) {
  const s = setup();
  const loaders = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
    'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks',
  };
  const pendingLoads = [], rendered = [];
  const loading = new Set();
  const tab = s.document.createElement('button');
  const search = s.document.createElement('input'); search.id = 'importRaceSearch'; s.document.body.append(search);
  for (const [name, functionName] of Object.entries(loaders)) {
    s.context[functionName] = async () => {
      // Model the existing loader guard: a concurrent invocation does no work.
      if (loading.has(name)) return;
      loading.add(name);
      const request = deferred(); pendingLoads.push({category: name, ...request});
      try { rendered.push(await request.promise); }
      finally { loading.delete(name); }
    };
  }
  Object.assign(s.context, {
    getTabButton: () => tab,
    invalidateLibrarySearchIndex() {}, categoryStatsCache: {}, libraryPages: new Map(), libraryFilters: new Map(),
    scheduleLibraryLaunchpadRefresh() {}, currentTab: category, editingRowId: null,
    libraryPageConfig: name => [null, null, s.context[loaders[name]]],
    LIBRARY_SEARCH_SOURCES: [{tab: category, input: search.id}],
    switchTab: name => {s.context.currentTab = name; return s.context[loaders[name]]();},
  });
  s.window.closeAccountModal = () => {};
  if (bindControls) {
    for (const id of [...Object.values(loaders), 'movieSort', 'tvSort', 'animeSort', 'videoGameSort', 'musicSort', 'bookSort']) {
      const control = s.document.createElement(id.startsWith('load') ? 'button' : 'select');
      control.id = id; s.document.body.append(control);
    }
    // The real application binds these controls before installing the bridge.
    vm.runInContext(appSource.slice(appSource.indexOf("document.getElementById('loadMovies').addEventListener"),
      appSource.indexOf('// Automatic search with debounce')), s.context);
  }
  vm.runInContext(appSource.slice(appSource.indexOf('// Import completion reuses'), appSource.indexOf('// Load initial data')), s.context);
  return {...s, pendingLoads, rendered, startLoad: () => s.context[loaders[category]]()};
}

test('import refresh waits for a pre-import load and then fetches the updated library for every category', async () => {
  for (const category of ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']) {
    const s = setupImportRefreshRace(category);
    const oldLoad = s.startLoad();
    await s.startLoad(); // An ignored duplicate must not replace the tracked load.
    const refreshed = s.window.OmniImportStudio.refresh({[category]: 1});
    assert.equal(s.pendingLoads.length, 1);
    s.pendingLoads[0].resolve('Before import');
    await oldLoad; await settle();
    assert.equal(s.pendingLoads.length, 2, `${category} must reload after the old response finishes`);
    s.pendingLoads[1].resolve('Includes imported titles');
    await refreshed;
    assert.deepEqual(s.rendered, ['Before import', 'Includes imported titles']);
    assert.equal(s.timers.size, 0, 'waiting for a library load needs no polling timer');
  }
});

test('queued import refresh is cancelled by session cleanup, account changes, navigation, or an unsaved edit', async () => {
  for (const change of ['reset', 'storage', 'pagehide', 'account', 'category', 'editing']) {
    const s = setupImportRefreshRace();
    const oldLoad = s.startLoad();
    const refreshed = s.window.OmniImportStudio.refresh({books: 1});
    if (change === 'reset') s.window.OmniImportStudio.reset();
    if (change === 'storage') s.events.get('storage')({key: 'omnitrackr_user'});
    if (change === 'pagehide') s.events.get('pagehide')();
    if (change === 'account') s.session({id: 99, username: 'another-account'});
    if (change === 'category') s.context.currentTab = 'movies';
    if (change === 'editing') s.context.editingRowId = 123;
    s.pendingLoads[0].resolve('Old request finished');
    await oldLoad; await refreshed;
    assert.equal(s.pendingLoads.length, 1, `${change} must prevent a delayed follow-up request`);
  }
});

test('a failed pre-import load still permits the queued import refresh', async () => {
  const s = setupImportRefreshRace();
  const oldLoad = s.startLoad();
  const refreshed = s.window.OmniImportStudio.refresh({books: 1});
  s.pendingLoads[0].reject(new Error('Old request failed'));
  await assert.rejects(oldLoad, /Old request failed/);
  await settle();
  assert.equal(s.pendingLoads.length, 2);
  s.pendingLoads[1].resolve('Imported library');
  await refreshed;
  assert.deepEqual(s.rendered, ['Imported library']);
});

test('Open category also reloads when its old request is still running', async () => {
  const s = setupImportRefreshRace();
  const oldLoad = s.startLoad();
  const opened = s.window.OmniImportStudio.openCategory('books');
  assert.equal(s.pendingLoads.length, 1);
  s.pendingLoads[0].resolve('Before import');
  await oldLoad; await settle();
  assert.equal(s.pendingLoads.length, 2);
  s.pendingLoads[1].resolve('After import');
  await opened;
  assert.deepEqual(s.rendered, ['Before import', 'After import']);
});

test('Refresh and sort controls enter the current loader wrapper instead of retaining an untracked loader', async () => {
  for (const [category, button, sort] of [
    ['movies', 'loadMovies', 'movieSort'], ['tv-shows', 'loadTVShows', 'tvSort'],
    ['anime', 'loadAnime', 'animeSort'], ['video-games', 'loadVideoGames', 'videoGameSort'],
    ['music', 'loadMusic', 'musicSort'], ['books', 'loadBooks', 'bookSort'],
  ]) {
    for (const [control, event] of [[button, 'click'], [sort, 'change']]) {
      const s = setupImportRefreshRace(category, true);
      const oldLoad = s.document.getElementById(control).trigger(event);
      const refreshed = s.window.OmniImportStudio.refresh({[category]: 1});
      assert.equal(s.pendingLoads.length, 1);
      s.pendingLoads[0].resolve('Before import');
      await oldLoad; await settle();
      assert.equal(s.pendingLoads.length, 2, `${control} must participate in the deferred refresh`);
      s.pendingLoads[1].resolve('After import');
      await refreshed;
      assert.deepEqual(s.rendered, ['Before import', 'After import']);
    }
  }
});
