// Profile widgets page (/u/<name>/widgets) and the widgets panel in Settings → Public profile.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(attrs = {}) {
    this.attrs = { ...attrs };
    this.classes = new Set();
    this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)), contains: c => this.classes.has(c) };
    this.listeners = {};
    this.children = [];
    this.value = attrs.value || '';
    this.textContent = '';
    this.hidden = false;
    this.style = {};
    this.dataset = {};
  }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    if (selector === 'img[data-widget-variant]') return this.children.filter(child => child.attrs.tag === 'img');
    if (selector === 'textarea[data-widget-field]') return this.children.filter(child => child.attrs['data-widget-field']);
    return [];
  }
}

const CODES = {
  signature: {
    'dark-png': { html: 'dark png html', markdown: 'dark png md', preview: '/u/dan/widget/signature.png?scale=2' },
    'light-png': { html: 'light png html', markdown: 'light png md', preview: '/u/dan/widget/signature.png?theme=light&scale=2' },
    'dark-svg': { html: 'dark svg html', markdown: 'dark svg md', preview: '/u/dan/widget/signature.svg' },
    'auto-svg': { html: 'auto svg html', markdown: 'auto svg md', preview: '/u/dan/widget/signature.svg?theme=auto' },
  },
  badge: { 'auto-svg': { html: 'badge auto', markdown: 'badge md', preview: 'javascript:alert(1)' } },
};

function setupPage() {
  const buttons = ['dark', 'light', 'auto'].map(theme => new Node({ 'data-widget-theme': theme }))
    .concat(['png', 'svg'].map(format => new Node({ 'data-widget-format': format })));
  const card = new Node({ 'data-widget-kind': 'signature' });
  const imgs = Object.fromEntries(['dark-png', 'light-png', 'dark-svg', 'light-svg', 'auto-svg']
    .map(key => [key, new Node({ tag: 'img', 'data-widget-variant': key })]));
  Object.entries(imgs).forEach(([key, node]) => { node.hidden = key !== 'dark-png'; });
  const img = { getAttribute: () => (Object.entries(imgs).find(([, node]) => !node.hidden) || [null])[0] };
  const html = new Node({ 'data-widget-field': 'html' });
  const markdown = new Node({ 'data-widget-field': 'markdown' });
  card.children.push(...Object.values(imgs), html, markdown);
  const badge = new Node({ 'data-widget-kind': 'badge' });
  const badgeImg = new Node({ tag: 'img', 'data-widget-variant': 'dark-png' });
  badge.children.push(badgeImg);
  const hint = new Node();
  const codes = new Node();
  codes.textContent = JSON.stringify(CODES);
  const body = new Node();
  const sent = [];
  global.document = {
    readyState: 'complete',
    body,
    getElementById: id => ({ widgetHint: hint, widgetCodes: codes })[id] || null,
    querySelectorAll: selector => {
      if (selector === '[data-widget-theme]') return buttons.filter(b => b.attrs['data-widget-theme']);
      if (selector === '[data-widget-format]') return buttons.filter(b => b.attrs['data-widget-format']);
      if (selector === '[data-widget-kind]') return [card, badge];
      return [];
    },
    addEventListener() {},
  };
  global.fetch = async (url, options) => { sent.push({ url, body: JSON.parse(options.body) }); return { ok: true }; };
  delete require.cache[require.resolve('../app/static/profile-widgets.js')];
  const module = require(path.join(__dirname, '../app/static/profile-widgets.js'));
  return { module, buttons, img, html, markdown, hint, body, badgeImg, sent };
}

test('picking colors and file swaps every code and preview', () => {
  const { module, buttons, img, html, markdown, hint, body } = setupPage();
  module.readCodes();
  module.pickTheme('light');
  assert.equal(html.value, 'light png html');
  assert.equal(img.getAttribute('src'), 'light-png');  // the one preview still showing
  assert.equal(body.classes.has('is-light'), true);
  assert.equal(buttons[1].getAttribute('aria-pressed'), 'true');
  module.pickTheme('dark');
  module.pickFormat('svg');
  assert.equal(markdown.value, 'dark svg md');
  assert.match(hint.textContent, /Some forums/);
});

test('auto needs SVG, and PNG takes auto back to dark', () => {
  const { module, buttons, html, hint, sent } = setupPage();
  module.readCodes();
  module.pickTheme('auto');
  assert.equal(module.state.format, 'svg');
  assert.equal(html.value, 'auto svg html');
  assert.equal(buttons.find(b => b.attrs['data-widget-format'] === 'svg').getAttribute('aria-pressed'), 'true');
  assert.match(hint.textContent, /light or dark mode/);
  module.pickFormat('png');
  assert.equal(module.state.theme, 'dark');
  assert.equal(html.value, 'dark png html');
  assert.deepEqual(sent.map(item => item.body.key), ['pick_auto']);
  module.pickTheme('nonsense');
  assert.equal(module.state.theme, 'dark');
});

