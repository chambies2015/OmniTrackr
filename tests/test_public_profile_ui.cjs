// Account → Public profile settings panel.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(id) { this.id = id; this.textContent = ''; this.value = ''; this.checked = false; this.hidden = false; this.href = ''; this.disabled = false; this.style = {}; this.listeners = {}; this.classes = new Set(); this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)) }; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}

function setup(fetchImpl) {
  const ids = ['publicProfileForm', 'profileEnabled', 'profileBio', 'profileBioCount', 'profileShowStats', 'profileShowFavorites',
    'profileShowReviews', 'profileShowCollections', 'profilePrivateNote', 'profileSave', 'profileError', 'profileSuccess',
    'profileLinkRow', 'profileLink', 'profileCopyLink', 'publicProfileSection'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node(id)]));
  global.document = { readyState: 'complete', getElementById: id => nodes[id] || null, addEventListener() {} };
  global.window = { location: { hash: '', origin: 'https://omnitrackr.xyz', pathname: '/', search: '' }, addEventListener() {} };
  global.fetch = fetchImpl || (async () => ({ ok: true, json: async () => ({}) }));
  delete require.cache[require.resolve('../app/static/public-profile.js')];
  const module = require(path.join(__dirname, '../app/static/public-profile.js'));
  return { nodes, module };
}

const SETTINGS = { enabled: true, bio: 'Hi <b>there</b>', show_stats: true, show_favorites: false, show_reviews: true,
  show_collections: true, url: '/u/dan', private_categories: ['Books'], statistics_private: true };

test('settings fill the form and show the link only when enabled', () => {
  const { nodes, module } = setup();
  module.apply(SETTINGS);
  assert.equal(nodes.profileEnabled.checked, true);
  assert.equal(nodes.profileBio.value, 'Hi <b>there</b>');
  assert.equal(nodes.profileShowFavorites.checked, false);
  assert.equal(nodes.profileLinkRow.hidden, false);
  assert.equal(nodes.profileLink.href, '/u/dan');
  assert.equal(nodes.profileLink.textContent, 'omnitrackr.xyz/u/dan');
  assert.match(nodes.profilePrivateNote.textContent, /Books/);
  assert.match(nodes.profilePrivateNote.textContent, /statistics are private/);
  assert.equal(nodes.profileBioCount.textContent, '15/280');
  module.apply({ ...SETTINGS, enabled: false, private_categories: [], statistics_private: false });
  assert.equal(nodes.profileLinkRow.hidden, true);
  assert.equal(nodes.profilePrivateNote.hidden, true);
});

test('a link that is not a profile path is never used', () => {
  const { nodes, module } = setup();
  module.apply({ ...SETTINGS, url: 'javascript:alert(1)' });
  assert.equal(nodes.profileLinkRow.hidden, true);
  assert.equal(nodes.profileLink.href, '');
});

test('save sends every field and shows the server error text as plain text', async () => {
  let sent = null;
  const { nodes, module } = setup(async (url, options) => {
    sent = { url, options };
    return { ok: false, json: async () => ({ detail: 'Bios can\'t include links <a>' }) };
  });
  nodes.profileEnabled.checked = true;
  nodes.profileBio.value = 'see https://x.example';
  nodes.profileShowReviews.checked = true;
  await module.save({ preventDefault() {} });
  assert.equal(sent.url, '/api/profile/settings');
  assert.equal(sent.options.method, 'PUT');
  const body = JSON.parse(sent.options.body);
  assert.deepEqual(Object.keys(body).sort(), ['bio', 'enabled', 'show_collections', 'show_favorites', 'show_reviews', 'show_stats']);
  assert.equal(nodes.profileError.textContent, 'Bios can\'t include links <a>');
  assert.equal(nodes.profileSave.disabled, false);
});

test('an over-long bio is caught before sending', async () => {
  let called = false;
  const { nodes, module } = setup(async () => { called = true; return { ok: true, json: async () => ({}) }; });
  nodes.profileBio.value = 'x'.repeat(281);
  await module.save({ preventDefault() {} });
  assert.equal(called, false);
  assert.match(nodes.profileError.textContent, /280 characters/);
});
