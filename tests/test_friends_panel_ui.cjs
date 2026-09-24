const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const authSource = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const panelStart = source.indexOf('function positionFriendsPanel()');
const panelEnd = source.indexOf('\nlet activeCompletionMomentId', panelStart);
assert.ok(panelStart >= 0 && panelEnd > panelStart, 'Friends helpers are present');

function harness({ authenticated = true, preference, denyStorage = false } = {}) {
  let context;
  const documentListeners = new Map();
  const windowListeners = new Map();
  const nodes = new Map();
  const storage = new Map(preference === undefined ? [] : [['friendsSidebarHidden', preference]]);
  const writes = [];
  const modals = [];
  const bounds = { bottom: 64, right: 1000 };
  const addListener = (listeners, name, handler, options) => {
    if (!listeners.has(name)) listeners.set(name, []);
    listeners.get(name).push({ handler, options });
  };
  function element(id, hidden = false) {
    const classes = new Set(hidden ? ['hidden'] : []);
    const properties = {};
    const listeners = new Map();
    const node = {
      id, hidden, attributes: {}, children: [], classes, listeners,
      style: {
        display: 'none',
        setProperty: (name, value) => { properties[name] = value; },
        getPropertyValue: name => properties[name] ?? '',
        removeProperty(name) { delete this[name]; delete properties[name]; },
      },
      classList: {
        add: name => classes.add(name),
        remove: name => classes.delete(name),
        contains: name => classes.has(name),
        toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
      },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return this.attributes[name] ?? null; },
      addEventListener: (name, handler, options) => addListener(listeners, name, handler, options),
      contains(target) { return target === this || this.children.some(child => child.contains(target)); },
      focus() { context.document.activeElement = this; },
    };
    nodes.set(id, node);
    return node;
  }
  const sidebar = element('friendsSidebar', true);
  const trigger = element('showFriendsSidebar', true);
  const close = element('toggleFriendsSidebar');
  const friend = element('friend');
  sidebar.children.push(close, friend);
  const triggerIcon = element('triggerIcon');
  trigger.children.push(triggerIcon);
  const outside = element('outside');
  const main = element('mainContainer');
  const notification = element('notificationDropdown');
  const footer = element('mainFooter');
  const toolbar = element('toolbar');
  toolbar.getBoundingClientRect = () => bounds;
  const body = element('body');
  context = vm.createContext({
    document: {
      body, activeElement: outside,
      documentElement: { clientWidth: 1200, clientHeight: 800 },
      getElementById: id => nodes.get(id) || null,
      querySelector: selector => selector === '.account-toolbar' ? toolbar : null,
      querySelectorAll(selector) {
        assert.equal(selector, '.modal-overlay, dialog[open], .screenshot-modal.show');
        return modals;
      },
      addEventListener: (name, handler, options) => addListener(documentListeners, name, handler, options),
    },
    innerHeight: 800,
    getComputedStyle: modal => ({ display: modal.display ?? 'flex', visibility: modal.visibility ?? 'visible' }),
    addEventListener: (name, handler, options) => addListener(windowListeners, name, handler, options),
    isAuthenticated: () => authenticated,
    localStorage: {
      getItem(key) { if (denyStorage) throw new Error('Storage denied'); return storage.get(key) ?? null; },
      setItem(key, value) {
        if (denyStorage) throw new Error('Storage denied');
        writes.push([key, String(value)]); storage.set(key, String(value));
      },
      removeItem(key) { storage.delete(key); if (key === 'user') authenticated = false; },
    },
  });
  context.window = context;
  vm.runInContext(source.slice(panelStart, panelEnd), context);
  const fire = (listeners, type, properties = {}) => {
    const event = { target: outside, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...properties };
    for (const { handler } of listeners.get(type) || []) handler(event);
    return event;
  };
  return {
    context, sidebar, trigger, close, friend, triggerIcon, outside, main, footer, notification, toolbar,
    body, bounds, modals, storage, writes, documentListeners, windowListeners,
    element, setAuthenticated: value => { authenticated = value; },
    documentEvent: (type, properties) => fire(documentListeners, type, properties),
    windowEvent: type => fire(windowListeners, type),
    click: node => fire(node.listeners, 'click', { target: node }),
  };
}

