// Dashboard monthly challenge: plain-language progress and a per-month "not this month" key.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const challenge = require(path.join(__dirname, '../app/static/challenges.js'));

const steps = [{ done: true }, { done: false }, { done: false }];

test('days left reads as plain words', () => {
  assert.equal(challenge.daysLeftText(12), '12 days left');
  assert.equal(challenge.daysLeftText(1), 'Last day');
  assert.equal(challenge.daysLeftText(0), 'Ends today');
});

test('the summary invites, then tracks, then celebrates', () => {
  const base = { month_name: 'October', steps, done_steps: 0, days_left: 9, joined: false, completion: null };
  assert.equal(challenge.summaryText(base), '3 small steps for October. Progress fills in from what you mark finished this month.');
  assert.match(challenge.summaryText({ ...base, done_steps: 1 }), /already 1 of 3 steps in/);
  assert.equal(challenge.summaryText({ ...base, joined: true, done_steps: 1 }), '1 of 3 steps done · 9 days left');
  assert.equal(challenge.summaryText({ ...base, joined: true, completion: { celebrate: true } }), 'Challenge complete. 9 days left in October.');
});

test('dismissing hides only this month for this member', () => {
  global.getUser = () => ({ id: 7 });
  try {
    assert.equal(challenge.dismissKey('2026-10'), 'omnitrackr_challenge_hidden_7_2026-10');
    assert.notEqual(challenge.dismissKey('2026-10'), challenge.dismissKey('2026-11'));
  } finally {
    delete global.getUser;
  }
});

test('a revisit step that is not done offers to log one in the Journal', () => {
  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const open = challenge.stepItem({ kind: 'revisit', label: 'Go back to something you love', done: false, count: 0, target: 1 });
    const button = open.children.find(node => node.tag === 'button');
    assert.ok(button);
    assert.equal(button.textContent, 'Log a revisit');
    assert.equal(button.type, 'button');
    assert.equal(button.dataset.challengeAction, 'log-revisit');
    const done = challenge.stepItem({ kind: 'revisit', label: 'Go back to something you love', done: true, count: 1, target: 1 });
    assert.equal(done.children.some(node => node.tag === 'button'), false);
    const other = challenge.stepItem({ kind: 'reflect', label: 'Write down what you love about one', done: false, count: 0, target: 1 });
    assert.equal(other.children.some(node => node.tag === 'button'), false);
  } finally {
    delete global.document;
  }
});

test('a stretch step lists the formats that count for this member until it is done', () => {
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: ['manga', 'podcasts', 'audiobooks'] }),
    'Counts for you: manga, podcasts or audiobooks');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: ['audiobooks'] }), 'Counts for you: audiobooks');
  const all = ['movies', 'TV', 'anime', 'games', 'albums', 'books', 'manga', 'podcasts', 'audiobooks'];
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false, formats: all }), 'Any format counts for you');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: true, formats: ['manga'] }), '');
  assert.equal(challenge.stretchHint({ kind: 'stretch', done: false }), '');
  assert.equal(challenge.stretchHint({ kind: 'reflect', done: false, formats: ['manga'] }), '');
});

