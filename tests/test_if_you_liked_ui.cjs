// "If you liked" guides: members add a pick through Pick for me's endpoint; only same-site links are followed.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = { readyState: 'complete', addEventListener() {} };
  global.window = { location: { pathname: '/if-you-liked/interstellar', href: '' } };
  global.localStorage = { getItem: () => null };
  delete require.cache[require.resolve('../app/static/if-you-liked.js')];
  return require(path.join(__dirname, '../app/static/if-you-liked.js'));
}

function button(id) {
  const status = { textContent: '', children: [], appendChild(child) { this.children.push(child); return child; } };
  return {
    dataset: { likedAdd: id }, disabled: false, textContent: 'Add to my library', status,
    closest: () => ({ querySelector: () => status }),
  };
}

test('safeUrl keeps only same-site paths', () => {
  const api = load();
  assert.equal(api.safeUrl('/?library_category=movies&library_item=3'), '/?library_category=movies&library_item=3');
  assert.equal(api.safeUrl('//evil.example'), null);
  assert.equal(api.safeUrl('javascript:alert(1)'), null);
  assert.equal(api.safeUrl(null), null);
});

test('a member add posts the pick with its source and shows a safe link', async () => {
  const api = load();
  const calls = [];
  global.document.createElement = tag => ({ tagName: tag, href: '', textContent: '' });
  global.document.createTextNode = text => ({ textContent: text });
  global.fetch = async (url, options) => {
    calls.push([url, JSON.parse(options.body)]);
    return { ok: true, status: 200, json: async () => ({ state: 'created', title: 'Outer Wilds', library_url: '//evil.example' }) };
  };
  const node = button('game/outer-wilds-2019');
  await api.addToLibrary(node);
  assert.deepEqual(calls, [['/api/pick/add', { id: 'game/outer-wilds-2019', source: 'if-you-liked' }]]);
  assert.equal(node.textContent, 'Added ✓');
  assert.match(node.status.textContent, /Outer Wilds/);
  assert.equal(node.status.children[1].href, '/');
});

test('a signed-out add sends the visitor to log in and come back', async () => {
  const api = load();
  global.fetch = async () => ({ ok: false, status: 401 });
  await api.addToLibrary(button('game/outer-wilds-2019'));
  assert.equal(global.window.location.href, '/?next=%2Fif-you-liked%2Finterstellar#landing-auth');
});
