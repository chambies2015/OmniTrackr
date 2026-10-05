// Finish modal: optional review step after finishing a title (Oct 2026).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../app/templates/index.html'), 'utf8');

function setup(routes) {
  const elements = new Map();
  const make = (id) => ({ id, value: '', dataset: {}, checked: false, hidden: false, textContent: '', style: {}, children: [],
    replaceChildren(...kids) { this.children = kids; }, appendChild(kid) { this.children.push(kid); } });
  const get = id => { if (!elements.has(id)) elements.set(id, make(id)); return elements.get(id); };
  const calls = [];
  const alerts = [];
  let reloads = 0;
  const context = vm.createContext({
    document: { getElementById: get, createElement: () => make(), createTextNode: text => ({ text }) },
    API_BASE: '', alert: message => alerts.push(message), loadMonthlyReplay() {},
    async authenticatedFetch(url, options) {
      calls.push({ url, body: options && options.body ? JSON.parse(options.body) : null });
      const route = routes(url, options);
      return { ok: route.status < 400, status: route.status, json: async () => route.body };
    },
  });
  context.globalThis = context;
  context.loadMovies = () => { reloads++; };
  const start = source.indexOf('let activeCompletionMomentId = null;');
  vm.runInContext(source.slice(start, source.indexOf('function renderMonthlyReplay(replay)', start)), context);
  return { context, get, calls, alerts, reloads: () => reloads };
}

const moment = (hasReview) => ({ status: 200, body: { id: 7, title: 'Arrival', takeaway: null, favorite: false, has_review: hasReview } });

test('modal markup has the review step, privacy choice and live counter', () => {
  for (const id of ['completionReviewStep', 'completionReviewText', 'completionReviewPublic', 'completionReviewCount', 'completionReviewResult', 'completionRitualSave']) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  assert.match(html, /id="completionReviewStep"[^>]*hidden/);
});

test('word hints follow the review thresholds', () => {
  const { context } = setup(() => ({ status: 200 }));
  assert.equal(context.countReviewWords("It's a slow-burn, but worth it."), 7);
  assert.equal(context.completionReviewHint(0), '');
  assert.match(context.completionReviewHint(1), /^1 word:/);
  assert.match(context.completionReviewHint(20), /own page/);
  assert.match(context.completionReviewHint(60), /can have its own review page/);
  assert.match(context.completionReviewHint(200), /thorough/);
});

test('review step shows only when the title has no review yet', async () => {
  for (const [hasReview, hidden] of [[false, false], [true, true]]) {
    const s = setup(() => moment(hasReview));
    await s.context.openCompletionMoment('movies', 3);
    assert.equal(s.get('completionReviewStep').hidden, hidden);
    assert.equal(s.get('completionReviewPublic').checked, true);
    assert.equal(s.get('completionRitualSave').dataset.action, 'save-completion-ritual');
  }
});

test('reflection only: saves and closes without posting a review', async () => {
  const s = setup(url => url.endsWith('/completion-moments/') ? moment(false) : { status: 200, body: {} });
  await s.context.openCompletionMoment('movies', 3);
  await s.context.saveCompletionRitual();
  assert.deepEqual(s.calls.map(c => c.url), ['/completion-moments/', '/completion-moments/7']);
  assert.equal(s.get('completionRitualModal').style.display, 'none');
});

test('public review is posted, linked and the library refreshed', async () => {
  const s = setup(url => {
    if (url.endsWith('/completion-moments/')) return moment(false);
    if (url.endsWith('/review')) return { status: 200, body: { public: true, listed: true, standalone: true, review_url: '/reviews/3?category=movie' } };
    return { status: 200, body: {} };
  });
  await s.context.openCompletionMoment('movies', 3);
  s.get('completionReviewText').value = '  A patient, moving film about language and grief.  ';
  s.get('completionReviewText').oninput();
  assert.equal(s.get('completionRitualSave').textContent, 'Save reflection and review');
  await s.context.saveCompletionRitual();
  const post = s.calls.find(c => c.url === '/completion-moments/7/review');
  assert.deepEqual(post.body, { review: 'A patient, moving film about language and grief.', public: true });
  const result = s.get('completionReviewResult');
  assert.equal(result.hidden, false);
  assert.equal(result.children[1].href, '/reviews/3?category=movie');
  assert.equal(s.reloads(), 1);
  assert.equal(s.get('completionRitualSave').dataset.action, 'close-completion-ritual');
  assert.equal(s.get('completionRitualSkip').hidden, true);
});

test('private, too-short and conflicting reviews get honest messages', async () => {
  const cases = [
    [{ status: 200, body: { public: false } }, /Only you can see it/],
    [{ status: 200, body: { public: true, listed: false, standalone: false } }, /little short/],
    [{ status: 200, body: { public: true, listed: true, standalone: false } }, /reviews page/],
    [{ status: 409, body: {} }, /already has a review/],
  ];
  for (const [reply, pattern] of cases) {
    const s = setup(url => url.endsWith('/completion-moments/') ? moment(false) : url.endsWith('/review') ? reply : { status: 200, body: {} });
    await s.context.openCompletionMoment('movies', 3);
    s.get('completionReviewText').value = 'Some thoughts.';
    await s.context.saveCompletionRitual();
    assert.match(s.get('completionReviewResult').children[0].text, pattern);
  }
});

test('a failed review save keeps the text for another try', async () => {
  const s = setup(url => url.endsWith('/completion-moments/') ? moment(false) : url.endsWith('/review') ? { status: 500 } : { status: 200, body: {} });
  await s.context.openCompletionMoment('movies', 3);
  s.get('completionReviewText').value = 'Keep me.';
  await s.context.saveCompletionRitual();
  assert.equal(s.get('completionReviewText').value, 'Keep me.');
  assert.match(s.alerts[0], /still here/);
});

test('only on-site review links are rendered', () => {
  const s = setup(() => ({ status: 200 }));
  s.context.showCompletionResult({ text: 'x', link: 'https://evil.example', linkText: 'See' });
  assert.equal(s.get('completionReviewResult').children.length, 1);
});