test('a recommended step offers this month\'s unsaid finishes until it is done', () => {
  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const unsaid = [
      { category: 'books', id: 4, title: 'A Lent Book' },
      { category: 'movies', id: 9, title: 'Film' },
      { category: 'manga', id: 0, title: 'No id' },
      { category: 'anime', id: 2, title: 'Show' },
      { category: 'music', id: 3, title: 'Fourth' },
    ];
    const item = challenge.stepItem({ kind: 'recommended', label: 'Finish something someone recommended to you', done: false, count: 0, target: 1, unsaid });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    const row = label.children.find(node => node.className === 'month-challenge__credits');
    assert.ok(row);
    assert.equal(row.children[0].textContent, 'Did someone recommend one of these?');
    const buttons = row.children.filter(node => node.tag === 'button');
    assert.deepEqual(buttons.map(button => button.textContent), ['A Lent Book', 'Film', 'Show']);
    assert.equal(buttons[0].dataset.challengeAction, 'credit');
    assert.equal(buttons[0].dataset.category, 'books');
    assert.equal(buttons[0].dataset.itemId, '4');
    assert.equal(buttons[0].attributes['aria-label'], 'Say who recommended A Lent Book');

    const one = challenge.creditRow({ unsaid: [{ category: 'books', id: 4, title: 'A Lent Book' }] });
    assert.equal(one.children[0].textContent, 'Did someone recommend it?');
    assert.equal(challenge.creditRow({ unsaid: [] }), null);

    const empty = challenge.stepItem({ kind: 'recommended', label: 'x', done: false, count: 0, target: 1, unsaid: [] });
    const hint = empty.children.find(node => node.className === 'month-challenge__label').children[0];
    assert.equal(hint.textContent, 'Name them under "Why I added it" on the title');

    const done = challenge.stepItem({ kind: 'recommended', label: 'x', done: true, count: 1, target: 1, unsaid });
    assert.equal(done.children.find(node => node.className === 'month-challenge__label').children.length, 0);
    const other = challenge.stepItem({ kind: 'reflect', label: 'x', done: false, count: 0, target: 1, unsaid });
    assert.equal(other.children.find(node => node.className === 'month-challenge__label').children.length, 0);
  } finally {
    delete global.document;
  }
});

test('a birthday step names titles in the library that turn a round number, or the years that count', () => {
  const turning = [
    { category: 'movies', id: 3, title: 'Star Wars', age: 50 },
    { category: 'video-games', id: 8, title: '  Portal ', age: 20 },
    { category: 'books', id: 1, title: '', age: 30 },
    { category: 'music', id: 2, title: 'No age' },
    { category: 'anime', id: 5, title: 'Den-noh Coil', age: 20 },
    { category: 'podcasts', id: 6, title: 'Fourth', age: 10 },
  ];
  assert.equal(challenge.birthdayHint({ kind: 'birthday', done: false, turning, years: [2017, 2007, 1997, 1987] }),
    'In your library: Star Wars turns 50, Portal turns 20, Den-noh Coil turns 20');
  assert.equal(challenge.birthdayHint({ kind: 'birthday', done: false, turning: [], years: [2017, 2007, 1997, 1987] }),
    'Counts if it came out in 2017, 2007, 1997, 1987 or an earlier year ending in 7');
  assert.equal(challenge.birthdayHint({ kind: 'birthday', done: false, years: [2018, 2008] }),
    'Counts if it came out in 2018, 2008 or an earlier year ending in 8');
  assert.equal(challenge.birthdayHint({ kind: 'birthday', done: false }), '');
  assert.equal(challenge.birthdayHint({ kind: 'birthday', done: true, turning, years: [2017] }), '');
  assert.equal(challenge.birthdayHint({ kind: 'reflect', done: false, turning, years: [2017] }), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const item = challenge.stepItem({ kind: 'birthday', label: 'Finish something that turns 10, 20, 30 or more this year',
      done: false, count: 0, target: 1, turning: [turning[0]], years: [2017] });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, 'In your library: Star Wars turns 50');
    assert.equal(item.children.some(node => node.tag === 'button'), false);
  } finally {
    delete global.document;
  }
});

