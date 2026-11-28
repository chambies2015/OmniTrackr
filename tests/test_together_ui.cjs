// Watch together scripts: the plan form's sums, the track cells, and the home card's bar.
const { test } = require('node:test');
const assert = require('node:assert/strict');

const page = require('../app/static/together.js');
const home = require('../app/static/together-home.js');

test('weeks round up and the summary names the last day', () => {
  assert.equal(page.weeksFor(10, 2), 5);
  assert.equal(page.weeksFor(11, 3), 4);
  assert.equal(page.weeksFor(0, 3), 0);
  assert.equal(page.weeksFor(10, 0), 0);
  const line = page.planSummary(10, 2, 'episode', '2026-11-23');
  assert.match(line, /^10 episodes, 2 a week: 5 weeks, ending /);
  assert.equal(page.planSummary(1, 1, 'chapter', ''), '1 chapter, 1 a week: 1 week.');
});

test('next Monday is always ahead of today', () => {
  assert.equal(page.isoDay(page.nextMonday(new Date(2026, 10, 22))), '2026-11-23'); // a Sunday
  assert.equal(page.isoDay(page.nextMonday(new Date(2026, 10, 23))), '2026-11-30'); // a Monday
  assert.equal(page.isoDay(page.nextMonday(new Date(2026, 10, 27))), '2026-11-30');
});

test('season choices come from the episode guide and skip empty seasons', () => {
  const choices = page.seasonChoices({ seasons: [{ number: 1, episodes: 9 }, { number: 2, episodes: 10 }, { number: 3, episodes: 0 }] });
  assert.deepEqual(choices.map(choice => choice.value), [1, 2]);
  assert.equal(choices[1].label, 'Season 2 (10 episodes)');
  assert.deepEqual(page.seasonChoices(null), []);
});

test('a library place maps into the chosen season like the server does', () => {
  assert.equal(page.placeFor({ unit: 'episode', season: 2, position: 4 }, 2, 10, 'episode'), 4);
  assert.equal(page.placeFor({ unit: 'episode', season: 3, position: 1 }, 2, 10, 'episode'), 10);
  assert.equal(page.placeFor({ unit: 'episode', season: 1, position: 8 }, 2, 10, 'episode'), 0);
  assert.equal(page.placeFor({ unit: 'chapter', position: 40 }, null, 18, 'chapter'), 18);
  assert.equal(page.placeFor({ unit: 'page', position: 40 }, null, 18, 'chapter'), 0);
  assert.equal(page.placeFor(null, 2, 10, 'episode'), 0);
});

test('track cells show who is where and which notes are open or waiting', () => {
  const weeks = page.trackWeeks({
    weeks: [{ number: 1, first: 1, last: 2, state: 'past', label: 'Week 1' }, { number: 2, first: 3, last: 4, state: 'now', label: 'Week 2' }],
    notes: [{ part: 0 }, { part: 2 }],
    locked: [{ part: 4 }, { part: 2 }],
    people: [{ username: 'sam', position: 4 }, { username: 'dana', position: 3 }],
    you: { position: 3 },
  });
  const cells = weeks.flatMap(week => week.cells);
  assert.deepEqual(cells.map(cell => cell.pin), [null, 'open', null, 'locked']);
  assert.deepEqual(cells.map(cell => cell.done), [true, true, true, false]);
  assert.deepEqual(cells[3].people.map(person => person.username), ['sam']);
});

test('share links carry the invite text and url', () => {
  const links = page.shareLinks('https://omnitrackr.xyz/together/join/abc', 'Watch Severance with me');
  assert.equal(links.length, 3);
  assert.ok(links[0][1].startsWith('https://wa.me/?text=Watch%20Severance%20with%20me%20https'));
});

test('the home bar tints this week and places everyone on it', () => {
  const parts = home.trackParts({
    total: 10, started: true, week_first: 3, week_last: 4,
    people: [{ username: 'dana', initials: 'DA', position: 3, you: true }, { username: 'sam', initials: 'SA', position: 4 }],
  });
  assert.deepEqual(parts.week, { from: 20, to: 40 });
  assert.equal(parts.you, 30);
  assert.deepEqual(parts.people.map(person => person.at), [30, 40]);
  const level = home.trackParts({ total: 10, started: true, week_first: 1, week_last: 2,
    people: [{ position: 2 }, { position: 2, you: true }, { position: 1 }] });
  assert.deepEqual(level.people.map(person => person.stack), [0, 1, 0]);
  const waiting = home.trackParts({ total: 10, started: false, week_first: null, week_last: null, people: [] });
  assert.equal(waiting.week, null);
  const odd = home.trackParts({ total: 0, started: true, week_first: 1, week_last: 1, people: [{ position: 7, you: true }] });
  assert.equal(odd.you, 100);
});

test('the home card says what was saved and what opened', () => {
  assert.equal(home.savedLine('Watched episode 4', 0), 'Saved: watched episode 4.');
  assert.equal(home.savedLine('Finished chapter 9', 1), 'Saved: finished chapter 9. A note from a friend just opened.');
  assert.equal(home.savedLine('Watched episode 2', 3), 'Saved: watched episode 2. 3 notes from friends just opened.');
  assert.equal(home.unreadWords(1), '1 new note');
  assert.equal(home.unreadWords(4), '4 new notes');
});

test('home links only go to a plan page', () => {
  assert.equal(home.safePath('/together/12'), '/together/12');
  assert.equal(home.safePath('https://example.com/together/12'), '/together');
  assert.equal(home.safePath('/together/12/../../admin'), '/together');
  assert.equal(home.safePath(null), '/together');
});
