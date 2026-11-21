// Sweep of the Nov 13 merges (#205-#207): the parts that run in the browser.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../app/static/friends-feed.js'), 'utf8');

function setup(saved) {
  const listeners = {};
  const tab = name => ({
    dataset: { socialTab: name }, tabIndex: 0, attrs: {},
    setAttribute(key, value) { this.attrs[key] = value; },
    addEventListener(type, handler) { listeners[`${name}:${type}`] = handler; },
    focus() {},
  });
  const tabs = [tab('friends'), tab('following')];
  const root = { dataset: { socialView: 'friends' } };
  const panels = { friendsFeedPanel: { hidden: false }, followingFeed: { hidden: true }, friendsFeedFilters: { hidden: false } };
  const loads = [];
  const module = { exports: {} };
  const context = vm.createContext({
    module, URLSearchParams,
    window: { OmniFollowing: { load: () => loads.push('following') } },
    localStorage: { getItem: () => saved, setItem() {} },
    document: {
      getElementById: id => panels[id] || null,
      querySelector: selector => (selector === '.social[data-social-view]' ? root : null),
      querySelectorAll: selector => (selector === '[data-social-tab]' ? tabs : []),
    },
  });
  vm.runInContext(source, context);
  return { feed: module.exports, root, panels, loads, listeners };
}

test('opening the dashboard on a saved Following view does not fetch the Following feed', () => {
  const { feed, root, panels, loads } = setup('following');
  feed.initSwitch();
  // The view is still restored, so the tab opens where the member left it...
  assert.equal(root.dataset.socialView, 'following');
  assert.equal(panels.followingFeed.hidden, false);
  assert.equal(panels.friendsFeedPanel.hidden, true);
  // ...but the two requests wait until the friends feed tab is opened.
  assert.deepEqual(loads, []);
});

test('picking Following still loads it', () => {
  const { feed, loads, listeners } = setup('friends');
  feed.initSwitch();
  assert.deepEqual(loads, []);
  listeners['following:click']();
  assert.deepEqual(loads, ['following']);
});
