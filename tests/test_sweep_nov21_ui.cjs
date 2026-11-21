// Nov 21 sweep of #273-#275: the April challenge card's "who recommended it" buttons.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const challenge = require(path.join(__dirname, '../app/static/challenges.js'));

function fakeDom({ creditButton = null } = {}) {
  const title = {
    attributes: {}, focused: false, isConnected: true,
    hasAttribute(name) { return name in this.attributes; },
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { this.focused = true; global.document.activeElement = this; },
  };
  const status = { textContent: '' };
  const body = { isConnected: true };
  global.document = {
    body,
    activeElement: body,
    getElementById: id => ({ monthlyChallengeTitle: title, monthlyChallengeStatus: status }[id] || null),
    querySelector: selector => (selector.includes('credit') ? creditButton : null),
  };
  return { title, status, body };
}

test('after saving the last credit, focus moves to the card heading and the step is announced', () => {
  const { title, status } = fakeDom();
  try {
    challenge.state.data = { steps: [{ kind: 'edition', done: true }, { kind: 'recommended', done: true }] };
    challenge.afterCredit();
    assert.equal(title.focused, true);
    assert.equal(title.attributes.tabindex, '-1');
    assert.equal(status.textContent, 'Saved. That counts for this step.');
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('with titles still to credit, focus moves to the next one', () => {
  const next = { focused: false, focus() { this.focused = true; } };
  const { title, status } = fakeDom({ creditButton: next });
  try {
    challenge.state.data = { steps: [{ kind: 'recommended', done: false }] };
    challenge.afterCredit();
    assert.equal(next.focused, true);
    assert.equal(title.focused, false);
    assert.equal(status.textContent, 'Saved.');
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('focus the member moved elsewhere stays where it is', () => {
  const next = { focused: false, focus() { this.focused = true; } };
  fakeDom({ creditButton: next });
  try {
    global.document.activeElement = { isConnected: true };
    challenge.state.data = { steps: [{ kind: 'recommended', done: false }] };
    challenge.afterCredit();
    assert.equal(next.focused, false);
  } finally {
    delete global.document;
    challenge.state.data = null;
  }
});

test('the card only moves focus for a save it started', () => {
  const source = fs.readFileSync(path.join(__dirname, '../app/static/challenges.js'), 'utf8');
  assert.match(source, /state\.crediting = opened \?/);
  assert.match(source, /refreshMonthlyChallenge\(\{ credited: fromCard \}\)/);
  assert.match(source, /if \(credited\) afterCredit\(\);/);
});

test('credit titles are separate chips that outrank the home board quiet-link style', () => {
  const css = fs.readFileSync(path.join(__dirname, '../app/static/styles.css'), 'utf8');
  const rule = css.match(/#monthlyChallenge \.month-challenge__credits \.month-challenge__link \{([^}]*)\}/);
  assert.ok(rule, 'chip rule present');
  assert.match(rule[1], /border: 1px solid/);
  assert.match(rule[1], /padding: 6px 12px/);
  assert.match(css, /\.month-challenge__credits \{[^}]*gap: 6px/);
});
