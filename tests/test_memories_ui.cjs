// On this day card: plain wording, safe images, actions only for titles still in the library, a per-member hide key.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const card = require(path.join(__dirname, '../app/static/memories.js'));

test('the extra-that-day line reads as words', () => {
  assert.equal(card.moreText(0), '');
  assert.equal(card.moreText(1), 'And one more thing that day.');
  assert.equal(card.moreText(4), 'And 4 more things that day.');
});

test('covers fall back to initials and only load http(s) images', () => {
  assert.equal(card.initials('The Wire'), 'TW');
  assert.equal(card.initials(''), '★');
  assert.equal(card.safeImage('https://img.example/a.jpg'), 'https://img.example/a.jpg');
  assert.equal(card.safeImage('javascript:alert(1)'), null);
  assert.equal(card.safeImage('https://img.example/a.jpg" onerror="x'), null);
});

test('open and Next Up need a real library title', () => {
  assert.equal(card.libraryTitle({ category: 'books', item_id: 4 }), true);
  assert.equal(card.libraryTitle({ category: 'books', item_id: null }), false);
  assert.equal(card.libraryTitle({ category: 'collections', item_id: 4 }), false);
  assert.equal(card.usable({ line: 'You read Dune.', label: 'A year ago today' }), true);
  assert.equal(card.usable({ line: 3, label: 'x' }), false);
});

test('hiding is per member', () => {
  global.getUser = () => ({ id: 9 });
  try {
    assert.equal(card.hiddenKey(), 'omnitrackr_memories_hidden_9');
  } finally {
    delete global.getUser;
  }
});
