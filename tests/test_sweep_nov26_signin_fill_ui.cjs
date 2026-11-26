// Nov 26 2026 sweep: carried titles on a signed-in /continue page, carried covers, and the
// "Fill in your year" page's counts and refills.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

// ------------------------------------------------------------ /continue

function fakeElement(tag) {
  return {
    tagName: String(tag).toUpperCase(), className: '', dataset: {}, children: [], listeners: {},
    textContent: '', hidden: false, disabled: false,
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    querySelector(selector) { return (this.parts || {})[selector] || null; },
    click() { (this.listeners.click || []).forEach(fn => fn({ preventDefault() {} })); },
  };
}

function loadContinue({ mode = 'member', hash = '', saved = [] } = {}) {
  const list = { MAX: 30, saved: saved.slice(), read() { return this.saved.slice(); }, write(next) { this.saved = next; return true; },
    readReturn: () => null };
  const box = fakeElement('div');
  box.hidden = true;
  box.parts = {
    '[data-continue-list-head]': fakeElement('p'),
    '[data-continue-titles]': fakeElement('ul'),
    '[data-continue-more]': fakeElement('p'),
  };
  const add = fakeElement('button');
  add.hidden = true;
  const open = fakeElement('a');
  open.className = 'site-btn site-btn--primary continue-wide';
  const lead = fakeElement('p');
  const parts = { '[data-continue-list]': box, '[data-continue-add]': add, '[data-continue-open]': open, '[data-continue-lead]': lead };
  const went = [];
  const beacons = [];
  global.document = {
    readyState: 'complete',
    body: { dataset: { continue: mode } },
    querySelector: selector => parts[selector] || null,
    createElement: fakeElement,
    createTextNode: text => ({ textContent: text }),
    addEventListener() {},
  };
  global.window = {
    OmniGuestList: list,
    location: { hash, search: '', origin: 'https://omnitrackr.xyz', host: 'omnitrackr.xyz', assign: to => went.push(to) },
    history: { replaceState() {} },
  };
  global.navigator = { sendBeacon: (url, blob) => { beacons.push(url); return true; } };
  global.Blob = function Blob() {};
  delete require.cache[require.resolve('../app/static/continue.js')];
  const api = require(path.join(__dirname, '../app/static/continue.js'));
  return { api, list, box, add, open, lead, went, beacons };
}

const CARRIED = [
  { kind: 'movie', slug: 'arrival-2016', title: 'Arrival', image: 'https://image.tmdb.org/t/p/w342/a.jpg' },
  { kind: 'book', slug: 'piranesi-2020', title: 'Piranesi', image: 'https://tracker.example/pixel.gif' },
];

test('signed in, a carried list is shown and only joins the library list when Add is pressed', () => {
  const first = loadContinue({ mode: 'browser' });
  const hash = `#ot-carry=${first.api.pack(CARRIED, null)}`;
  const { list, box, add, open, lead, went } = loadContinue({ mode: 'member', hash });
  // Nothing was added just by opening the link.
  assert.deepEqual(list.saved, []);
  assert.equal(box.hidden, false);
  assert.equal(box.parts['[data-continue-list-head]'].textContent, 'This link carries 2 titles');
  assert.deepEqual(box.parts['[data-continue-titles]'].children.map(row => row.children[1].textContent), ['Piranesi', 'Arrival']);
  assert.equal(add.hidden, false);
  assert.equal(add.textContent, 'Add the 2 titles to your library');
  assert.match(open.className, /site-btn--ghost/);
  assert.match(lead.textContent, /Add them to your library, or open your library without them/);
  add.click();
  assert.deepEqual(list.saved.map(item => item.slug), ['arrival-2016', 'piranesi-2020']);
  assert.deepEqual(went, ['/']);
});

test('signed in without a carried list, the page is just the library link', () => {
  const { list, box, add, open, went } = loadContinue({ mode: 'member' });
  assert.deepEqual(list.saved, []);
  assert.equal(box.hidden, true);
  assert.equal(add.hidden, true);
  assert.match(open.className, /site-btn--primary/);
  assert.deepEqual(went, []);
});

test('a carried cover is kept only from a poster host the site uses', () => {
  const { api } = loadContinue({ mode: 'browser' });
  const back = api.unpack(api.pack(CARRIED, null));
  assert.equal(back.items[0].image, 'https://image.tmdb.org/t/p/w342/a.jpg');
  assert.equal(back.items[1].image, undefined);
  assert.equal(api.coverAllowed('https://is1-ssl.mzstatic.com/image/thumb/a.jpg'), true);
  assert.equal(api.coverAllowed('https://upload.wikimedia.org/a.jpg'), true);
  assert.equal(api.coverAllowed('http://image.tmdb.org/t/p/a.jpg'), false);
  assert.equal(api.coverAllowed('https://notmzstatic.com/a.jpg'), false);
  assert.equal(api.coverAllowed('https://user:pw@image.tmdb.org/a.jpg'), false);
  assert.equal(api.coverAllowed('https://image.tmdb.org:8443/a.jpg'), false);
  assert.equal(api.coverAllowed('javascript:alert(1)'), false);
});

test('a guest who arrives in Safari still gets the carried list straight away', () => {
  const first = loadContinue({ mode: 'browser' });
  const hash = `#ot-carry=${first.api.pack(CARRIED, null)}`;
  const { list, box } = loadContinue({ mode: 'browser', hash });
  assert.deepEqual(list.saved.map(item => item.slug), ['arrival-2016', 'piranesi-2020']);
  assert.equal(list.saved[1].image, undefined);
  assert.equal(box.hidden, false);
});

// ------------------------------------------------------------ Fill in your year

function loadFill() {
  delete global.document;
  delete global.window;
  delete require.cache[require.resolve('../app/static/year-fill.js')];
  return require(path.join(__dirname, '../app/static/year-fill.js'));
}

test('the rest question counts every title waiting, not just the cards on screen', () => {
  const fill = loadFill();
  const counts = { undated_left: 412, open_left: 300 };
  assert.equal(fill.waiting('undated', counts, 40), 412);
  assert.equal(fill.waiting('open', counts, 12), 300);
  assert.equal(fill.waiting('open', null, 12), 12);
  assert.equal(fill.restQuestion('undated', 412, 2026),
    'Mark the 412 titles left as finished before 2026? They stay ticked off, just out of this recap.');
  assert.equal(fill.restQuestion('open', 300, 2026), 'Leave all 300 titles on your list as not finished yet?');
});

test('an answered-out list loads the next titles, for "still on your list" as well', () => {
  const fill = loadFill();
  assert.equal(fill.needsMore(0, 3, { undated_left: 5, open_left: 3 }), true);
  assert.equal(fill.needsMore(4, 0, { undated_left: 4, open_left: 288 }), true);
  assert.equal(fill.needsMore(4, 0, { undated_left: 4, open_left: 0 }), false);
  assert.equal(fill.needsMore(0, 0, { undated_left: 0, open_left: 0 }), false);
  assert.equal(fill.needsMore(0, 0, null), false);
});
