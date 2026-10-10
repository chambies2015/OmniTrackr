const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');

const snippet = source.slice(source.indexOf('function openInviteFromHash('), source.indexOf('window.closeFriendRequestModal = function'));

function run(hash, signedIn = true) {
  const calls = { opened: 0, replaced: [], timers: 0 };
  const window = {
    location: { hash, pathname: '/', search: '' },
    history: { state: null, replaceState: (_s, _t, url) => calls.replaced.push(url) },
    openFriendRequestModal: () => { calls.opened++; },
    setTimeout: () => { calls.timers++; },
  };
  vm.runInContext(snippet, vm.createContext({
    window, getUser: () => (signedIn ? { id: 1 } : null),
    document: { getElementById: id => (id === 'friendRequestModal' ? {} : null) },
  }));
  return calls;
}

test('the weekly email link opens the friend form with the invite option and clears the hash', () => {
  const calls = run('#invite-friends');
  assert.equal(calls.opened, 1);
  assert.deepEqual(calls.replaced, ['/']);
});

test('other pages and signed-out visitors are left alone (signed-out retries briefly)', () => {
  assert.equal(run('#supporter').opened, 0);
  const signedOut = run('#invite-friends', false);
  assert.equal(signedOut.opened, 0);
  assert.equal(signedOut.timers, 1);
});
