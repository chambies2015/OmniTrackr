// "On your services" on the home screen (streaming.js): summary copy, service names, the service filter.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function load() {
  global.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null }, querySelectorAll() { return []; } };
  global.window = { addEventListener() {}, location: { hash: '' } };
  const file = path.join(__dirname, '..', 'app', 'static', 'streaming.js');
  delete require.cache[require.resolve(file)];
  return require(file);
}

const chosen = names => names.map((name, index) => ({ id: `s${index}`, name, count: 1 }));

test('the summary counts titles, arrivals and titles still being checked', () => {
  const ui = load();
  assert.equal(ui.summaryFor({ chosen: chosen(['Netflix', 'Hulu']), total: 7, new: 2, pending: 0 }),
    '7 titles on your list are streaming on Netflix and Hulu. 2 arrived in the last two weeks.');
  assert.equal(ui.summaryFor({ chosen: chosen(['Netflix']), total: 1, new: 1, pending: 3 }),
    '1 title on your list is streaming on Netflix. One arrived in the last two weeks. Still checking 3 titles, so more may turn up within the hour.');
  assert.equal(ui.summaryFor({ chosen: chosen(['Max']), total: 0, new: 0, pending: 0, alerts: true }),
    'Nothing on your list is streaming on Max right now. We’ll tell you when something arrives.');
  assert.ok(!ui.summaryFor({ chosen: chosen(['Max']), total: 0, alerts: false }).includes('tell you'));
});

test('long service lists are shortened and kinds are named', () => {
  const ui = load();
  assert.equal(ui.serviceNames(chosen(['Netflix', 'Hulu', 'Max', 'Peacock', 'Tubi'])), 'Netflix, Hulu and 3 more');
  assert.equal(ui.serviceNames(chosen(['Netflix', 'Hulu', 'Max'])), 'Netflix, Hulu and Max');
  assert.equal(ui.kindWords(['movies', 'tv-shows', 'anime']), 'films, shows and anime');
  assert.equal(ui.kindWords([]), 'films and shows');
});

test('the service filter keeps titles on that service only', () => {
  const ui = load();
  const card = { items: [
    { title: 'Dune', services: [{ id: 'hbomax' }] },
    { title: 'Past Lives', services: [{ id: 'netflix' }, { id: 'hulu' }] },
  ] };
  ui.state.filter = '';
  assert.equal(ui.filtered(card).length, 2);
  ui.state.filter = 'hulu';
  assert.deepEqual(ui.filtered(card).map(item => item.title), ['Past Lives']);
  ui.state.filter = '';
});

test('home layout keeps the card out when something just arrived, and links find it', () => {
  global.document = { readyState: 'loading', addEventListener() {}, getElementById() { return null }, activeElement: null };
  global.window = { addEventListener() {}, location: { hash: '' }, localStorage: null };
  const file = path.join(__dirname, '..', 'app', 'static', 'home-layout.js');
  delete require.cache[require.resolve(file)];
  const layout = require(file);
  const unit = status => ({ id: 'onYourServices', dataset: { status }, classList: { contains: () => false }, contains: () => false, querySelector: () => null });
  assert.equal(layout.engaged(unit('new')), true);
  assert.equal(layout.engaged(unit('list')), false);
  assert.equal(layout.quiet(unit('choose')), false);
  const source = require('node:fs').readFileSync(file, 'utf8');
  assert.ok(source.includes("'#on-your-services': 'onYourServices'"));
});
