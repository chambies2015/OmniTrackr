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
  return { window, document, el, elements, links, timers };
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

function classes() {
  const names = new Set();
  return {
    names,
    add(name) { names.add(name); },
    toggle(name, on) { if (on) names.add(name); else names.delete(name); },
    contains(name) { return names.has(name); },
  };
}

test('choosing a group shows that section alone, from its top, and marks it in the menu', () => {
  const s = load();
  const scrolls = [];
  const panels = s.el('accountSettingsPanels', { scrollTo: options => scrolls.push(options), classList: classes() });
  let focused = null;
  const profile = s.el('settings-profile', { dataset: { settingsGroup: 'profile' }, classList: classes() });
  const privacy = s.el('settings-privacy', {
    dataset: { settingsGroup: 'privacy' }, classList: classes(), focus: options => { focused = options; },
  });
  s.document.querySelectorAll = selector => {
    if (selector === '[data-settings-link]') return s.links;
    return selector === '[data-settings-group]' ? [profile, privacy] : [];
  };
  s.window.OmniSettings.showGroup('privacy');
  assert.deepEqual(scrolls.map(o => ({ ...o })), [{ top: 0, behavior: 'instant' }]);
  assert.equal(focused.preventScroll, true);
  assert.ok(privacy.classList.contains('is-current'));
  assert.ok(!profile.classList.contains('is-current'));
  assert.ok(panels.classList.contains('account-settings__panels--paged'));
  assert.equal(s.links[1].getAttribute('aria-current'), 'true');
  assert.equal(s.links[0].getAttribute('aria-current'), null);
});

test('a card in another section brings its section forward before anything scrolls to it', () => {
  const s = load();
  s.el('accountSettingsPanels', { classList: classes() });
  const data = s.el('settings-data', { dataset: { settingsGroup: 'data' }, classList: classes() });
  s.document.querySelectorAll = selector => (selector === '[data-settings-group]' ? [data] : []);
  const card = s.el('importStudio', { closest: selector => (selector === '[data-settings-group]' ? data : null) });
  assert.equal(s.window.OmniSettings.reveal('importStudio'), card);
  assert.ok(data.classList.contains('is-current'));
  assert.equal(s.window.OmniSettings.reveal('missing'), null);
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
