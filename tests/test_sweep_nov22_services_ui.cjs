// Nov 22 2026 sweep of the "On your services" share link on the home card (streaming.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function node(tag) {
  return {
    tag, className: '', textContent: '', hidden: false, children: [], listeners: {},
    append(...kids) { this.children.push(...kids); },
    appendChild(kid) { this.children.push(kid); return kid; },
    replaceChildren(...kids) { this.children = kids; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    querySelector() { return null; },
  };
}

function text(element) {
  return [element.textContent, ...element.children.map(text)].join(' ');
}

function load(nodes) {
  global.document = {
    readyState: 'loading', addEventListener() {}, getElementById: id => nodes[id] || null,
    querySelectorAll() { return []; }, createElement: node,
  };
  global.window = { addEventListener() {}, location: { hash: '', origin: 'https://omnitrackr.xyz' } };
  const file = path.join(__dirname, '..', 'app', 'static', 'streaming.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const LINK = '/on-my-services/abcdefghijklmnop';

test('a link out while services are cleared shows as paused with a way to turn it off', () => {
  const nodes = { onYourServicesShare: node('div'), onYourServicesPrivacy: node('p') };
  const ui = load(nodes);
  ui.renderShare({ state: 'choose', share: { path: LINK, allowed: false, reason: 'services', opened: 2, left_out: [] } });
  const box = nodes.onYourServicesShare;
  assert.equal(box.hidden, false);
  assert.match(text(box), /Your share link is paused/);
  assert.match(text(box), /Turn off/);
  // No link and nothing to share yet: nothing shows.
  ui.renderShare({ state: 'choose', share: null });
  assert.equal(box.hidden, true);
});

test('the card says which formats stay off the link', () => {
  const ui = load({});
  assert.equal(ui.leftOut({ left_out: [] }), '');
  assert.equal(ui.leftOut({}), '');
  assert.equal(ui.leftOut({ left_out: ['anime'] }), ' Your anime stays off it, because that shelf is private or hidden.');
  assert.equal(ui.leftOut({ left_out: ['movies', 'tv-shows'] }),
    ' Your films and shows stay off it, because those shelves are private or hidden.');
  assert.equal(ui.leftOut({ left_out: ['<b>'] }), '');
  const nodes = { onYourServicesShare: node('div') };
  const card = load(nodes);
  card.renderShare({ state: 'list', share: { path: LINK, allowed: true, reason: null, opened: 0, left_out: ['tv-shows'] } });
  assert.match(text(nodes.onYourServicesShare), /Your shows stay off it/);
});

test('hiding the card says the link keeps working', () => {
  const source = require('node:fs').readFileSync(path.join(__dirname, '..', 'app', 'static', 'streaming.js'), 'utf8');
  assert.ok(source.includes('Your share link still works, and you can turn it off from its page.'));
});
