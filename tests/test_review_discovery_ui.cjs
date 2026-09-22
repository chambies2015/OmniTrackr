// Run with: node --test tests/test_review_discovery_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/reviews.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};
const review = (id, category = 'book', values = {}) => ({
  id, category, title: `Title ${id}`, review: 'A thoughtful opinion with enough context for another reader.',
  username: 'reader', rating: 8, year: 2024, search_ready: true, ...values,
});
const envelope = (reviews, next = reviews.length, more = false) => ({ reviews, next_offset: next, has_more: more });
const ok = body => ({ ok: true, json: async () => body });

function setup({ hasMore = true, offset = 20, category = '', q = '', empty = false } = {}) {
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attributes = {};
      this.listeners = {}; this.value = ''; this.hidden = false; this.disabled = false;
      this.className = ''; this._text = ''; this.style = {};
      this.classList = { add: name => { this.className += ` ${name}`; } };
    }
    set textContent(value) { this.replaceChildren(); this._text = String(value); }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set innerHTML(_) { throw new Error('User content must not be parsed as markup'); }
    appendChild(child) { this.children.push(child); child.parentElement = this; return child; }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return this.attributes[name] ?? null; }
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
    emit(type) { this.listeners[type]?.forEach(callback => callback({ preventDefault() {}, target: this })); }
    querySelectorAll(selector) {
      const match = element => {
        if (selector === '[data-review-key]') return element.dataset.reviewKey !== undefined;
        if (selector[0] === '.') return element.className.split(' ').includes(selector.slice(1));
        return element.tagName.toLowerCase() === selector;
      };
      return this.children.flatMap(child => [...(match(child) ? [child] : []), ...child.querySelectorAll(selector)]);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  const elements = new Map();
  const add = (id, tag = 'div') => { const element = new Element(tag); element.id = id; elements.set(id, element); return element; };
  const get = id => elements.get(id);
  const container = add('reviewsContainer');
  container.dataset = { category, query: q, nextOffset: String(offset), hasMore: String(hasMore), hydrated: 'true' };
  const ssr = new Element('article');
  ssr.dataset.reviewKey = 'book:100'; ssr.textContent = 'Original server review';
  if (!empty) container.appendChild(ssr);
  else { const section = new Element('section'); section.textContent = 'Curated empty state'; container.appendChild(section); }
  const form = add('reviewFilters', 'form');
  add('categoryFilter', 'select').value = category;
  add('reviewSearch', 'input').value = q;
  add('loadMoreReviews', 'button'); add('retryReviews', 'button'); add('reviewFeedStatus');
  const collectionSchema = new Element('script');
  collectionSchema.textContent = JSON.stringify({ '@type': 'CollectionPage', mainEntity: { '@type': 'ItemList', itemListElement: [{ name: 'Original server review' }] } });
  const organizationSchema = new Element('script');
  organizationSchema.textContent = JSON.stringify({ '@type': 'Organization', name: 'OmniTrackr' });
  const document = {
    listeners: {}, getElementById: get, createElement: tag => new Element(tag),
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); },
    querySelectorAll(selector) { return selector === 'script[type="application/ld+json"]' ? [collectionSchema, organizationSchema] : []; },
  };
  const requests = [], reports = [], timers = new Map(), windowListeners = {}; let timerId = 0;
  const context = vm.createContext({
    document, AbortController, URL, URLSearchParams, HTMLImageElement: Element,
    setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url, options) {
      // Ignore cancellation deliberately: an already-decoding response can still arrive.
      const request = { url, options, ...deferred() }; requests.push(request); return request.promise;
    },
    window: {
      addEventListener(type, callback) { windowListeners[type] = callback; },
      createReviewReportControls(category, id) { reports.push({ category, id }); const report = new Element('details'); report.className = 'review-report'; return report; },
    },
  });
  vm.runInContext(source, context);
  document.listeners.DOMContentLoaded.forEach(callback => callback());
  return {
    get, context, container, ssr, form, requests, reports, timers, collectionSchema, organizationSchema,
    start(nextCategory = '', nextQuery = '') { get('categoryFilter').value = nextCategory; get('reviewSearch').value = nextQuery; return context.loadReviews(); },
    respond(index, body) { requests[index].resolve(ok(body)); },
    cards() { return container.querySelectorAll('[data-review-key]'); },
    timeout() { [...timers.values()].forEach(callback => callback()); },
    hide() { windowListeners.pagehide(); },
  };
}

test('initialization preserves server cards, order and paging without a fetch', () => {
  const s = setup();
  assert.equal(s.requests.length, 0);
  assert.equal(s.cards()[0], s.ssr);
  assert.equal(s.get('loadMoreReviews').hidden, false);
  assert.match(s.get('reviewFeedStatus').textContent, /1 review to explore/);
  assert.equal(JSON.parse(s.collectionSchema.textContent).mainEntity.itemListElement.length, 1);
});

