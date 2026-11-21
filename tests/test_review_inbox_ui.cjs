// Dashboard "Share your reviews" home card (review-inbox.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.className = ''; this.hidden = false; this.textContent = '';
    this.listeners = {}; this.dataset = {}; this.attributes = {}; this.disabled = false; this.checked = false;
    this.classList = { add: name => { this.className += ` ${name}`; } };
  }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(typeof child === 'string' ? Object.assign(new Node('#text'), { textContent: child }) : child)); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute(name, value) { this.attributes[name] = value; }
  querySelectorAll() { return []; }
  find(predicate) {
    if (predicate(this)) return this;
    for (const child of this.children) { const found = child.find(predicate); if (found) return found; }
    return null;
  }
  get text() { return [this.textContent, ...this.children.map(child => child.text)].join(' ').replace(/\s+/g, ' ').trim(); }
}

function setup(fetchImpl) {
  const ids = ['reviewInbox', 'reviewInboxList', 'reviewInboxSummary', 'reviewInboxHide', 'reviewInboxMore'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  nodes.reviewInbox.hidden = true;
  const notices = [];
  global.localStorage = { store: new Map(), getItem(k) { return this.store.get(k) ?? null; }, setItem(k, v) { this.store.set(k, v); } };
  global.document = { readyState: 'complete', getElementById: id => nodes[id] || null, createElement: tag => new Node(tag), addEventListener() {} };
  global.window = {};
  global.showNotice = (message, tone) => notices.push([message, tone]);
  global.fetch = fetchImpl || (async () => ({ ok: true, json: async () => DATA }));
  delete require.cache[require.resolve('../app/static/review-inbox.js')];
  const module = require(path.join(__dirname, '../app/static/review-inbox.js'));
  module.init();
  return { nodes, module, notices };
}

function item(id, title, extra = {}) {
  return { category: 'movie', library_category: 'movies', id, kind: 'movie', label: 'Movie', title, year: 2014,
    rating: 9, excerpt: `What I thought of ${title}.`, words: 64, version: 'a'.repeat(64), standalone: false,
    first: false, private_list: false, spoilers: false, path: `/titles/movie/${id}`, ...extra };
}

const DATA = {
  total: 5,
  items: [item(1, 'Interstellar <b>', { first: true, standalone: true }), item(2, 'Arrival', { first: true }),
    item(3, 'Heat', { private_list: true }), item(4, 'Alien'), item(5, 'Dune')],
};

test('the card says how many reviews are private and shows three of them as plain text', async () => {
  const { nodes, module } = setup();
  await module.refresh();
  assert.equal(nodes.reviewInbox.hidden, false);
  assert.match(nodes.reviewInboxSummary.textContent, /^You've written 5 reviews that only you can see\. 2 of them would be the first review/);
  assert.match(nodes.reviewInboxSummary.textContent, /Nothing changes unless you press Share\.$/);
  assert.equal(nodes.reviewInboxList.children.length, 2);
  const first = nodes.reviewInboxList.children[0];
  assert.match(first.text, /Interstellar <b> \(2014\)/);
  assert.match(first.text, /Would be the first review on its page/);
  assert.match(first.text, /Long enough for a page of its own/);
  assert.equal(nodes.reviewInboxMore.hidden, false);
  assert.equal(nodes.reviewInboxMore.textContent, 'Show 3 more reviews');
  nodes.reviewInboxMore.listeners.click();
  assert.equal(nodes.reviewInboxList.children.length, 5);
});

test('a private list says so and its title is not linked before sharing', async () => {
  const { nodes, module } = setup();
  await module.refresh();
  nodes.reviewInboxMore.listeners.click();
  const heat = nodes.reviewInboxList.children[2];
  assert.match(heat.text, /Your Movies list is private/);
  assert.equal(heat.find(node => node.className === 'review-inbox__title').tagName, 'span');
  assert.equal(nodes.reviewInboxList.children[0].find(node => node.className === 'review-inbox__title').tagName, 'a');
});

test('Share sends the version and spoiler choice, then offers a link and Undo', async () => {
  const calls = [];
  const { nodes, module, notices } = setup(async (url, options = {}) => {
    calls.push([url, options.body && JSON.parse(options.body)]);
    if (url.endsWith('/share')) return { ok: true, json: async () => ({ shared: true, path: '/titles/movie/1', review_url: '/reviews/1?category=movie' }) };
    return { ok: true, json: async () => DATA };
  });
  await module.refresh();
  const card = nodes.reviewInboxList.children[0];
  card.find(node => node.tagName === 'input').checked = true;
  await card.find(node => node.textContent === 'Share it').listeners.click();
  assert.deepEqual(calls[1], ['/api/review-inbox/share', { category: 'movie', item_id: 1, version: 'a'.repeat(64), spoilers: true }]);
  const done = nodes.reviewInboxList.children[0];
  assert.match(done.text, /Shared\. It's on the Interstellar <b> page and has a page of its own ?\./);
  assert.ok(done.find(node => node.textContent === 'Undo'));
  assert.match(nodes.reviewInboxSummary.textContent, /^You've written 4 reviews/);
  assert.deepEqual(notices.at(-1), ['Your review of Interstellar <b> is public now.', 'success']);
});

test('errors from the server are shown and the buttons come back', async () => {
  const { nodes, module, notices } = setup(async url => {
    if (url.endsWith('/keep')) return { ok: false, json: async () => ({ detail: 'This review changed since the list loaded.' }) };
    return { ok: true, json: async () => DATA };
  });
  await module.refresh();
  await nodes.reviewInboxList.children[1].find(node => node.textContent === 'Keep private').listeners.click();
  assert.deepEqual(notices.at(-1), ['This review changed since the list loaded.', 'error']);
  assert.match(nodes.reviewInboxList.children[1].text, /Keep private/);
});

test('hiding the card keeps it away for a while', async () => {
  let calls = 0;
  const { nodes, module } = setup(async () => { calls += 1; return { ok: true, json: async () => DATA }; });
  await module.refresh();
  nodes.reviewInboxHide.listeners.click();
  assert.equal(nodes.reviewInbox.hidden, true);
  await module.refresh();
  assert.equal(nodes.reviewInbox.hidden, true);
  // While it's hidden the dashboard doesn't ask the server to read every review again.
  assert.equal(calls, 1);
});

test('no reviews to share, or a failed request, leaves the card hidden', async () => {
  let { nodes, module } = setup(async () => ({ ok: true, json: async () => ({ total: 0, items: [] }) }));
  await module.refresh();
  assert.equal(nodes.reviewInbox.hidden, true);
  ({ nodes, module } = setup(async () => ({ ok: false, json: async () => ({}) })));
  await module.refresh();
  assert.equal(nodes.reviewInbox.hidden, true);
});
