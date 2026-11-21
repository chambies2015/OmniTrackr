// Binge calculator planner: what is left, the two ways to plan, the wording and the calendar file.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = { readyState: 'complete', addEventListener() {}, querySelector: () => null, querySelectorAll: () => [] };
  delete require.cache[require.resolve('../app/static/binge-calculator.js')];
  return require(path.join(__dirname, '../app/static/binge-calculator.js'));
}

const iso = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

const NARUTO = { kind: 'anime', name: 'Naruto and Naruto Shippuden', skip: 3, parts: [
  { id: '0', name: 'Naruto', unit: 'episode', n: 220, min: 5060, altN: 130, altMin: 2990 },
  { id: '1', name: 'Naruto Shippuden', unit: 'episode', n: 500, min: 11500, altN: 295, altMin: 6785 },
  { id: '2', name: 'The Last', unit: 'film', n: 1, min: 112, altN: 1, altMin: 112, optional: true },
] };
const POTTER = { kind: 'book', name: 'Harry Potter', skip: 0, pagesPerHour: 40, parts: [
  { id: '0', name: 'One', unit: 'book', n: 1, min: 384, pages: 256, audio: 498 },
  { id: '1', name: 'Two', unit: 'book', n: 1, min: 426, pages: 284, audio: 543 },
] };

test('finish dates count the start day and skip the days off', () => {
  const api = load();
  // Sunday 1 November 2026: 25 days of viewing ends on the 25th.
  assert.equal(iso(api.finishDate('2026-11-01', 25, 7)), '2026-11-25');
  assert.equal(iso(api.finishDate('2026-11-01', 1, 7)), '2026-11-01');
  // Weekends only: Sunday, then the next Saturday and Sunday.
  assert.equal(iso(api.finishDate('2026-11-01', 3, 2)), '2026-11-08');
  // Weekdays only starts on Monday the 2nd.
  assert.equal(iso(api.finishDate('2026-11-01', 5, 5)), '2026-11-06');
  assert.equal(api.finishDate('not-a-date', 5, 7), null);
  assert.equal(api.activeDaysBetween('2026-11-01', '2026-11-30', 7), 30);
  assert.equal(api.activeDaysBetween('2026-11-01', '2026-11-30', 5), 21);
  assert.equal(api.activeDaysBetween('2026-11-01', '2026-11-30', 2), 9);
  assert.equal(api.activeDaysBetween('2026-11-30', '2026-11-01', 7), 0);
});

test('planning by time and by date agree with each other', () => {
  const api = load();
  const byTime = api.planByTime(62 * 47, 2, 7, '2026-11-10');
  assert.equal(byTime.days, 25);
  assert.equal(iso(byTime.finish), '2026-12-04');
  const byDate = api.planByDate(62 * 47, '2026-11-10', '2026-12-04', 7);
  assert.equal(byDate.days, 25);
  assert.ok(byDate.perDay > 116 && byDate.perDay < 117);
  assert.deepEqual(api.planByDate(600, '2026-11-10', '', 7), { error: 'missing' });
  assert.equal(api.planByDate(600, '2026-11-10', '2026-11-09', 7).error, 'past');
  assert.equal(api.planByDate(600000, '2026-11-10', '2026-11-12', 7).error, 'too-much');
  // A Monday-to-Friday window has no weekend days in it.
  assert.equal(api.planByDate(600, '2026-11-09', '2026-11-13', 2).error, 'no-days');
  assert.equal(api.planByTime(0, 2, 7, '2026-11-10'), null);
  assert.equal(api.planByTime(600, 0, 7, '2026-11-10'), null);
});

test('what is left follows ticks, episodes seen, filler and intros', () => {
  const api = load();
  const all = api.remaining(NARUTO, {});
  assert.equal(all.minutes, 16560);
  assert.deepEqual(all.byUnit, { episode: 720, film: 0 });
  // The optional film only counts once it is ticked.
  const withFilm = api.remaining(NARUTO, { checked: new Set(['0', '1', '2']) });
  assert.equal(withFilm.minutes, 16672);
  assert.deepEqual(withFilm.byUnit, { episode: 720, film: 1 });
  const noFiller = api.remaining(NARUTO, { alt: true });
  assert.equal(noFiller.byUnit.episode, 425);
  assert.equal(noFiller.minutes, 9775);
  // Skipping openings takes three minutes off episodes and nothing off the film.
  assert.equal(api.remaining(NARUTO, { alt: true, skip: 3, checked: new Set(['0', '1', '2']) }).minutes, 9775 - 425 * 3 + 112);
  // 300 episodes seen clears the first show and 80 of the second.
  const seen = api.remaining(NARUTO, { seen: 300 });
  assert.equal(seen.byUnit.episode, 420);
  assert.equal(Math.round(seen.minutes), 420 * 23);
  assert.equal(seen.parts[0].share, 0);
  assert.equal(api.remaining(NARUTO, { seen: 5000 }).minutes, 0);
  assert.equal(api.remaining(NARUTO, { checked: new Set(['1']) }).minutes, 11500);
});