test('empty server content is preserved without a duplicate request', () => {
  const s = setup({ empty: true, hasMore: false });
  assert.equal(s.requests.length, 0);
  assert.match(s.container.textContent, /Curated empty state/);
  assert.equal(s.get('loadMoreReviews').hidden, true);
});

test('rapid category changes cancel old work and latest results win', async () => {
  const s = setup();
  s.get('categoryFilter').value = 'movie'; s.get('categoryFilter').emit('change');
  s.get('categoryFilter').value = 'music'; s.get('categoryFilter').emit('change');
  assert.equal(s.requests.length, 2);
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.cards()[0], s.ssr, 'usable content stays while the replacement loads');
  s.respond(1, envelope([review(2, 'music')])); await settle();
  s.respond(0, envelope([review(1, 'movie')])); await settle();
  assert.equal(s.cards().length, 1);
  assert.equal(s.cards()[0].dataset.reviewKey, 'music:2');
  assert.match(s.get('reviewFeedStatus').textContent, /Music/);
  assert.equal(s.timers.size, 0);
});

test('a late JSON decode cannot replace a newer search', async () => {
  const s = setup(); const body = deferred();
  const first = s.start('book', 'older');
  s.requests[0].resolve({ ok: true, json: () => body.promise }); await settle();
  const second = s.start('book', 'newer');
  s.respond(1, envelope([review(2)])); await second;
  body.resolve(envelope([review(1)])); await first;
  assert.equal(s.cards()[0].dataset.reviewKey, 'book:2');
});

test('a failed replacement preserves cards and retry uses the failed filter context', async () => {
  const s = setup(); const first = s.start('movie', 'Dune');
  s.requests[0].resolve({ ok: false, status: 503 }); await first;
  assert.equal(s.cards()[0], s.ssr);
  assert.match(s.get('reviewFeedStatus').textContent, /Movies matching “Dune”/);
  assert.match(s.get('reviewFeedStatus').textContent, /displayed reviews are still here/);
  assert.equal(s.get('retryReviews').hidden, false);
  assert.equal(s.get('loadMoreReviews').hidden, true);
  s.get('reviewSearch').value = 'Unsubmitted edit';
  s.get('retryReviews').emit('click');
  assert.equal(new URL(s.requests[1].url, 'https://example.test').searchParams.get('q'), 'Dune');
  s.respond(1, envelope([review(1, 'movie')])); await settle();
  assert.equal(s.cards()[0].dataset.reviewKey, 'movie:1');
  assert.equal(s.get('retryReviews').hidden, true);
});

test('load more retries the same offset, retains prior cards and deduplicates category plus id', async () => {
  const s = setup({ category: 'book', q: 'Title' });
  const failed = s.context.loadReviews(false);
  s.requests[0].reject(new Error('offline')); await failed;
  assert.equal(s.cards()[0], s.ssr);
  s.get('retryReviews').emit('click');
  assert.equal(new URL(s.requests[1].url, 'https://example.test').searchParams.get('offset'), '20');
  s.respond(1, envelope([review(100), review(3), review(3), review(3, 'movie')], 24, true)); await settle();
  assert.equal(s.cards().length, 3);
  assert.equal(s.cards()[0], s.ssr);
  const more = s.context.loadReviews(false);
  assert.equal(new URL(s.requests[2].url, 'https://example.test').searchParams.get('offset'), '24');
  s.respond(2, envelope([], 24)); await more;
  assert.equal(s.get('loadMoreReviews').hidden, true);
});

test('repeated load-more clicks do not issue overlapping page requests', async () => {
  const s = setup(); const pending = s.context.loadReviews(false);
  await s.context.loadReviews(false);
  assert.equal(s.requests.length, 1);
  assert.equal(s.get('loadMoreReviews').disabled, true);
  s.respond(0, envelope([review(1)], 21)); await pending;
});

test('a new filter interrupts pending pagination without appending the old page', async () => {
  const s = setup(); const more = s.context.loadReviews(false);
  const reset = s.start('anime', 'new');
  s.respond(1, envelope([review(5, 'anime')])); await reset;
  s.respond(0, envelope([review(9)], 21)); await more;
  assert.equal(s.cards().length, 1);
  assert.equal(s.cards()[0].dataset.reviewKey, 'anime:5');
});

test('timeouts including hung JSON leave content usable and ignore a late response', async () => {
  const s = setup(); const body = deferred(); const pending = s.start('book');
  s.requests[0].resolve({ ok: true, json: () => body.promise }); await settle();
  s.timeout(); await pending;
  assert.equal(s.cards()[0], s.ssr);
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.get('retryReviews').hidden, false);
  body.resolve(envelope([review(1)])); await settle();
  assert.equal(s.cards()[0], s.ssr);
  assert.equal(s.timers.size, 0);
});

