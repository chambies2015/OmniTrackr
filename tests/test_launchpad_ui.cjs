const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = require('./helpers/dashboard_source.cjs');

function setup(dismissed = false) {
  const elements = new Map();
  function makeElement() {
    return {
      hidden: true, children: [], dataset: {}, textContent: '',
      replaceChildren() { this.children = []; },
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); },
      removeAttribute(name) { if (name === 'hidden') this.hidden = false; },
      scrollIntoView() { this.scrolled = true; },
      focus() { this.focused = true; },
    };
  }
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  };
  let opens = 0;
  const context = vm.createContext({
    demoStartGuidance: false,
    document: { getElementById: get, createElement: makeElement },
    isLibraryLaunchpadDismissed: () => dismissed,
    window: { openAccountModal: () => { opens++; } },
  });
  vm.runInContext(source.slice(source.indexOf('function openLaunchpadImport('), source.indexOf('function renderLibraryPulseList(')), context);
  return { context, get, opens: () => opens };
}

test('empty library exposes six existing add paths and discovery/import, not empty insights', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, false);
  assert.equal(get('libraryLaunchpadStarterPaths').hidden, false);
  assert.equal(get('libraryLaunchpadInsights').hidden, true);
  assert.deepEqual(Array.from(get('libraryLaunchpadCategories').children, b => b.dataset.launchpadCategory),
    ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']);
});

test('first save transitions to useful guidance and hides starter paths', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 0 });
  context.renderLibraryLaunchpad({ total_items: 1 });
  assert.match(get('libraryLaunchpadSummary').textContent, /first title is saved/);
  assert.equal(get('libraryLaunchpadStarterPaths').hidden, true);
  assert.equal(get('libraryLaunchpadCategories').hidden, true);
  assert.equal(get('libraryLaunchpadInsights').hidden, false);
});

test('completed introductory steps retire the panel without persisting a dismissal', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 1 });
  context.renderLibraryLaunchpad({ total_items: 3, rated_items: 1, reviewed_items: 1 });
  assert.equal(get('libraryLaunchpad').hidden, true);
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, false);
});

test('dismissed guidance stays hidden on refresh', () => {
  const { context, get } = setup(true);
  get('libraryLaunchpad').hidden = false;
  context.renderLibraryLaunchpad({ total_items: 0 });
  assert.equal(get('libraryLaunchpad').hidden, true);
});

test('import shortcut opens the existing account importer and focuses its source selector', () => {
  const { context, get, opens } = setup();
  context.openLaunchpadImport();
  assert.equal(opens(), 1);
  assert.equal(get('importStudio').scrolled, true);
  assert.equal(get('importStudioSource').focused, true);
});

const NEW_MEMBER = {
  show: true, friend: false, public_review: false, weekly_email: false, email_available: true, verified: true,
  review_target: { title: 'Heat', path: '/titles/movie/heat-1995' },
};
const stepLabels = get => get('libraryLaunchpadSteps').children.map(step => step.children[1].textContent);
const stepAction = (get, index) => get('libraryLaunchpadSteps').children[index].children[2];

test('new members get social steps with their own actions once a title is saved', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 0 }, NEW_MEMBER);
  assert.equal(get('libraryLaunchpadSteps').children.length, 3);  // nothing social before the first title
  context.renderLibraryLaunchpad({ total_items: 2 }, NEW_MEMBER);
  assert.deepEqual(stepLabels(get).slice(3), [
    'Add a friend to see what they track', 'Share a public review of Heat',
    'Get a weekly email when something you track comes out',
  ]);
  assert.equal(stepAction(get, 3).dataset.action, 'launchpad-add-friend');
  assert.equal(stepAction(get, 4).href, '/titles/movie/heat-1995#write-review');
  assert.equal(stepAction(get, 5).dataset.action, 'launchpad-weekly-email');
});

test('library steps done keeps the panel open until the social steps are done too', () => {
  const { context, get } = setup();
  const library = { total_items: 3, rated_items: 1, reviewed_items: 1 };
  context.renderLibraryLaunchpad(library, NEW_MEMBER);
  assert.equal(get('libraryLaunchpad').hidden, false);
  assert.match(get('libraryLaunchpadSummary').textContent, /add a friend, share a review/);
  context.renderLibraryLaunchpad(library, { ...NEW_MEMBER, friend: true, public_review: true, weekly_email: true });
  assert.equal(get('libraryLaunchpad').hidden, true);
  context.renderLibraryLaunchpad(library, { show: false });  // longtime members see no change
  assert.equal(get('libraryLaunchpad').hidden, true);
});

test('finished steps and unsafe or missing targets show no action', () => {
  const { context, get } = setup();
  context.renderLibraryLaunchpad({ total_items: 1 }, {
    ...NEW_MEMBER, friend: true, verified: false, email_available: true,
    review_target: { title: 'X', path: 'javascript:alert(1)' },
  });
  assert.equal(stepLabels(get)[3], 'Friend added');
  assert.equal(stepAction(get, 3), undefined);
  assert.equal(stepAction(get, 4), undefined);
  assert.equal(stepLabels(get)[5], 'Verify your email to get the weekly release email');
  assert.equal(stepAction(get, 5), undefined);
  context.renderLibraryLaunchpad({ total_items: 1 }, { ...NEW_MEMBER, email_available: false, review_target: null });
  assert.equal(stepLabels(get).length, 5);
  assert.equal(stepLabels(get)[4], 'Share a public review from any title page');
});
