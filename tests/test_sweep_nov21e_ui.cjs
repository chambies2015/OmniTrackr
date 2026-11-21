// Nov 21 midday sweep of #285, #288, #289 and #290: the September card's "Keep writing" button.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const challenge = require(path.join(__dirname, '../app/static/challenges.js'));

function fakeDom({ writeButton = null } = {}) {
  const title = {
    attributes: {}, focused: false, isConnected: true,
    hasAttribute(name) { return name in this.attributes; },
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { this.focused = true; global.document.activeElement = this; },
  };
  const status = { textContent: '' };
  const body = { isConnected: true };
  const asked = [];
  global.document = {
    body,
    activeElement: body,
    getElementById: id => ({ monthlyChallengeTitle: title, monthlyChallengeStatus: status }[id] || null),
    querySelector: selector => { asked.push(selector); return selector.includes('"write"') ? writeButton : null; },
  };
  return { title, status, body, asked };
}

const report = (done, words) => ({
  kind: 'report', done, words: 50, best: done ? null : { title: 'The Odyssey', category: 'books', id: 4, words },
});

test('after the finish screen closes on a save, focus goes back to Keep writing', () => {
  const next = { focused: false, focus() { this.focused = true; } };
  const { title, status, asked } = fakeDom({ writeButton: next });
  try {
    challenge.state.data = { steps: [{ kind: 'edition', done: true }, report(false, 30)] };
    challenge.afterWrite();
    assert.equal(next.focused, true);
    assert.equal(title.focused, false);
    assert.equal(status.textContent, 'Saved. The Odyssey: 30 words so far, 20 to go.');
    assert.deepEqual(asked, ['#monthlyChallenge [data-challenge-action="write"]']);
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('once the report is in, focus moves to the card heading', () => {
  const { title, status } = fakeDom();
  try {
    challenge.state.data = { steps: [report(true)] };
    challenge.afterWrite();
    assert.equal(title.focused, true);
    assert.equal(title.attributes.tabindex, '-1');
    assert.equal(status.textContent, 'Saved. That counts as your report.');
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('focus still inside the open finish screen (a review result) stays there', () => {
  const next = { focused: false, focus() { this.focused = true; } };
  fakeDom({ writeButton: next });
  try {
    global.document.activeElement = { isConnected: true };
    challenge.state.data = { steps: [report(false, 30)] };
    challenge.afterWrite();
    assert.equal(next.focused, false);
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('the card only reports and moves focus for a write it started', () => {
  const source = fs.readFileSync(path.join(__dirname, '../app/static/challenges.js'), 'utf8');
  assert.match(source, /refreshMonthlyChallenge\(\{ wrote: fromCard \}\)/);
  assert.match(source, /if \(wrote\) afterWrite\(\);/);
});