test('a day step says when the next finish is due, in local time, or how the step counts', () => {
  const now = new Date(2027, 5, 12, 22, 0);
  const tomorrow = new Date(2027, 5, 13, 21, 40);
  const time = tomorrow.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const open = { titles: ['  Gone Home '], count: 1, until: tomorrow.toISOString() };
  const step = { kind: 'day', done: false, count: 1, target: 2, hours: 24, open };
  assert.equal(challenge.dayHint(step, now), `Finish one more by ${time} tomorrow to go with Gone Home`);

  const later = new Date(2027, 5, 12, 23, 30);
  assert.equal(challenge.dayHint({ ...step, open: { ...open, until: later.toISOString() } }, now),
    `Finish one more by ${later.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} today to go with Gone Home`);

  const three = { ...step, target: 3, open: { titles: ['A', 'B'], count: 2, until: tomorrow.toISOString() } };
  assert.equal(challenge.dayHint(three, now), `Finish one more by ${time} tomorrow to go with A and B`);

  // A window that has closed, a missing one or a broken date falls back to how the step counts.
  const fallback = 'Any two finishes less than 24 hours apart count';
  assert.equal(challenge.dayHint({ ...step, open: { ...open, until: new Date(2027, 5, 12, 21).toISOString() } }, now), fallback);
  assert.equal(challenge.dayHint({ ...step, open: null }, now), fallback);
  assert.equal(challenge.dayHint({ ...step, open: { titles: ['Gone Home'], until: 'soon' } }, now), fallback);
  assert.equal(challenge.dayHint({ ...step, open: { titles: [], until: tomorrow.toISOString() } }, now), fallback);
  assert.equal(challenge.dayHint({ ...step, done: true }, now), '');
  assert.equal(challenge.dayHint({ ...step, kind: 'birthday' }, now), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const item = challenge.stepItem({ kind: 'day', label: 'Finish two things within a day', done: false,
      count: 0, target: 2, hours: 24, open: null });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, fallback);
    assert.ok(item.children.some(node => node.className === 'month-challenge__count' && node.textContent === '0 of 2'));
  } finally {
    delete global.document;
  }
});

test('a pair step names other versions waiting in the library, or how the step counts', () => {
  const step = { kind: 'pair', done: false, count: 0, target: 1, waiting: [
    { title: ' Dune ', format: 'film', with: 'book' },
    { title: 'Akira', format: 'anime', with: 'manga' },
  ] };
  assert.equal(challenge.pairHint(step), 'In your library: Dune (film) to go with the book, Akira (anime) to go with the manga');
  // At most three, and entries without a title or format are skipped.
  const many = { ...step, waiting: [{ title: 'A', format: 'film' }, { title: '', format: 'book' }, { title: 'B', format: 7 },
    { title: 'C', format: 'game', with: 'book' }, { title: 'D', format: 'TV' }, { title: 'E', format: 'album' }] };
  assert.equal(challenge.pairHint(many), 'In your library: A (film), C (game) to go with the book, D (TV)');

  const fallback = "Counts when it shares a name with something you've finished in another format";
  assert.equal(challenge.pairHint({ ...step, waiting: [] }), fallback);
  assert.equal(challenge.pairHint({ ...step, waiting: 'Dune' }), fallback);
  assert.equal(challenge.pairHint({ ...step, done: true }), '');
  assert.equal(challenge.pairHint({ ...step, kind: 'day' }), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const item = challenge.stepItem({ kind: 'pair', label: 'Finish the other version of something', done: false,
      count: 0, target: 1, waiting: [] });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, fallback);
    assert.ok(!item.children.some(node => node.className === 'month-challenge__count'));
  } finally {
    delete global.document;
  }
});

test('a maker step names titles by people you know waiting in the library, or how the step counts', () => {
  const step = { kind: 'maker', done: false, count: 0, target: 1, waiting: [
    { title: ' The Conversation ', maker: 'Francis Ford Coppola' },
    { title: 'Tusk', maker: 'Fleetwood Mac' },
  ] };
  assert.equal(challenge.makerHint(step), 'In your library: The Conversation (Francis Ford Coppola), Tusk (Fleetwood Mac)');
  // At most three, entries without a title are skipped, and a missing maker leaves just the title.
  const many = { ...step, waiting: [{ title: 'A', maker: 'X' }, { title: '', maker: 'Y' }, { title: 'B', maker: 7 },
    { title: 'C', maker: 'Z' }, { title: 'D', maker: 'W' }] };
  assert.equal(challenge.makerHint(many), 'In your library: A (X), B, C (Z)');

  const fallback = "Counts when the director, author, band or host matches something you've finished";
  assert.equal(challenge.makerHint({ ...step, waiting: [] }), fallback);
  assert.equal(challenge.makerHint({ ...step, waiting: 'Tusk' }), fallback);
  assert.equal(challenge.makerHint({ ...step, done: true }), '');
  assert.equal(challenge.makerHint({ ...step, kind: 'pair' }), '');
  // The pair hint ignores a maker step, so each step gets only its own line.
  assert.equal(challenge.pairHint(step), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {},
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const item = challenge.stepItem({ kind: 'maker', label: 'Finish something else by a creator you already know',
      done: false, count: 0, target: 1, waiting: [{ title: 'Sula', maker: 'Toni Morrison' }] });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, 'In your library: Sula (Toni Morrison)');
  } finally {
    delete global.document;
  }
});

