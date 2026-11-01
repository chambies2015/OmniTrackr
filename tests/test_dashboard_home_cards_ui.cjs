// Run with: node --test tests/test_dashboard_home_cards_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');
const settle = () => new Promise(resolve => setImmediate(resolve));

function setup({ readyState = 'complete' } = {}) {
  const timers = [];
  const readyListeners = [];
  const calls = [];
  const card = name => () => { calls.push(name); return Promise.resolve(name); };
  const window = {
    setTimeout: callback => { timers.push(callback); return timers.length; },
    clearTimeout() {},
    refreshYearGoals: card('goals'),
    refreshMonthlyChallenge: card('challenge'),
    refreshSeasonCard: card('season'),
    refreshBadges: card('badges'),
  };
  const document = {
    readyState,
    addEventListener: (type, callback) => { if (type === 'DOMContentLoaded') readyListeners.push(callback); },
  };
  const context = vm.createContext({
    window, document, Promise, Array, Set,
    launchpadRefreshTimer: null,
    launchpadDecisionRefreshRequested: false,
    decisionCardsRefreshPromise: null,
    refreshLibraryLaunchpad: () => Promise.resolve(),
    refreshNextUpQueue: () => Promise.resolve(),
    refreshDashboardDecisionCards() {},
  });
  vm.runInContext(source.slice(source.indexOf('const dashboardLayoutRefreshes ='), source.indexOf('const loadMovieLibrary =')), context);
  const run = () => timers.splice(0).forEach(callback => callback());
  const ready = () => { document.readyState = 'interactive'; readyListeners.splice(0).forEach(callback => callback()); };
  return { context, window, calls, run, ready, timers };
}

test('the first home refresh waits for the cards auth.js already asked for instead of asking again', async () => {
  const { context, window, calls, run } = setup();
  let finishBadges;
  const badges = new Promise(resolve => { finishBadges = resolve; });
  window.dashboardHomeCards = [Promise.resolve('goals'), badges];
  context.scheduleLibraryLaunchpadRefresh(false);
  run();
  assert.deepEqual(calls, [], 'no second request for cards already on their way');
  assert.equal(window.dashboardHomeCards, null);

  let ready = false;
  context.waitForDashboardLayoutRefreshes().then(() => { ready = true; });
  await settle();
  assert.equal(ready, false, 'the library stays hidden until the slowest card has drawn');
  finishBadges('badges');
  await settle(); await settle();
  assert.equal(ready, true);

  // Later refreshes (after adding or finishing a title) always fetch fresh cards.
  window.dashboardHomeCards = [Promise.resolve('stale')];
  context.scheduleLibraryLaunchpadRefresh(false);
  run();
  assert.deepEqual(calls, ['goals', 'challenge', 'season', 'badges']);
});

test('without cards from auth.js the first refresh asks for them itself', () => {
  const { context, calls, run } = setup();
  context.scheduleLibraryLaunchpadRefresh(false);
  run();
  assert.deepEqual(calls, ['goals', 'challenge', 'season', 'badges']);
});

test('a refresh asked for while the page is still parsing waits for auth.js to ask for the cards', () => {
  const { context, window, calls, run, ready, timers } = setup({ readyState: 'loading' });
  context.scheduleLibraryLaunchpadRefresh(false);
  context.scheduleLibraryLaunchpadRefresh(false);
  assert.equal(timers.length, 0, 'nothing runs before the page has parsed');
  // auth.js asks for the cards on DOMContentLoaded, before home.js's listener runs.
  window.dashboardHomeCards = [Promise.resolve('goals')];
  ready();
  run();
  assert.deepEqual(calls, [], 'the first batch reuses the cards instead of asking again');
});
