const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(ROOT, 'app/static/dashboard/lazy/statistics.js'), 'utf8');
const page = fs.readFileSync(path.join(ROOT, 'app/templates/index.html'), 'utf8');

function escapeHtml(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setup({ hiddenTabs = [] } = {}) {
  const elements = new Map();
  const makeElement = id => ({
    id, hidden: false, innerHTML: '', children: [], dataset: {}, style: { display: '', setProperty() {} },
    setAttribute() {}, appendChild(child) { this.children.push(child); elements.set(child.id, child); },
    querySelectorAll: () => [], addEventListener() {}, remove() { elements.delete(id); }, focus() {},
  });
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
  };
  const fetched = [];
  const context = vm.createContext({
    API_BASE: '', escapeHtml, console: { error() {} }, categoryStatsCache: {},
    document: { getElementById: get, createElement: () => makeElement(''), querySelectorAll: () => [] },
    getTabButton: category => ({ style: { display: hiddenTabs.includes(category) ? 'none' : '' } }),
    authenticatedFetch: async (url) => { fetched.push(url); return { ok: false }; },
  });
  vm.runInContext(source, context);
  return { context, get, fetched };
}

const movies = {
  watch_stats: { total_items: 4, watched_items: 3, unwatched_items: 1, completion_percentage: 75 },
  rating_stats: {
    total_rated_items: 3, average_rating: 8.33,
    rating_distribution: { 7: 1, 9: 2 },
    highest_rated: [{ title: '<img src=x onerror=alert(1)>', rating: 9 }],
    lowest_rated: [{ title: 'Heat', rating: 7 }],
  },
  year_stats: { oldest_year: 1995, newest_year: 2023, decade_stats: { '1990s': 1, '2020s': 3 } },
  director_stats: {
    top_directors: [{ director: 'Michael <b>Mann</b>', count: 2 }],
    highest_rated_directors: [{ director: 'Celine Song', avg_rating: 9, count: 1 }],
  },
};

test('the statistics tab has one overview and a tab list, and the old accordions are gone', () => {
  assert.match(page, /<link rel="stylesheet" href="\/static\/statistics\.css\?v=/);
  assert.match(page, /id="statsFormatTabs" class="stats-tabs" role="tablist"/);
  assert.match(page, /id="statsFormatPanels"/);
  for (const id of ['timeSpent', 'monthlyReplay', 'tasteprint']) assert.ok(page.includes(`id="${id}"`), id);
  assert.ok(!page.includes('data-toggle-category-accordion'));
  assert.ok(!source.includes('toggleCategoryAccordion'));
});

test('a format panel escapes titles and names that came from the library', () => {
  const { context, get } = setup();
  context.displayCategoryStatistics(movies, 'movies');
  const html = get('moviesStatsData').innerHTML;
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('Michael &lt;b&gt;Mann&lt;/b&gt;'));
  assert.ok(html.includes('From 1995 to 2023.'));
  assert.ok(html.includes('aria-label="75% of your movies finished"'));
  assert.ok(!html.includes('style='), 'sizes go through the CSSOM, never a style attribute');
});

test('the rating chart has a column for 1 to 10 and gives each one a sentence', () => {
  const { context } = setup();
  const html = context.statsHistogram({ 7: 1, 9: 2 }, 'movies');
  assert.equal((html.match(/class="stats-hist__col"/g) || []).length, 10);
  assert.ok(html.includes('<span class="sr-only">Rated 9: 2 titles</span>'));
  assert.ok(html.includes('<span class="sr-only">Rated 7: 1 title</span>'));
  assert.ok(html.includes('<span class="sr-only">Rated 1: 0 titles</span>'));
  assert.ok(html.includes('data-stats-h="100.0"'));
  // A rating under 0.5 is the only thing that adds a 0 column.
  assert.equal((context.statsHistogram({ 0: 1, 9: 2 }, 'movies').match(/class="stats-hist__col"/g) || []).length, 11);
  assert.match(context.statsHistogram({}, 'movies'), /No ratings yet/);
});

test('an empty format offers its shelf and draws no charts', () => {
  const { context, get } = setup();
  context.displayCategoryStatistics({ watch_stats: { total_items: 0 } }, 'podcasts');
  const html = get('podcastsStatsData').innerHTML;
  assert.ok(html.includes('No podcasts yet'));
  assert.ok(html.includes('data-switch-tab="podcasts"'));
  assert.ok(!html.includes('stats-hist'));
});

test('tabs list every format in use, skip hidden empty ones, and open on the biggest shelf', () => {
  const { context, get, fetched } = setup({ hiddenTabs: ['music', 'manga'] });
  context.renderStatsFormatTabs({ categories: [
    { key: 'movies', total: 4 }, { key: 'anime', total: 9 }, { key: 'manga', total: 2 }, { key: 'music', total: 0 },
  ] });
  const tabs = get('statsFormatTabs').innerHTML;
  const listed = Array.from(tabs.matchAll(/data-stats-format="([a-z-]+)"/g), match => match[1]);
  // Manga is hidden from the member's menu but still holds titles, so it stays. Music is hidden and empty.
  assert.deepEqual(listed, ['movies', 'tv-shows', 'anime', 'video-games', 'books', 'manga', 'podcasts', 'audiobooks']);
  assert.equal((tabs.match(/role="tab"/g) || []).length, 8);
  assert.deepEqual(fetched, ['/statistics/anime/']);
});
