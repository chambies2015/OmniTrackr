// Phones: "Start tracking" opens a sign-up sheet on the page instead of loading the homepage form.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function fakeElement(tag) {
  const el = {
    tagName: String(tag).toUpperCase(), className: '', dataset: {}, children: [], attributes: {}, listeners: {},
    textContent: '', innerHTML: '', open: false, href: '', rel: '', type: '', id: '',
    setAttribute(name, value) { this.attributes[name] = String(value); },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    append(...nodes) { this.children.push(...nodes); },
    appendChild(node) { this.children.push(node); return node; },
    querySelector(selector) {
      const key = selector.replace(/^\[data-|\]$/g, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      const stack = [...this.children];
      while (stack.length) {
        const node = stack.shift();
        if (node && node.dataset && key in node.dataset) return node;
        if (node && node.children) stack.push(...node.children);
      }
      return null;
    },
    showModal() { this.open = true; },
    close() { this.open = false; },
  };
  return el;
}

function allText(node) {
  if (!node || typeof node !== 'object') return '';
  return [node.textContent || '', ...(node.children || []).map(allText)].join(' ');
}

function load({ mark = 'google', phone = true, member = false, saved = 0, guestSheet = '', guestList = null, invite = '' } = {}) {
  const store = new Map();
  if (member) store.set('omnitrackr_user', '{"id":1}');
  if (saved) store.set('omnitrackr_guest_list', JSON.stringify(Array.from({ length: saved }, (_, i) => ({ kind: 'movie', slug: `t-${i}`, title: `T ${i}` }))));
  global.localStorage = {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
  };
  const session = new Map(invite ? [['omnitrackr_friend_invite', invite]] : []);
  global.sessionStorage = { getItem: key => (session.has(key) ? session.get(key) : null), setItem() {} };
  const clicks = [];
  const menus = [{ open: true }];
  const body = fakeElement('body');
  body.dataset = mark ? { signupSheet: mark } : {};
  if (guestSheet) body.dataset.guestSheet = guestSheet;
  global.document = {
    body,
    documentElement: { dataset: {}, classList: { add() {}, remove() {} } },
    title: 'Star Wars in order | OmniTrackr',
    querySelector: () => null,
    querySelectorAll: selector => (selector === 'details.site-menu[open]' ? menus : []),
    addEventListener(type, fn) { if (type === 'click') clicks.push(fn); },
    createElement: fakeElement,
    createElementNS: (_, tag) => fakeElement(tag),
    createTextNode: text => ({ textContent: text }),
  };
  const events = [];
  global.window = {
    localStorage: global.localStorage, sessionStorage: global.sessionStorage,
    HTMLDialogElement: function HTMLDialogElement() {},
    matchMedia: query => ({ matches: phone && query === '(max-width: 760px)' }),
    reportFunnelEvent: event => events.push(event),
    OmniGuestList: guestList,
    location: { pathname: '/in-order/star-wars' },
  };
  global.navigator = {};
  delete require.cache[require.resolve('../app/static/site-nav.js')];
  require(path.join(__dirname, '../app/static/site-nav.js'));

  function press(href = '/#signup', { inDialog = false } = {}) {
    const link = { href, closest: sel => (sel === 'dialog' ? (inDialog ? {} : null) : null) };
    const target = { closest: sel => (sel === `a[href="${href}"]` ? link : null) };
    const event = { target, button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    clicks.forEach(fn => fn(event));
    return event;
  }
  const sheet = () => body.children.find(node => node.dataset && 'signupSheetDialog' in node.dataset);
  return { press, sheet, events, menus, store };
}

test('on a phone, Start tracking opens the sheet in place and closes the menu', () => {
  const { press, sheet, events, menus } = load();
  const event = press();
  assert.equal(event.defaultPrevented, true);
  const dialog = sheet();
  assert.ok(dialog && dialog.open);
  assert.equal(menus[0].open, false);
  const text = allText(dialog);
  assert.match(text, /Start your library/);
  assert.match(text, /Continue with Google/);
  assert.match(text, /Sign up with email/);
  assert.deepEqual(events, ['signup_sheet_opened']);
  const links = [];
  const walk = node => { if (node && node.href) links.push(node.href); (node.children || []).forEach(walk); };
  walk(dialog);
  assert.deepEqual(links, ['/auth/google/start', '/#signup', '/#login']);
});

test('Continue with Google counts as starting to sign up and remembers the page', () => {
  const { press, sheet, events, store } = load();
  press();
  const google = sheet().children.find(node => node.className === 'guest-sheet__actions').children[0];
  google.listeners.click.forEach(fn => fn({}));
  assert.deepEqual(events, ['signup_sheet_opened', 'signup_sheet_google', 'signup_form_opened']);
  const back = JSON.parse(store.get('omnitrackr_guest_return'));
  assert.equal(back.path, '/in-order/star-wars');
  assert.equal(back.title, 'Star Wars in order | OmniTrackr');
});

test('a friend invite rides along to Google, and saved titles count as a guest list sign-up', () => {
  const { press, sheet, events } = load({ invite: 'abcdefghijklmnop1234', saved: 2 });
  press();
  const google = sheet().children.find(node => node.className === 'guest-sheet__actions').children[0];
  google.listeners.click.forEach(fn => fn({}));
  assert.equal(google.href, '/auth/google/start?invite=abcdefghijklmnop1234');
  assert.ok(events.includes('guest_list_signup'));
  const bad = load({ invite: '../../x' });
  bad.press();
  const other = bad.sheet().children.find(node => node.className === 'guest-sheet__actions').children[0];
  other.listeners.click.forEach(fn => fn({}));
  assert.equal(other.href, '/auth/google/start');
});

test('the sheet mentions titles saved in this browser', () => {
  const { press, sheet } = load({ saved: 3 });
  press();
  assert.match(allText(sheet()), /The 3 titles you saved in this browser move into it/);
});

test('wider screens, members, other links and unmarked pages keep the old link', () => {
  for (const options of [{ phone: false }, { member: true }, { mark: '' }, { mark: 'email' }]) {
    const { press, sheet } = load(options);
    assert.equal(press().defaultPrevented, false, JSON.stringify(options));
    assert.equal(sheet(), undefined);
  }
  const { press } = load();
  assert.equal(press('/#login').defaultPrevented, false);
  assert.equal(press('/#signup', { inDialog: true }).defaultPrevented, false);
});

test('a guest with saved titles on a guide gets the Keep your list sheet instead', () => {
  const list = { read: () => [{ kind: 'movie', slug: 'up-2009', title: 'Up' }] };
  const { press, sheet } = load({ guestSheet: 'google', guestList: list });
  assert.equal(press().defaultPrevented, false);
  assert.equal(sheet(), undefined);
});