test('books switch between reading pace and audiobook speed', () => {
  const api = load();
  assert.equal(api.remaining(POTTER, { how: 'read', pagesPerHour: 40 }).minutes, 810);
  assert.equal(api.remaining(POTTER, { how: 'read', pagesPerHour: 60 }).minutes, 540);
  assert.equal(api.remaining(POTTER, { how: 'listen', speed: 1 }).minutes, 1041);
  assert.equal(api.remaining(POTTER, { how: 'listen', speed: 1.5 }).minutes, 694);
  assert.equal(api.remaining(POTTER, { how: 'read', pagesPerHour: 40, checked: new Set(['1']) }).pages, 284);
});

test('the sentences under the number say what was asked', () => {
  const api = load();
  const left = api.remaining(NARUTO, { checked: new Set(['0', '1', '2']), alt: true });
  const time = api.describe(NARUTO, left, { mode: 'time', hours: 2, week: 7, start: '2026-11-10' }, { alt: true }, '2026-11-10');
  assert.match(time.finish, /^At 2 hours a day, that is 83 days\. Start today and you would finish on Sunday, January 31, 2027\.$/);
  assert.equal(time.detail, '425 episodes and 1 film. About 5.1 episodes a day.');
  const later = api.describe(NARUTO, left, { mode: 'time', hours: 2, week: 7, start: '2026-12-01' }, { alt: true }, '2026-11-10');
  assert.match(later.finish, /Start then and you would finish on/);
  const weekends = api.describe(NARUTO, left, { mode: 'time', hours: 4, week: 2, start: '2026-11-10' }, { alt: true }, '2026-11-10');
  assert.match(weekends.finish, /^At 4 hours a day on 42 viewing days, you would finish on /);
  const date = api.describe(NARUTO, left, { mode: 'date', by: '2027-03-01', week: 7, start: '2026-11-10' }, { alt: true }, '2026-11-10');
  assert.match(date.finish, /^To finish by Monday, March 1, 2027, you need about 1 hour 28 minutes a day for 112 days\.$/);
  assert.equal(api.describe(NARUTO, left, { mode: 'date', by: '', week: 7, start: '2026-11-10' }, {}, '2026-11-10').finish,
    'Pick the date you want to be finished by.');
  const pages = api.describe(POTTER, api.remaining(POTTER, { how: 'read', pagesPerHour: 40 }),
    { mode: 'time', hours: 1, week: 7, start: '2026-11-10' }, { how: 'read', pagesPerHour: 40 }, '2026-11-10');
  assert.equal(pages.detail, '540 pages at 40 pages an hour. About 39 pages a day.');
  const nothing = api.describe(NARUTO, api.remaining(NARUTO, { checked: new Set() }), { mode: 'time', hours: 2, week: 7, start: '2026-11-10' }, {}, '2026-11-10');
  assert.equal(nothing.finish, 'Nothing left to plan. Tick a part to add it back.');
});

test('the hub turns typed numbers into a one-part plan', () => {
  const api = load();
  const show = api.customPlan({ kind: 'screen', name: '', episodes: 62, minutes: 47 });
  assert.equal(show.name, 'Your show');
  assert.equal(api.remaining(show, {}).minutes, 2914);
  const left = api.remaining(show, {});
  assert.equal(api.describe(show, left, { mode: 'time', hours: 2, week: 7, start: '2026-11-10' }, {}, '2026-11-10').detail,
    '62 episodes at 47 minutes each. About 2.5 episodes a day.');
  const films = api.customPlan({ kind: 'film', name: 'Trilogy', films: 3, filmMinutes: 120 });
  assert.equal(api.remaining(films, {}).minutes, 360);
  const book = api.customPlan({ kind: 'book', pages: 400, pace: 40 });
  assert.equal(api.remaining(book, { how: book.how, pagesPerHour: book.pagesPerHour }).minutes, 600);
  const audio = api.customPlan({ kind: 'audio', audioHours: 12 });
  assert.equal(api.remaining(audio, { how: audio.how, speed: 1.5 }).minutes, 480);
  const game = api.customPlan({ kind: 'game', gameHours: 30 });
  assert.equal(api.remaining(game, {}).minutes, 1800);
  const mine = api.customPlan({ kind: 'screen', override: { name: 'Severance', minutes: 780, detail: 'What you have left.' } });
  assert.equal(mine.name, 'Severance');
  assert.equal(api.remaining(mine, {}).minutes, 780);
});