function surroundingState(h) {
  return [h.main, h.footer, h.notification, h.toolbar, h.body].map(node => ({
    id: node.id, hidden: node.hidden, style: { ...node.style }, classes: [...node.classes], attributes: { ...node.attributes },
  }));
}

test('Friends toggle synchronizes hidden and expanded state without changing surrounding layout nodes', () => {
  const h = harness({ preference: 'true' });
  const before = surroundingState(h);
  h.context.initializeFriendsPanel();
  assert.equal(h.trigger.hidden, false);
  assert.equal(h.trigger.getAttribute('aria-controls'), 'friendsSidebar');
  assert.equal(h.trigger.getAttribute('aria-expanded'), 'false');
  h.click(h.trigger);
  assert.equal(h.sidebar.hidden, false);
  assert.equal(h.sidebar.classList.contains('hidden'), false);
  assert.equal(h.trigger.getAttribute('aria-expanded'), 'true');
  assert.equal(h.context.document.activeElement, h.close);
  assert.equal(h.trigger.style.display, undefined);
  assert.equal(h.sidebar.style.display, undefined);
  h.click(h.trigger);
  assert.equal(h.sidebar.hidden, true);
  assert.equal(h.sidebar.classList.contains('hidden'), true);
  assert.equal(h.trigger.getAttribute('aria-expanded'), 'false');
  assert.equal(h.context.document.activeElement, h.trigger);
  assert.deepEqual(surroundingState(h), before);
  assert.deepEqual(h.writes, [['friendsSidebarHidden', 'false'], ['friendsSidebarHidden', 'true']]);
});

for (const [preference, expectedHidden] of [[undefined, false], ['false', false], ['true', true]]) {
  test(`restoring ${preference ?? 'default'} preference preserves it without taking focus`, () => {
    const h = harness({ preference });
    h.context.initializeFriendsPanel();
    assert.equal(h.sidebar.hidden, expectedHidden);
    assert.equal(h.context.document.activeElement, h.outside);
    assert.deepEqual(h.writes, []);
  });
}

test('denied browser storage does not prevent opening, closing, or initializing the panel', () => {
  const h = harness({ denyStorage: true });
  assert.doesNotThrow(() => h.context.initializeFriendsPanel());
  assert.equal(h.sidebar.hidden, false);
  assert.doesNotThrow(() => h.click(h.close));
  assert.equal(h.sidebar.hidden, true);
  assert.doesNotThrow(() => h.click(h.trigger));
  assert.equal(h.sidebar.hidden, false);
});

test('outside click dismisses Friends without stealing focus from the clicked control', () => {
  const h = harness();
  h.context.initializeFriendsPanel();
  h.documentEvent('click', { target: h.friend });
  assert.equal(h.sidebar.hidden, false);
  h.documentEvent('click', { target: h.triggerIcon });
  assert.equal(h.sidebar.hidden, false);
  h.outside.focus();
  h.documentEvent('click');
  assert.equal(h.sidebar.hidden, true);
  assert.equal(h.context.document.activeElement, h.outside);
  assert.equal(h.documentListeners.get('click')[0].options, true);
});

test('Escape dismisses Friends and restores trigger focus, but respects already handled keys', () => {
  const h = harness();
  h.context.initializeFriendsPanel();
  h.documentEvent('keydown', { key: 'Enter' });
  h.documentEvent('keydown', { key: 'Escape', defaultPrevented: true });
  assert.equal(h.sidebar.hidden, false);
  const escape = h.documentEvent('keydown', { key: 'Escape' });
  assert.equal(escape.defaultPrevented, true);
  assert.equal(h.sidebar.hidden, true);
  assert.equal(h.context.document.activeElement, h.trigger);
  assert.equal(h.documentEvent('keydown', { key: 'Escape' }).defaultPrevented, false);
});

