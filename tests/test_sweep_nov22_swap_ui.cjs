// Pick swap sweep: the wrapped boxes before unwrap day name nobody but you, and the draw day never defaults to today.
const { test } = require('node:test');
const assert = require('node:assert/strict');

const page = require('../app/static/pick-swap.js');

test('boxes come from the totals, with only your own labelled', () => {
  const swap = {
    givers: 5, wrapped: 3,
    people: [
      { username: 'dana', you: false, in_draw: true, wrapped: null },
      { username: 'sam', you: true, in_draw: true, wrapped: true },
      { username: 'lee', you: false, in_draw: true, wrapped: null },
      { username: 'kim', you: false, in_draw: true, wrapped: null },
      { username: 'jo', you: false, in_draw: true, wrapped: null },
    ],
  };
  const boxes = page.boxStates(swap);
  assert.equal(boxes.length, 5);
  assert.deepEqual(boxes[0], { label: 'You', wrapped: true });
  assert.equal(boxes.filter(box => box.wrapped).length, 3);
  assert.ok(boxes.every(box => !['dana', 'lee', 'kim', 'jo'].includes(box.label)));
});

test('someone who joined after the draw sees the boxes without one of their own', () => {
  const boxes = page.boxStates({ givers: 2, wrapped: 1, people: [{ you: true, in_draw: false, wrapped: null }] });
  assert.deepEqual(boxes.map(box => box.wrapped), [true, false]);
  assert.ok(boxes.every(box => box.label !== 'You'));
  assert.deepEqual(page.boxStates({ givers: 0, wrapped: 0, people: [] }), []);
});

test('the draw day starts a week out, or tomorrow when unwrap day is close', () => {
  assert.equal(page.firstDrawDay('2026-11-22', '2026-12-25'), '2026-11-29');
  assert.equal(page.firstDrawDay('2026-12-20', '2026-12-25'), '2026-12-21');
  assert.equal(page.firstDrawDay('2026-12-31', '2027-01-03'), '2027-01-01');
});