test('a report step counts the words so far, names the finish to write about, or says how it counts', () => {
  const step = { kind: 'report', done: false, count: 0, target: 1, words: 50,
    best: { title: ' Lord of the Flies ', category: 'books', id: 12, words: 32 } };
  assert.equal(challenge.reportHint(step), 'Lord of the Flies: 32 words so far, 18 to go');
  assert.equal(challenge.reportHint({ ...step, best: { ...step.best, words: 1 } }), 'Lord of the Flies: 1 word so far, 49 to go');
  assert.equal(challenge.reportHint({ ...step, best: { ...step.best, words: 0 } }),
    'Write 50 words about Lord of the Flies, or about anything else you finish this month');
  // A missing word target falls back to fifty, and a missing or broken finish to how the step counts.
  const fallback = 'Counts when what you write about one finish adds up to 50 words';
  assert.equal(challenge.reportHint({ ...step, words: undefined, best: null }), fallback);
  assert.equal(challenge.reportHint({ ...step, best: { title: '  ', words: 3 } }), fallback);
  assert.equal(challenge.reportHint({ ...step, best: 'Lord of the Flies' }), fallback);
  assert.equal(challenge.reportHint({ ...step, done: true }), '');
  assert.equal(challenge.reportHint({ ...step, kind: 'maker' }), '');
  // The other hints ignore a report step, so it gets only its own line.
  assert.equal(challenge.makerHint(step), '');
  assert.equal(challenge.pairHint(step), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {}, type: '',
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const button = challenge.writeButton(step);
    assert.equal(button.textContent, 'Keep writing');
    assert.equal(button.dataset.challengeAction, 'write');
    assert.equal(button.dataset.category, 'books');
    assert.equal(button.dataset.itemId, '12');
    assert.equal(button.attributes['aria-label'], 'Write about Lord of the Flies');
    assert.equal(challenge.writeButton({ ...step, best: { ...step.best, words: 0 } }).textContent, 'Write it');
    // A finish that was removed from the library has no id, so there is nothing to open.
    assert.equal(challenge.writeButton({ ...step, best: { ...step.best, id: null } }), null);
    assert.equal(challenge.writeButton({ ...step, best: { ...step.best, category: '' } }), null);
    assert.equal(challenge.writeButton({ ...step, done: true }), null);
    assert.equal(challenge.writeButton({ ...step, kind: 'reflect' }), null);

    const item = challenge.stepItem({ ...step, label: 'Hand in a fifty-word report' });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, 'Lord of the Flies: 32 words so far, 18 to go');
    assert.equal(label.children[1].dataset.challengeAction, 'write');
  } finally {
    delete global.document;
  }
});

