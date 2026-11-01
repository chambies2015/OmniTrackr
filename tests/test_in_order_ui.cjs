// "In order" guides: progress wording, member adds through the guide's endpoint, and "Save all" for visitors.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load(extra = {}) {
  global.document = {
    readyState: 'complete', addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ href: '', textContent: '' }), createTextNode: text => ({ textContent: text }), ...extra,
  };
  global.window = { location: { pathname: '/in-order/alien', href: '', hash: '' } };
  global.localStorage = { getItem: () => null };
  delete require.cache[require.resolve('../app/static/in-order.js')];
  return require(path.join(__dirname, '../app/static/in-order.js'));
}

function statusNode() {
  return { textContent: '', children: [], appendChild(child) { this.children.push(child); return child; } };
}

test('safeUrl keeps only same-site paths', () => {
  const api = load();
  assert.equal(api.safeUrl('/'), '/');
  assert.equal(api.safeUrl('//evil.example'), null);
  assert.equal(api.safeUrl('javascript:alert(1)'), null);
});

test('progress wording covers not started, partway and finished', () => {
  const api = load();
  assert.equal(api.progressText({ done: 0, tracked: 0, total: 7 }), 'Not started yet: 0 of 7');
  assert.equal(api.progressText({ done: 0, tracked: 2, total: 7 }), '2 of 7 on your list, none finished yet');
  assert.equal(api.progressText({ done: 3, tracked: 4, total: 7 }), "You've finished 3 of 7");
  assert.equal(api.progressText({ done: 7, tracked: 7, total: 7 }), "You've finished all 7. Nicely done.");
  assert.equal(api.addAllLabel(1), 'Add the 1 you are missing to my library');
  assert.equal(api.addAllLabel(4), 'Add the 4 you are missing to my library');
});

test('a member add posts the chosen entries to the guide and reports what was added', async () => {
  const api = load();
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/progress')) return { ok: true, status: 200, json: async () => ({ entries: {}, done: 0, total: 7, missing: ['aliens'] }) };
    return { ok: true, status: 200, json: async () => ({ added: [{ id: 'aliens', title: 'Aliens' }], existing: [] }) };
  };
  await api.loadProgress('alien');
  const button = { disabled: false, hasAttribute: name => name === 'data-io-add' };
  const status = statusNode();
  const result = await api.addEntries(['aliens'], button, status);
  assert.equal(calls[1].url, '/api/in-order/alien/add');
  assert.equal(calls[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[1].options.body), { ids: ['aliens'] });
  assert.equal(result.added[0].title, 'Aliens');
  assert.equal(status.textContent, 'Added “Aliens” to your library.');
  assert.equal(status.children[1].href, '/');
  assert.equal(button.disabled, true);
});

test('a failed add re-enables the button', async () => {
  const api = load();
  global.fetch = async url => (url.endsWith('/progress')
    ? { ok: true, status: 200, json: async () => ({ entries: {}, done: 0, total: 1, missing: [] }) }
    : { ok: false, status: 500 });
  await api.loadProgress('alien');
  const button = { disabled: false, hasAttribute: () => false };
  const status = statusNode();
  assert.equal(await api.addEntries(['aliens'], button, status), null);
  assert.equal(button.disabled, false);
  assert.match(status.textContent, /Could not add/);
});

test('"Save all" adds every main entry to the guest list once', () => {
  const tiles = [
    { dataset: { guestKind: 'movie', guestSlug: 'alien-1979', guestTitle: 'Alien' } },
    { dataset: { guestKind: 'movie', guestSlug: 'aliens-1986', guestTitle: 'Aliens' } },
  ];
  const status = statusNode();
  const api = load({
    querySelectorAll: selector => (selector.includes('[data-guest-kind]') ? tiles : []),
    querySelector: selector => (selector === '[data-io-status]' ? status : null),
  });
  const saved = new Set(['movie/alien-1979']);
  let refreshed = 0;
  global.window.OmniGuestList = {
    MAX: 30,
    add(kind, slug) {
      const key = `${kind}/${slug}`;
      if (saved.has(key)) return { added: false };
      saved.add(key);
      return { added: true };
    },
    refreshTiles() { refreshed += 1; },
  };
  const button = { textContent: '' };
  assert.equal(api.saveAllForGuest(button), 1);
  assert.equal(refreshed, 1);
  assert.match(status.textContent, /^Saved 1 to your list/);
  assert.equal(button.textContent, 'Saved to your list ✓');
});