test('only the preview for the picked pairing shows', () => {
  const { module, badgeImg } = setupPage();
  module.readCodes();
  module.pickTheme('auto');
  // The badge card has no auto SVG image in this page, so its dark PNG hides rather than showing the wrong one.
  assert.equal(badgeImg.hidden, true);
  module.pickTheme('dark');
  module.pickFormat('png');
  assert.equal(badgeImg.hidden, false);
});

// ---------------------------------------------------------------- Settings panel

class SettingsNode {
  constructor(id) { this.id = id; this.textContent = ''; this.value = ''; this.checked = false; this.hidden = false; this.href = ''; this.src = ''; this.disabled = false; this.style = {}; this.listeners = {}; this.classes = new Set(); this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)) }; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}

function setupSettings(fetchImpl) {
  const ids = ['publicProfileForm', 'profileEnabled', 'profileBio', 'profileBioCount', 'profileShowStats', 'profileShowFavorites',
    'profileShowReviews', 'profileShowCollections', 'profileShowDiary', 'profilePrivateNote', 'profileSave', 'profileError',
    'profileSuccess', 'profileLinkRow', 'profileLink', 'profileCopyLink', 'publicProfileSection', 'profileWidgetsRow',
    'profileWidgetsLink', 'profileWidgetsPreview', 'profileWidgetsPreviewLink', 'profileWidgetsLoads', 'profileWidgetsCopy',
    'profileWidgetsCopied'];
  const nodes = Object.fromEntries(ids.map(id => [id, new SettingsNode(id)]));
  global.document = { readyState: 'complete', getElementById: id => nodes[id] || null, addEventListener() {} };
  global.window = { location: { hash: '', origin: 'https://omnitrackr.xyz', pathname: '/', search: '' }, addEventListener() {} };
  global.fetch = fetchImpl;
  delete require.cache[require.resolve('../app/static/public-profile.js')];
  const module = require(path.join(__dirname, '../app/static/public-profile.js'));
  return { nodes, module };
}

const PANEL = { enabled: true, page: '/u/dan/widgets', preview: '/u/dan/widget/signature.png?scale=2',
  preview_light: '/u/dan/widget/signature.png?theme=light&scale=2', forum_code: '[url=x][img]y[/img][/url]',
  summary: 'Your widgets were loaded 4 times in the last 7 days, on myanimelist.net.', loads: 4, sites: ['myanimelist.net'] };

test('the Settings panel shows the signature, its loads and the forum code', async () => {
  const urls = [];
  const { nodes, module } = setupSettings(async url => {
    urls.push(url);
    return { ok: true, json: async () => PANEL };
  });
  await module.loadWidgets();
  assert.deepEqual(urls, ['/api/profile/widgets']);
  assert.equal(nodes.profileWidgetsPreviewLink.hidden, false);
  assert.equal(nodes.profileWidgetsPreviewLink.href, '/u/dan/widgets');
  assert.match(nodes.profileWidgetsPreview.src, /^\/u\/dan\/widget\/signature\.png\?scale=2&v=\d+$/);
  assert.equal(nodes.profileWidgetsLoads.textContent, PANEL.summary);
  assert.equal(nodes.profileWidgetsCopy.hidden, false);
  let copied = '';
  Object.defineProperty(globalThis, 'navigator', { value: { clipboard: { writeText: async text => { copied = text; } } }, configurable: true });
  await module.copyForumCode();
  assert.equal(copied, PANEL.forum_code);
  assert.match(nodes.profileWidgetsCopied.textContent, /signature box/);
  assert.equal(urls[1], '/api/widgets/event');
});

test('a switched-off profile or odd addresses leave the panel empty', () => {
  const { nodes, module } = setupSettings(async () => ({ ok: true, json: async () => ({}) }));
  module.showWidgets({ enabled: false });
  assert.equal(nodes.profileWidgetsPreviewLink.hidden, true);
  assert.equal(nodes.profileWidgetsLoads.hidden, true);
  assert.equal(nodes.profileWidgetsCopy.hidden, true);
  module.showWidgets({ ...PANEL, preview: 'javascript:alert(1)', page: '//evil.example/u/x' });
  assert.equal(nodes.profileWidgetsPreviewLink.hidden, true);
  assert.equal(nodes.profileWidgetsPreview.src, '');
});

test('saving an enabled profile loads the panel once', async () => {
  let calls = 0;
  const { nodes, module } = setupSettings(async url => {
    if (url.endsWith('/api/profile/widgets')) calls += 1;
    return { ok: true, json: async () => PANEL };
  });
  module.apply({ enabled: true, url: '/u/dan', bio: '' });
  module.apply({ enabled: true, url: '/u/dan', bio: '' });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(nodes.profileWidgetsRow.hidden, false);
  assert.ok(calls >= 1 && calls <= 2);
  module.apply({ enabled: false, url: '/u/dan', bio: '' });
  assert.equal(nodes.profileWidgetsRow.hidden, true);
});
