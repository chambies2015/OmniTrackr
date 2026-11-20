// Nov 20 2026 bug walk: the front-end fixes, run against small stand-ins for the page.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const STATIC = path.join(__dirname, '..', 'app', 'static');

function fresh(file) {
  const full = path.join(STATIC, file);
  delete require.cache[require.resolve(full)];
  return full;
}

// ------------------------------------------------ Your week: "Hide this card" after the card comes back

function weekPage() {
  const elements = {
    yourWeek: { hidden: true, dataset: {}, scrollIntoView() {} },
    yourWeekHide: { disabled: false, hidden: false },
  };
  // 'loading' so the script waits to wire its buttons; render() is what's under test.
  global.document = { readyState: 'loading', addEventListener() {}, getElementById: id => elements[id] || null };
  global.window = { addEventListener() {}, location: { hash: '#your-week' }, requestAnimationFrame: callback => callback() };
  global.fetch = async () => ({ ok: true, json: async () => ({}) });
  return elements;
}

test('a card brought back after Hide this card can be hidden again', () => {
  const elements = weekPage();
  const yourWeek = require(fresh('your-week.js'));
  // The Hide press leaves its button disabled while the card is gone.
  elements.yourWeekHide.disabled = true;
  yourWeek.render({ status: 'open', label: 'Nov 16 to 22', goal: { kind: 'days', target: 3 }, days: [], today: '2026-11-20' });
  assert.equal(elements.yourWeek.hidden, false);
  assert.equal(elements.yourWeekHide.disabled, false);
});

// ------------------------------------------------ title page Share menu: "Link copied" stays in view

function sharePage() {
  global.document = { addEventListener() {}, querySelector: () => null };
  global.window = { location: { href: 'https://omnitrackr.xyz/titles/movie/dune-part-two-2024', origin: 'https://omnitrackr.xyz' } };
  const copied = [];
  Object.defineProperty(global, 'navigator', {
    value: { clipboard: { writeText: async text => { copied.push(text); } } },
    configurable: true, writable: true,
  });
  return copied;
}

function control(text) {
  return { textContent: text, dataset: {}, closest: () => null };
}

test('copying from inside the Share menu says so on the menu button, which stays on screen', async () => {
  const copied = sharePage();
  const share = require(fresh('share.js'));
  const summary = control('Share');
  const item = control('Copy or send the link');
  item.dataset.shareTitle = 'Dune: Part Two on OmniTrackr';
  const menu = { querySelector: selector => (selector === 'summary' ? summary : null) };
  item.closest = selector => (selector === 'details' ? menu : null);

  assert.equal(share.flashTarget(item), summary);
  assert.equal(await share.share(item), 'copied');
  assert.deepEqual(copied, ['https://omnitrackr.xyz/titles/movie/dune-part-two-2024']);
  assert.equal(summary.textContent, 'Link copied ✓');
  assert.equal(item.textContent, 'Copy or send the link');
});

test('a plain Share button still says Link copied on itself', async () => {
  sharePage();
  const share = require(fresh('share.js'));
  const button = control('Share');
  assert.equal(share.flashTarget(button), button);
  assert.equal(await share.share(button), 'copied');
  assert.equal(button.textContent, 'Link copied ✓');
});

// ------------------------------------------------ phone dock: Home stays lit over the home cards

function dockPage({ panelTop, tabsTop = 176 }) {
  const items = ['home', 'library', 'add', 'feed', 'more'].map(name => {
    const attributes = {};
    return {
      dataset: { dock: name },
      attributes,
      setAttribute(key, value) { attributes[key] = value; },
      removeAttribute(key) { delete attributes[key]; },
      getAttribute(key) { return attributes[key]; },
      addEventListener() {},
    };
  });
  const byDock = Object.fromEntries(items.map(item => [item.dataset.dock, item]));
  const dock = {
    hidden: false,
    querySelector: selector => {
      const match = /data-dock="(\w+)"/.exec(selector);
      return match ? byDock[match[1]] : null;
    },
    querySelectorAll: () => items,
  };
  const sheet = { open: false, addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
  const main = {};
  const tabs = { offsetTop: tabsTop };
  const panel = { offsetParent: {}, getBoundingClientRect: () => ({ top: panelTop - global.window.scrollY }) };
  const listeners = {};
  global.document = {
    body: { dataset: { activeTab: 'movies' }, classList: { toggle() {} } },
    getElementById: id => ({ appDock: dock, appMoreSheet: sheet, mainContainer: main })[id] || null,
    querySelector: selector => ({ '.tabs': tabs, '.tab-content.active': panel })[selector] || null,
    querySelectorAll: () => [],
    addEventListener() {},
  };
  global.window = {
    scrollY: 0,
    addEventListener(type, callback) { listeners[type] = callback; },
    matchMedia: () => ({ matches: false }),
  };
  global.getComputedStyle = () => ({ display: 'block' });
  global.MutationObserver = class { observe() {} };
  global.requestAnimationFrame = callback => callback();
  global.Node = { TEXT_NODE: 3 };
  require(fresh('app-nav.js'));
  return {
    current() { return items.filter(item => item.attributes['aria-current'] === 'page').map(item => item.dataset.dock).join(','); },
    scrollTo(y) { global.window.scrollY = y; listeners.scroll(); },
  };
}

test('the dock says Home over the home cards and Library once the list is at the top', () => {
  const page = dockPage({ panelTop: 5000 });
  assert.equal(page.current(), 'home');
  page.scrollTo(300); // past the tab strip, reading the Your week card
  assert.equal(page.current(), 'home');
  page.scrollTo(4000);
  assert.equal(page.current(), 'home');
  page.scrollTo(5005); // what the dock's own Library button scrolls to
  assert.equal(page.current(), 'library');
});

test('with no home cards above it the list still lights Library as soon as it is reached', () => {
  const page = dockPage({ panelTop: 260 });
  page.scrollTo(100);
  assert.equal(page.current(), 'home');
  page.scrollTo(200);
  assert.equal(page.current(), 'library');
});

// ------------------------------------------------ guest header on a 320px phone

test('the narrowest phones get a tighter guest header', () => {
  const css = fs.readFileSync(path.join(STATIC, 'site.css'), 'utf8');
  const block = css.slice(css.indexOf('@media (max-width: 360px)'));
  const rules = block.slice(0, block.indexOf('\n}'));
  assert.match(rules, /\.site-header \.site-nav \{ gap: 6px; padding: 0 10px; \}/);
  assert.match(rules, /\.site-header \.site-nav__links > \.site-btn \{ font-size: \.8rem; padding: 0 10px; \}/);
});