test('the calendar file is an all-day event on the finish date', () => {
  const api = load();
  const file = api.calendarFile('Dune; Part One, again', api.parseIso('2026-12-31'), 'Line one\nline two', 'https://omnitrackr.xyz/binge-calculator/dune',
    new Date(Date.UTC(2026, 10, 10, 9, 30, 0)));
  const lines = file.split('\r\n');
  assert.equal(lines[0], 'BEGIN:VCALENDAR');
  assert.ok(lines.includes('DTSTART;VALUE=DATE:20261231'));
  assert.ok(lines.includes('DTEND;VALUE=DATE:20270101'));
  assert.ok(lines.includes('DTSTAMP:20261110T093000Z'));
  assert.ok(lines.includes('SUMMARY:Finish Dune\\; Part One\\, again'));
  assert.ok(lines.includes('DESCRIPTION:Line one\\nline two'));
  assert.equal(lines.at(-1), 'END:VCALENDAR');
});

test('members are told where their library puts them', () => {
  const api = load();
  const plan = { kind: 'tv', name: 'Breaking Bad' };
  const left = { minutes: 1645 };
  assert.equal(api.trackText(plan, { total: 1, done: 0, tracked: 0, missing: ['t0'] }, left).title, 'Not in your library yet');
  assert.equal(api.trackText(plan, { total: 1, done: 0, tracked: 1, watched: 27 }, left).title, 'You are 27 episodes in');
  assert.match(api.trackText(plan, { total: 1, done: 0, tracked: 1, watched: 27 }, left).text, /about 27 hours of watching left/);
  assert.equal(api.trackText(plan, { total: 1, done: 1, tracked: 1 }, left).title, 'You have finished Breaking Bad');
  const books = { kind: 'book', name: 'Harry Potter' };
  assert.equal(api.trackText(books, { total: 7, done: 2, tracked: 3 }, left).title, 'You have finished 2 of 7');
  assert.equal(api.trackText(books, { total: 7, done: 0, tracked: 3 }, left).title, '3 of 7 are in your library');
  assert.equal(api.addLabel(books, { total: 7, missing: ['3', '4', '5', '6'] }), 'Add the 4 you are missing to my library');
  assert.equal(api.addLabel(books, { total: 7, missing: ['0', '1', '2', '3', '4', '5', '6'] }), 'Add all 7 to my library');
  assert.equal(api.addLabel(plan, { total: 1, missing: ['t0'] }), 'Add it to my library');
  assert.equal(api.addLabel(plan, { total: 1, missing: [] }), '');
  assert.match(api.mineSummary({ count: 0 }), /^Nothing unfinished/);
  assert.equal(api.mineSummary({ count: 3, minutes: 6000, started: 1, started_minutes: 1620 }),
    'You have 3 unfinished titles in your library, about 100 hours in all. The one you have started needs about 27 hours to finish.');
});

test('small formatters', () => {
  const api = load();
  assert.equal(api.formatHours(9.04), '9');
  assert.equal(api.formatHours(9.26), '9.3');
  assert.equal(api.formatHours(1180.4), '1,180');
  assert.equal(api.clock(558), '9 h 18 min');
  assert.equal(api.clock(120), '2 h');
  assert.equal(api.clock(45), '45 min');
  assert.equal(api.spoken(77), '1 hour 17 minutes');
  assert.equal(api.spoken(60), '1 hour');
  assert.equal(api.spoken(0.2), '1 minute');
  assert.equal(api.plural(1, 'film'), '1 film');
  assert.equal(api.plural(1180, 'episode'), '1,180 episodes');
  assert.equal(api.plural(2.5, 'episode'), '2.5 episodes');
  assert.equal(api.todayIso(new Date(2026, 10, 10, 23, 30)), '2026-11-10');
});
