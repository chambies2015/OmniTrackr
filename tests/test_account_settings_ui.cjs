// Settings dialog script: links like /#settings-privacy, the section menu, and the
// pinned "Saved" note that repeats success messages from further down the page.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/account-settings.js'), 'utf8');

function load() {
  const elements = new Map();
  const timers = [];
  function el(id, props = {}) {
    const node = {
      id, attrs: {}, dataset: {}, style: {}, hidden: false, textContent: '', listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      removeAttribute(k) { delete this.attrs[k]; },
      hasAttribute(k) { return k in this.attrs; },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      querySelectorAll: () => [],
      ...props,
    };
    elements.set(id, node);
    return node;
  }
  const links = ['profile', 'privacy'].map(key => el(`link-${key}`, { dataset: { settingsLink: key } }));
  const document = {
    readyState: 'complete',
    getElementById: id => elements.get(id) || null,
    querySelector: () => null,
    querySelectorAll: selector => (selector === '[data-settings-link]' ? links : []),
    addEventListener() {},
  };
  const window = { location: { hash: '', pathname: '/', search: '' }, history: { replaceState() {} }, addEventListener() {} };
  const context = vm.createContext({
    document, window,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    clearTimeout() {},
  });
  vm.runInContext(source, context);
  return { window, el, elements, links, timers };
}

test('links like /#settings-privacy name a group; anything else is ignored', () => {
  const { window } = load();
  const { groupFromHash } = window.OmniSettings;
  assert.equal(groupFromHash('#settings-privacy'), 'privacy');
  assert.equal(groupFromHash('#settings-danger'), 'danger');
  assert.equal(groupFromHash('#settings'), 'profile');
  assert.equal(groupFromHash('#settings-admin'), null);
  assert.equal(groupFromHash('#supporter'), null);
  assert.equal(groupFromHash('#settings-privacy<script>'), null);
});

test('jumping to a group marks it in the menu and scrolls only the settings column', () => {
  const s = load();
  const scrolls = [];
  s.el('accountSettingsPanels', { scrollTo: options => scrolls.push(options) });
  let focused = null;
  s.el('settings-privacy', { offsetTop: 640, focus: options => { focused = options; } });
  s.window.OmniSettings.showGroup('privacy');
  assert.deepEqual(scrolls.map(o => ({ ...o })), [{ top: 636, behavior: 'instant' }]);
  assert.equal(focused.preventScroll, true);
  assert.equal(s.links[1].getAttribute('aria-current'), 'true');
  assert.equal(s.links[0].getAttribute('aria-current'), null);
});

test('the saved note shows, hides itself, and is silent when the message is already read out', () => {
  const s = load();
  const toast = s.el('accountToast', { hidden: true });
  s.window.OmniSettings.showToast('Saved your menu');
  assert.equal(toast.hidden, false);
  assert.equal(toast.textContent, 'Saved your menu');
  assert.equal(toast.getAttribute('aria-hidden'), null);
  s.timers.at(-1).fn();
  assert.equal(toast.hidden, true);

  s.window.OmniSettings.showToast('Public profile saved', { announce: false });
  assert.equal(toast.getAttribute('aria-hidden'), 'true');
});