test('a draw step names the kept card, offers to deal, or says what the draw needs', () => {
  const step = { kind: 'draw', done: false, count: 0, target: 1, card: { title: ' Dune ', category: 'movies', night: '2027-10-15' }, ready: false };
  assert.equal(challenge.drawHint(step), 'Your card: Dune, kept for Friday');
  assert.equal(challenge.drawHint({ ...step, card: { ...step.card, night: null } }), 'Your card: Dune. Finish it to take the deal');
  assert.equal(challenge.drawHint({ ...step, card: { ...step.card, night: '15 October' } }), 'Your card: Dune. Finish it to take the deal');
  assert.equal(challenge.drawHint({ ...step, card: null, ready: true }), 'Deal three cards from your backlog and keep one');
  const needs = "The draw deals from titles you've saved and not started, and needs three";
  assert.equal(challenge.drawHint({ ...step, card: null }), needs);
  assert.equal(challenge.drawHint({ ...step, card: { title: '   ' } }), needs);
  assert.equal(challenge.drawHint({ ...step, card: 'Dune', ready: 'yes' }), needs);
  assert.equal(challenge.drawHint({ ...step, done: true }), '');
  assert.equal(challenge.drawHint({ ...step, kind: 'report' }), '');
  // The other hints ignore a draw step, so it gets only its own line.
  assert.equal(challenge.reportHint(step), '');
  assert.equal(challenge.makerHint(step), '');
  // Dates are read as calendar days, so no time zone moves them.
  assert.equal(challenge.nightName('2027-10-31'), 'Sunday');
  assert.equal(challenge.nightName('2027-02-30'), '');
  assert.equal(challenge.nightName('tomorrow'), '');
  assert.equal(challenge.nightName(null), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {}, type: '',
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const button = challenge.drawButton(step);
    assert.equal(button.textContent, 'See my card');
    assert.equal(button.dataset.challengeAction, 'draw');
    assert.equal(challenge.drawButton({ ...step, card: null, ready: true }).textContent, 'Deal me in');
    // Nothing to deal yet, or nothing left to do: no button.
    assert.equal(challenge.drawButton({ ...step, card: null }), null);
    assert.equal(challenge.drawButton({ ...step, done: true }), null);
    assert.equal(challenge.drawButton({ ...step, kind: 'total' }), null);

    const item = challenge.stepItem({ ...step, label: 'Take the deal' });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[0].textContent, 'Your card: Dune, kept for Friday');
    assert.equal(label.children[1].dataset.challengeAction, 'draw');
  } finally {
    delete global.document;
  }
});

test('Deal me in opens the backlog draw, or says where to find it', async () => {
  const said = [];
  global.document = { getElementById: id => (id === 'monthlyChallengeStatus' ? { set textContent(value) { said.push(value); } } : null) };
  global.window = { OmniBacklogDraw: { show: async () => true } };
  try {
    assert.equal(await challenge.showDraw(), true);
    assert.deepEqual(said, []);
    window.OmniBacklogDraw.show = async () => false;
    assert.equal(await challenge.showDraw(), false);
    assert.equal(said.at(-1), 'Find the Draw from your backlog card on your home screen.');
    window.OmniBacklogDraw.show = async () => { throw new Error('offline'); };
    assert.equal(await challenge.showDraw(), false);
    delete window.OmniBacklogDraw;
    assert.equal(await challenge.showDraw(), false);
  } finally {
    delete global.window;
    delete global.document;
  }
});

