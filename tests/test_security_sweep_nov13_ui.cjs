// Sweep of the Nov 12 merges (#201-#204): the parts that run in the browser.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(ROOT, 'app/static/dashboard/lazy/statistics.js'), 'utf8');

function escapeHtml(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setup(answers) {
  const elements = new Map();
  const makeElement = id => ({
    id, hidden: false, innerHTML: '', textContent: '', children: [], dataset: {}, style: { display: '', setProperty() {} },
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
    getTabButton: () => ({ style: { display: '' } }),
    authenticatedFetch: async (url) => {
      fetched.push(url);
      const body = answers[url];
      return body === undefined ? { ok: false } : { ok: true, json: async () => body };
    },
  });
  vm.runInContext(source, context);
  return { context, get, fetched };
}

const insights = {
  total_items: 4, completed_items: 3, backlog_items: 1, completion_percentage: 75, rated_items: 2,
  reviewed_items: 0, public_reviews: 0,
  categories: [{ key: 'movies', label: 'Movies', total: 4, completed: 3, completion_percentage: 75 }],
  top_category: { label: 'Movies', total: 4 },
};
const ratings = {
  total_rated_items: 2, average_rating: 8, rating_distribution: { 7: 1, 9: 1 },
  highest_rated: [{ title: 'Arrival', type: 'Movie', rating: 9 }], lowest_rated: [{ title: 'Heat', type: 'Movie', rating: 7 }],
};
const years = { oldest_year: 1995, newest_year: 2016, decade_stats: { '1990s': 1, '2010s': 3 } };

test('the overview asks for ratings and years only, not the whole statistics dashboard', async () => {
  const { context, get, fetched } = setup({
    '/statistics/insights/': insights, '/statistics/ratings/': ratings, '/statistics/years/': years,
  });
  await context.renderStatsPage();
  assert.deepEqual(fetched.slice(0, 3).sort(), ['/statistics/insights/', '/statistics/ratings/', '/statistics/years/']);
  assert.ok(!fetched.includes('/statistics/'));
  const html = get('libraryInsightsStatsData').innerHTML;
  assert.ok(html.includes('Arrival') && html.includes('Heat'), 'highest and lowest rated still show');
  assert.ok(html.includes('1990s') && html.includes('From 1995 to 2016.'), 'release decades still show');
});

test('the overview still shows the counts when ratings or years fail', async () => {
  const { context, get } = setup({ '/statistics/insights/': insights });
  await context.renderStatsPage();
  const html = get('libraryInsightsStatsData').innerHTML;
  assert.ok(html.includes('Titles saved'));
  assert.ok(html.includes('No ratings yet') && html.includes('No release years saved yet.'));
});
