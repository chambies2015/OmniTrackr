// Notification dropdown: shared-list notes open the list they are about.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');

const source = require('./helpers/dashboard_source.cjs');

function slice(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0 && end > start, `${startMarker} is present`);
  return source.slice(start, end);
}

const loadSource = slice('async function loadNotifications() {', 'async function updateNotificationCount() {');
const escapeSource = slice('function escapeHtml(str) {', 'function normalizeLibrarySearchText(');

async function render(notifications) {
  const list = { innerHTML: '' };
  const context = vm.createContext({
    API_BASE: '', console, Date,
    document: { getElementById: id => (id === 'notificationList' ? list : null), createElement: () => ({ set textContent(v) { this.innerHTML = String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); } }) },
    authenticatedFetch: async () => ({ ok: true, json: async () => notifications }),
    getTimeAgo: () => 'just now',
  });
  vm.runInContext(`${escapeSource}\n${loadSource}\nthis.loadNotifications = loadNotifications;`, context);
  await context.loadNotifications();
  return list.innerHTML;
}

const note = (type, link) => ({ id: 1, type, link, message: 'alice added you to the shared list "Couch queue".',
  created_at: '2026-10-21T12:00:00Z', read_at: null });

test('shared-list notifications link to the list', async () => {
  for (const type of ['shared_list_added', 'shared_list_joined', 'shared_list_item']) {
    const html = await render([note(type, '/lists/12')]);
    assert.match(html, /<a class="notification-action-btn" href="\/lists\/12">Open the list<\/a>/, type);
  }
});

test('shared-list notifications with an unexpected link get no button', async () => {
  for (const link of [null, '/lists/0', '//evil.example/lists/1', '/lists/1?x=1', 'javascript:alert(1)']) {
    const html = await render([note('shared_list_added', link)]);
    assert.doesNotMatch(html, /Open the list/, String(link));
  }
});