test('open dialogs keep Friends open during outside clicks and Escape until the dialog is dismissed', () => {
  const h = harness();
  h.context.initializeFriendsPanel();
  const modal = { hidden: false, display: 'flex', visibility: 'visible' };
  h.modals.push(modal);
  h.documentEvent('click');
  const escape = h.documentEvent('keydown', { key: 'Escape' });
  assert.equal(h.sidebar.hidden, false);
  assert.equal(escape.defaultPrevented, false);
  modal.display = 'none';
  h.documentEvent('click');
  assert.equal(h.sidebar.hidden, true);
});

test('hidden modal nodes do not block panel dismissal', () => {
  const h = harness();
  h.context.initializeFriendsPanel();
  h.modals.push({ hidden: true }, { display: 'none' }, { visibility: 'hidden' });
  h.documentEvent('keydown', { key: 'Escape' });
  assert.equal(h.sidebar.hidden, true);
});

test('initialization is idempotent so a single click only toggles once', () => {
  const h = harness({ preference: 'true' });
  h.context.initializeFriendsPanel();
  h.context.initializeFriendsPanel();
  assert.equal(h.trigger.listeners.get('click').length, 1);
  assert.equal(h.close.listeners.get('click').length, 1);
  assert.equal(h.documentListeners.get('click').length, 1);
  assert.equal(h.windowListeners.get('resize').length, 1);
  h.click(h.trigger);
  assert.equal(h.sidebar.hidden, false);
  assert.equal(h.writes.length, 1);
});

test('signed-out initialization and attempted opening leave both Friends controls hidden', () => {
  const h = harness({ authenticated: false, preference: 'false' });
  h.context.initializeFriendsPanel();
  h.context.setFriendsSidebarOpen(true);
  assert.equal(h.sidebar.hidden, true);
  assert.equal(h.trigger.hidden, true);
  assert.equal(h.trigger.getAttribute('aria-expanded'), 'false');
  assert.deepEqual(h.writes, []);
});

test('clearing authentication runs the real reset hook without replacing the saved panel preference', () => {
  const h = harness({ preference: 'false' });
  h.context.initializeFriendsPanel();
  Object.assign(h.context, {
    TOKEN_KEY: 'token', USER_KEY: 'user', RETURN_PROMPT_KEY: 'return',
    sessionStorage: { removeItem() {} }, clearDiscoverAuthReturn() {}, clearDemoStartIntent() {},
  });
  const start = authSource.indexOf('function clearAuth(');
  vm.runInContext(authSource.slice(start, authSource.indexOf('\nfunction isAuthenticated(', start)), h.context);
  h.context.clearAuth();
  assert.equal(h.sidebar.hidden, true);
  assert.equal(h.trigger.hidden, true);
  assert.equal(h.trigger.getAttribute('aria-expanded'), 'false');
  assert.equal(h.storage.get('friendsSidebarHidden'), 'false');
  assert.deepEqual(h.writes, []);
  h.setAuthenticated(true);
  h.context.restoreSidebarState();
  assert.equal(h.sidebar.hidden, false);
  assert.equal(h.trigger.hidden, false);
});

test('panel follows toolbar bounds and clamps its top and right positions during scrolling and resizing', () => {
  const h = harness();
  h.context.initializeFriendsPanel();
  const top = () => h.sidebar.style.getPropertyValue('--friends-panel-top');
  const right = () => h.sidebar.style.getPropertyValue('--friends-panel-right');
  assert.equal(top(), '72px');
  assert.equal(right(), '200px');
  h.bounds.bottom = -100;
  h.bounds.right = 1300;
  h.windowEvent('scroll');
  assert.equal(top(), '12px');
  assert.equal(right(), '12px');
  assert.equal(h.windowListeners.get('scroll')[0].options.passive, true);
  h.bounds.bottom = 500;
  h.context.innerHeight = 320;
  h.windowEvent('resize');
  assert.equal(top(), '160px');
  h.context.innerHeight = 0;
  h.context.document.documentElement.clientHeight = 400;
  h.windowEvent('resize');
  assert.equal(top(), '240px');
  h.context.setFriendsSidebarOpen(false);
  h.bounds.bottom = 10;
  h.windowEvent('scroll');
  assert.equal(top(), '240px', 'closed panels do not need positioning');
});
