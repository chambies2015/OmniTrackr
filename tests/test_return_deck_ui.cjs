// Run with: node --test tests/test_return_deck_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const returnDeckSource = source.slice(
  source.indexOf("const LAUNCHPAD_DISMISS_KEY"),
  source.indexOf('function isLibraryLaunchpadDismissed'),
);

function setup(storedContext = null) {
  const storage = new Map();
  if (storedContext !== null) {
    storage.set('omnitrackr_return_prompt', JSON.stringify(storedContext));
  }
  const requests = [];
  const elements = new Map();
  function makeElement() {
    return {
      hidden: true,
      children: [],
      className: '',
      dataset: {},
      textContent: '',
      replaceChildren() { this.children = []; },
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); },
      removeAttribute(name) { if (name === 'hidden') this.hidden = false; },
      setAttribute(name) { if (name === 'hidden') this.hidden = true; },
    };
  }
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  };
  const context = vm.createContext({
    API_BASE: '',
    Date,
    URLSearchParams,
    document: {
      createElement: makeElement,
      getElementById: get,
      querySelector: () => makeElement(),
    },
    sessionStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    hasStoredAuth: () => true,
    authenticatedFetch: async (url, options = {}) => {
      requests.push({ url, options });
      return { ok: true, json: async () => ({ eligible: false, library_item_count: 0 }) };
    },
    refreshTodaysPick: () => { context.todayRefreshes = (context.todayRefreshes || 0) + 1; },
    refreshLibraryPulse: () => { context.pulseRefreshes = (context.pulseRefreshes || 0) + 1; },
  });
  vm.runInContext(returnDeckSource, context);
  context.scheduleLibraryLaunchpadRefresh = () => {
    context.scheduleCalls = (context.scheduleCalls || 0) + 1;
    context.refreshLibraryPulse();
    context.refreshTodaysPick();
  };
  return { context, get, requests, storage };
}

function activeContext(overrides = {}) {
  return {
    days_away: 4,
    engagement_token: 'signed-return-token-that-is-long-enough',
    created_at: Date.now(),
    shown: false,
    ...overrides,
  };
}

test('return context rejects malformed, future, expired, and tokenless state', () => {
  for (const candidate of [
    activeContext({ days_away: 'not-a-number' }),
    activeContext({ created_at: Date.now() + 120000 }),
    activeContext({ created_at: Date.now() - 86400001 }),
    activeContext({ engagement_token: '' }),
  ]) {
    const { context, storage } = setup(candidate);
    assert.equal(context.getReturnPromptContext(), null);
    assert.equal(storage.has('omnitrackr_return_prompt'), false);
  }
});

test('return deck sends its signed token and records one shown event', async () => {
  const prompt = activeContext();
  const { context, get, requests } = setup(prompt);
  context.authenticatedFetch = async (url, options = {}) => {
    requests.push({ url, options });
    if (url.includes('/return-deck/?')) {
      return {
        ok: true,
        json: async () => ({
          eligible: true,
          days_away: 4,
          primary: { id: 1, title: 'Movie', category: 'movies', category_label: 'Movie', reason: 'Continue', status_label: 'Unfinished' },
          alternative: null,
          reflection: null,
          recap: {},
        }),
      };
    }
    return { ok: true };
  };

  assert.equal(await context.refreshReturnDeck(), true);
  assert.equal(get('returnDeck').hidden, false);
  const getRequest = requests.find(request => request.url.includes('/return-deck/?'));
  assert.match(getRequest.url, /days_away=4/);
  assert.doesNotMatch(getRequest.url, /engagement_token=/);
  assert.equal(getRequest.options.headers['X-Return-Prompt'], prompt.engagement_token);
  const shown = requests.find(request => request.url.endsWith('/return-deck/engagement'));
  assert.deepEqual(JSON.parse(shown.options.body), {
    action: 'shown',
    engagement_token: prompt.engagement_token,
  });
});

test('double dismissal records only one terminal event and restores dashboard cards once', () => {
  const prompt = activeContext({ shown: true });
  const { context, requests } = setup(prompt);
  context.renderReturnDeck({
    eligible: true,
    days_away: 4,
    primary: { id: 1, title: 'Book', category: 'books', category_label: 'Book', reason: 'Continue', status_label: 'Unread' },
    alternative: null,
    reflection: null,
    recap: {},
  }, prompt);

  context.dismissReturnDeck();
  context.dismissReturnDeck();

  const terminal = requests.filter(request => request.url.endsWith('/return-deck/engagement'));
  assert.equal(terminal.length, 1);
  assert.equal(JSON.parse(terminal[0].options.body).action, 'dismissed');
  assert.equal(context.todayRefreshes, 1);
  assert.equal(context.pulseRefreshes, 1);
  assert.equal(context.scheduleCalls, 1);
});

test('eligible startup suppresses fallback cards while the deck is pending and active', async () => {
  const prompt = activeContext();
  const { context } = setup(prompt);
  let resolveDeck;
  context.authenticatedFetch = url => {
    if (url.includes('/return-deck/?')) {
      return new Promise(resolve => { resolveDeck = resolve; });
    }
    return Promise.resolve({ ok: true });
  };
  context.scheduleLibraryLaunchpadRefresh = () => {
    context.scheduledDecisionRefresh = context.refreshDashboardDecisionCards();
  };

  const bootstrap = context.bootstrapReturnDeck();
  assert.equal(await context.refreshDashboardDecisionCards(), false);
  assert.equal(context.todayRefreshes || 0, 0);
  assert.equal(context.pulseRefreshes || 0, 0);

  resolveDeck({
    ok: true,
    json: async () => ({
      eligible: true,
      days_away: 4,
      primary: { id: 1, title: 'Movie', category: 'movies', category_label: 'Movie', reason: 'Continue', status_label: 'Unfinished' },
      alternative: null,
      reflection: null,
      recap: {},
    }),
  });
  await bootstrap;
  assert.equal(await context.scheduledDecisionRefresh, false);
  assert.equal(context.todayRefreshes || 0, 0);
  assert.equal(context.pulseRefreshes || 0, 0);
});

test('ineligible startup requests each fallback card exactly once', async () => {
  const { context } = setup(activeContext());
  context.scheduleLibraryLaunchpadRefresh = () => {
    context.scheduledDecisionRefresh = context.refreshDashboardDecisionCards();
  };

  assert.equal(await context.bootstrapReturnDeck(), false);
  assert.equal(await context.scheduledDecisionRefresh, true);
  assert.equal(context.todayRefreshes, 1);
  assert.equal(context.pulseRefreshes, 1);
});
