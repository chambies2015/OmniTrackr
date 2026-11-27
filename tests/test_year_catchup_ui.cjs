// The year's big ones on "Fill in your year" (app/static/year-catchup.js): the helpers that pick the month
// buttons, the line under an answered poster and what a pressed button means.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { monthsFrom, saidText, parseChoice } = require(path.join(__dirname, '..', 'app', 'static', 'year-catchup.js'));

test('month buttons run from the month it came out to the last month that can be picked', () => {
  assert.deepEqual(monthsFrom(11, 12), [11, 12]);
  assert.deepEqual(monthsFrom('7', '9'), [7, 8, 9]);
  assert.deepEqual(monthsFrom(1, 1), [1]);
  assert.deepEqual(monthsFrom(12, 11), []);
  assert.deepEqual(monthsFrom(undefined, 2), [1, 2]);
  assert.deepEqual(monthsFrom(-4, 40), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
});

test('the line under an answered poster', () => {
  assert.equal(saidText('month', 'Watched', 8), 'Watched in August');
  assert.equal(saidText('month', 'Played', 13), 'Played');
  assert.equal(saidText('want', 'Read'), 'On your list');
  assert.equal(saidText('library_saved', 'Read'), 'On your list');
  assert.equal(saidText('library_done', 'Read'), 'In your library');
  assert.equal(saidText('no', 'Watched'), 'Not for me');
  assert.equal(saidText('open', 'Watched'), '');
});

test('only known buttons mean anything', () => {
  assert.deepEqual(parseChoice('month-7'), { answer: 'month', month: 7 });
  assert.deepEqual(parseChoice('month-12'), { answer: 'month', month: 12 });
  assert.deepEqual(parseChoice('want'), { answer: 'want', month: null });
  assert.deepEqual(parseChoice('no'), { answer: 'no', month: null });
  assert.deepEqual(parseChoice('undo'), { answer: 'undo', month: null });
  for (const value of ['month-0', 'month-13', 'month-x', 'month-', 'drop', '', null, undefined, 'month-123']) {
    assert.equal(parseChoice(value), null, String(value));
  }
});