test('malformed responses never clear the visible cards', async () => {
  for (const body of [null, [], { reviews: [], has_more: true, next_offset: 0 }, envelope([review(1), review(2, 'unknown')])]) {
    const s = setup(); const pending = s.start(); s.respond(0, body); await pending;
    assert.equal(s.cards()[0], s.ssr);
    assert.equal(s.get('retryReviews').hidden, false);
  }
});

test('an empty successful search replaces stale reviews with a helpful empty state', async () => {
  const s = setup(); const pending = s.start('movie', 'No title'); s.respond(0, envelope([])); await pending;
  assert.equal(s.cards().length, 0);
  assert.match(s.container.textContent, /Try another title or choose All media/);
  assert.equal(s.get('loadMoreReviews').hidden, true);
  assert.equal(s.get('retryReviews').hidden, true);
});

test('form search trims and encodes a bounded title without auto-fetching edits', async () => {
  const s = setup(); s.get('reviewSearch').value = '  Dune & friends  ';
  s.get('reviewSearch').emit('input');
  assert.equal(s.requests.length, 0);
  s.form.emit('submit');
  assert.equal(new URL(s.requests[0].url, 'https://example.test').searchParams.get('q'), 'Dune & friends');
  assert.equal(s.requests[0].options.method, undefined, 'search only reads the feed');
  s.respond(0, envelope([])); await settle();
  const pending = s.start('', 'x'.repeat(110));
  assert.equal(new URL(s.requests[1].url, 'https://example.test').searchParams.get('q').length, 100);
  s.respond(1, envelope([])); await pending;
});

test('cards use real separate read/save links, safe text, and preserve a zero rating', () => {
  const s = setup();
  const card = s.context.createReviewCard(review(1, 'book', { title: '<script>unsafe</script>', rating: 0, poster_url: 'javascript:alert(1)' }));
  assert.equal(card.tagName, 'ARTICLE');
  assert.equal(card.querySelector('.review-title-link').textContent, '<script>unsafe</script>');
  assert.equal(card.querySelector('.review-title-link').href, '/reviews/1?category=book');
  assert.equal(card.querySelector('.review-save-link').href, '/reviews/1/save?category=book');
  assert.equal(card.querySelector('.review-rating').textContent, 'Rating: 0/10');
  assert.equal(card.querySelector('img').src, '/static/default-avatar.svg');
  assert.equal(card.listeners.click, undefined, 'card does not hijack nested actions');
  assert.equal(s.reports.length, 0);
});

test('summary reviews retain full long text and report controls without a dead detail link', () => {
  const s = setup(); const full = 'A long personal review. '.repeat(30);
  const card = s.context.createReviewCard(review(2, 'music', { search_ready: false, review: full }));
  assert.equal(card.querySelector('.review-title-link'), null);
  assert.equal(card.querySelector('.review-detail-link'), null);
  assert.equal(card.querySelector('.review-full-text').querySelector('p').textContent, full.trim());
  assert.equal(card.querySelector('.review-save-link').href, '/reviews/2/save?category=music');
  assert.equal(s.reports.length, 1);
  assert.equal(s.reports[0].category, 'music');
});

test('filter replacement clears only stale review structured data', async () => {
  const s = setup(); const organization = s.organizationSchema.textContent;
  const pending = s.start('book'); s.respond(0, envelope([review(1)])); await pending;
  assert.equal(JSON.parse(s.collectionSchema.textContent).mainEntity.itemListElement.length, 0);
  assert.equal(s.organizationSchema.textContent, organization);
  assert.equal(s.context.document.title, undefined, 'server metadata is not promoted by client filtering');
});

test('leaving the page cancels work and a restored page can retry without stale results', async () => {
  const s = setup(); const pending = s.start('movie', 'Dune');
  s.hide(); await pending;
  assert.equal(s.requests[0].options.signal.aborted, true);
  assert.equal(s.timers.size, 0);
  assert.equal(s.container.getAttribute('aria-busy'), 'false');
  assert.equal(s.get('retryReviews').hidden, false);
  s.respond(0, envelope([review(1, 'movie')])); await settle();
  assert.equal(s.cards()[0], s.ssr);
  s.get('retryReviews').emit('click');
  s.respond(1, envelope([review(2, 'movie')])); await settle();
  assert.equal(s.cards()[0].dataset.reviewKey, 'movie:2');
});

test('superseded requests release timers even when the network ignores cancellation', async () => {
  const s = setup(); const first = s.start('book', 'older');
  const second = s.start('book', 'newer');
  await first;
  assert.equal(s.timers.size, 1);
  s.respond(1, envelope([review(2)])); await second;
  assert.equal(s.timers.size, 0);
});