test('a tell step offers the latest finish to recommend, or says how the step counts', () => {
  const step = { kind: 'tell', done: false, count: 0, target: 1, suggest: { title: ' The Princess Bride ', category: 'movies', id: 7 } };
  assert.equal(challenge.tellHint(step),
    "Loved The Princess Bride? Send it to a friend, or make a link for someone who isn't on OmniTrackr");
  const fallback = "Choose Recommend on anything in your library: a friend's inbox or a share link both count";
  assert.equal(challenge.tellHint({ ...step, suggest: null }), fallback);
  assert.equal(challenge.tellHint({ ...step, suggest: { ...step.suggest, title: '  ' } }), fallback);
  // A finish removed from the library has no id, so the dialog has nothing to send.
  assert.equal(challenge.tellHint({ ...step, suggest: { ...step.suggest, id: null } }), fallback);
  assert.equal(challenge.tellHint({ ...step, suggest: 'The Princess Bride' }), fallback);
  assert.equal(challenge.tellHint({ ...step, done: true }), '');
  assert.equal(challenge.tellHint({ ...step, kind: 'draw' }), '');
  // The other hints ignore a tell step, so it gets only its own line.
  assert.equal(challenge.drawHint(step), '');
  assert.equal(challenge.decadesHint(step), '');

  const make = tag => ({
    tag, className: '', textContent: '', dataset: {}, children: [], attributes: {}, type: '',
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  global.document = { createElement: make };
  try {
    const button = challenge.tellButton(step);
    assert.equal(button.textContent, 'Recommend it');
    assert.equal(button.dataset.challengeAction, 'tell');
    // friend-recs.js opens any button marked like this, with the title from the member's own library.
    assert.equal(button.dataset.friendRecOpen, '');
    assert.equal(button.dataset.recCategory, 'movies');
    assert.equal(button.dataset.recItemId, '7');
    assert.equal(button.dataset.recTitle, 'The Princess Bride');
    assert.equal(button.attributes['aria-label'], 'Recommend The Princess Bride to someone');
    assert.equal(challenge.tellButton({ ...step, suggest: null }), null);
    assert.equal(challenge.tellButton({ ...step, suggest: { ...step.suggest, category: '' } }), null);
    assert.equal(challenge.tellButton({ ...step, done: true }), null);
    assert.equal(challenge.tellButton({ ...step, kind: 'reflect' }), null);

    const item = challenge.stepItem({ ...step, label: 'Tell someone about one' });
    const label = item.children.find(node => node.className === 'month-challenge__label');
    assert.equal(label.children[0].className, 'month-challenge__hint');
    assert.equal(label.children[1].dataset.challengeAction, 'tell');
  } finally {
    delete global.document;
  }
});

test('Recommend it remembers the title, or says where to find Recommend', () => {
  const said = [];
  global.document = { getElementById: id => (id === 'monthlyChallengeStatus' ? { set textContent(value) { said.push(value); } } : null) };
  global.window = { OmniFriendRecs: { open() {} } };
  try {
    challenge.tellTitle({ dataset: { recCategory: 'movies', recItemId: '7' } });
    assert.deepEqual(challenge.state.telling, { category: 'movies', id: 7 });
    assert.deepEqual(said, []);
    delete window.OmniFriendRecs;
    challenge.tellTitle({ dataset: { recCategory: 'movies', recItemId: '7' } });
    assert.equal(challenge.state.telling, null);
    assert.equal(said.at(-1), 'Open the title in your library and choose Recommend.');
  } finally {
    delete global.window;
    delete global.document;
  }
});

test('a decades step lists the decades so far and titles from others, or how the step counts', () => {
  const step = { kind: 'decades', done: false, count: 2, target: 3, decades: [1980, 2010],
    waiting: [{ title: ' Alien ', category: 'movies', decade: 1970 }, { title: 'Halo', category: 'video-games', decade: 2000 }] };
  assert.equal(challenge.decadesHint(step), 'So far: the 1980s and the 2010s. In your library: Alien (1970s), Halo (2000s)');
  assert.equal(challenge.decadesHint({ ...step, waiting: [] }), 'So far: the 1980s and the 2010s');
  assert.equal(challenge.decadesHint({ ...step, decades: [1990] }), 'So far: the 1990s. In your library: Alien (1970s), Halo (2000s)');
  assert.equal(challenge.decadesHint({ ...step, decades: [] }), 'In your library: Alien (1970s), Halo (2000s)');
  const fallback = 'Counts by the year saved on each title: 1987 and 1989 are one decade, 1989 and 1990 are two';
  assert.equal(challenge.decadesHint({ ...step, decades: [], waiting: [] }), fallback);
  // Anything that isn't a whole decade is left out rather than printed.
  assert.equal(challenge.decadesHint({ ...step, decades: [1987, '1990', null], waiting: [{ title: 'X', decade: 1955 }, { title: '', decade: 1950 }] }), fallback);
  assert.equal(challenge.decadesHint({ ...step, done: true }), '');
  assert.equal(challenge.decadesHint({ ...step, kind: 'tell' }), '');
  assert.equal(challenge.tellHint(step), '');
});
