// A shared "On your services" list (services-share.js): matching a visitor's services and the line it shows.
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const share = require(path.join(__dirname, '..', 'app', 'static', 'services-share.js'));

test('overlap keeps the title\'s order and only the visitor\'s services', () => {
  assert.deepStrictEqual(share.overlap(['netflix', 'hulu', 'max'], ['max', 'netflix']), ['netflix', 'max']);
  assert.deepStrictEqual(share.overlap(['netflix'], []), []);
});

test('the result line says how many they can watch', () => {
  assert.strictEqual(share.resultText(0, 5, 0), '');
  assert.match(share.resultText(0, 5, 2), /None of these 5/);
  assert.strictEqual(share.resultText(5, 5, 1), 'You can watch all 5 of these on your services.');
  assert.strictEqual(share.resultText(2, 5, 3), 'You can watch 2 of these 5 on your services.');
});

test('stored picks are read back only when they look like service ids', () => {
  const store = {};
  global.localStorage = { getItem: key => store[key] ?? null, setItem: (key, value) => { store[key] = value; } };
  share.storeMine(['netflix', 'hulu']);
  assert.deepStrictEqual(share.readMine(), ['netflix', 'hulu']);
  store[share.KEY] = JSON.stringify(['netflix', '<img>', 7, 'max']);
  assert.deepStrictEqual(share.readMine(), ['netflix', 'max']);
  store[share.KEY] = 'not json';
  assert.strictEqual(share.readMine(), null);
  delete global.localStorage;
});

test('names join the way the page writes them', () => {
  assert.strictEqual(share.and(['Netflix']), 'Netflix');
  assert.strictEqual(share.and(['Netflix', 'Hulu', 'Max']), 'Netflix, Hulu and Max');
});
