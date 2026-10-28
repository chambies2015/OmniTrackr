// Dashboard "Add to my calendar" panel on the "Coming up for you" card.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.hidden = false; this.textContent = ''; this.href = '#'; this.attrs = {}; this.disabled = false; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  addEventListener() {}
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
}

const LINKS = {
  url: 'https://omnitrackr.xyz/calendar/u/tok.ics',
  webcal: 'webcal://omnitrackr.xyz/calendar/u/tok.ics',
  google: 'https://calendar.google.com/calendar/r?cid=webcal%3A%2F%2Fomnitrackr.xyz%2Fcalendar%2Fu%2Ftok.ics',
  outlook: 'https://outlook.live.com/calendar/0/addfromweb?url=x&name=y',
};

function setup(responses) {
  const ids = ['comingUp', 'comingUpStatus', 'comingUpCalendarButton', 'releaseCalendarPanel', 'releaseCalendarGoogle',
    'releaseCalendarApple', 'releaseCalendarOutlook', 'releaseCalendarCopy', 'releaseCalendarReset', 'releaseCalendarOff',
    'releaseCalendarStatus'];
  const nodes = Object.fromEntries(ids.map(id => [id, new Node('div')]));
  nodes.releaseCalendarPanel.hidden = true;
  const calls = [];
  global.document = {
    readyState: 'complete', getElementById: id => nodes[id] || null, querySelector: () => null,
    createElement: tag => new Node(tag), addEventListener() {},
  };
  global.window = { location: { hash: '' }, addEventListener() {} };
  global.localStorage = { getItem: () => null, setItem() {} };
  global.fetch = async (url, options = {}) => {
    calls.push([options.method || 'GET', url]);
    const body = responses.shift();
    return { ok: body.ok !== false, json: async () => body };
  };
  delete require.cache[require.resolve('../app/static/for-you.js')];
  const module = require(path.join(__dirname, '../app/static/for-you.js'));
  return { nodes, module, calls };
}

test('opening the calendar turns it on and fills the subscribe links', async () => {
  const { nodes, module, calls } = setup([{ enabled: true, links: LINKS }]);
  await module.openCalendar();
  assert.deepEqual(calls, [['POST', '/api/calendar']]);
  assert.equal(nodes.releaseCalendarPanel.hidden, false);
  assert.equal(nodes.comingUpCalendarButton.attrs['aria-expanded'], 'true');
  assert.equal(nodes.releaseCalendarGoogle.href, LINKS.google);
  assert.equal(nodes.releaseCalendarApple.href, LINKS.webcal);
  assert.equal(nodes.releaseCalendarOutlook.href, LINKS.outlook);
  assert.equal(nodes.comingUpCalendarButton.textContent, 'My calendar');
});

test('links from the server that are not calendar addresses are never used', () => {
  const { nodes, module } = setup([]);
  module.renderCalendar({ enabled: true, links: { google: 'javascript:alert(1)', webcal: 'https://evil.example', outlook: 'x' } });
  assert.equal(nodes.releaseCalendarGoogle.href, '#');
  assert.equal(nodes.releaseCalendarApple.href, '#');
  assert.equal(nodes.releaseCalendarOutlook.href, '#');
});

test('turning the calendar off hides the panel and says the old address stops working', async () => {
  const { nodes, module, calls } = setup([{ enabled: true, links: LINKS }, { enabled: false }]);
  await module.openCalendar();
  await module.turnOffCalendar();
  assert.deepEqual(calls[1], ['DELETE', '/api/calendar']);
  assert.equal(nodes.releaseCalendarPanel.hidden, true);
  assert.match(nodes.comingUpStatus.textContent, /no longer works/);
  assert.equal(nodes.comingUpCalendarButton.textContent, 'Add to my calendar');
});

test('a reset explains that the calendar must be added again', async () => {
  const { nodes, module, calls } = setup([{ enabled: true, links: LINKS }, { enabled: true, links: { ...LINKS, url: 'https://omnitrackr.xyz/calendar/u/new.ics' } }]);
  await module.openCalendar();
  await module.resetCalendar();
  assert.deepEqual(calls[1], ['POST', '/api/calendar/reset']);
  assert.match(nodes.releaseCalendarStatus.textContent, /old one has stopped working/);
});

test('a failed request shows the error and leaves the panel closed', async () => {
  const { nodes, module } = setup([{ ok: false, detail: 'Not authenticated' }]);
  await module.openCalendar();
  assert.equal(nodes.releaseCalendarPanel.hidden, true);
  assert.equal(nodes.comingUpStatus.textContent, 'Not authenticated');
  assert.equal(nodes.comingUpCalendarButton.disabled, false);
});

test('the episodes box reflects the setting and shows how many are coming', () => {
  const { nodes, module } = setup([]);
  nodes.releaseCalendarEpisodes = new Node('input');
  nodes.releaseCalendarEpisodesNote = new Node('small');
  module.renderCalendar({ enabled: true, include_episodes: true, episodes_soon: 3, links: LINKS });
  assert.equal(nodes.releaseCalendarEpisodes.checked, true);
  assert.equal(nodes.releaseCalendarEpisodesNote.textContent, '3 episodes airing in the next two weeks.');
  module.renderCalendar({ enabled: true, include_episodes: false, links: LINKS });
  assert.equal(nodes.releaseCalendarEpisodes.checked, false);
  assert.equal(nodes.releaseCalendarEpisodesNote.textContent, '');
});

test('ticking the episodes box saves it, and a failure puts the box back', async () => {
  const { nodes, module, calls } = setup([{ enabled: true, include_episodes: true, links: LINKS }, { ok: false, detail: 'Nope' }]);
  nodes.releaseCalendarEpisodes = new Node('input');
  nodes.releaseCalendarEpisodes.checked = true;
  await module.saveCalendarEpisodes();
  assert.deepEqual(calls, [['PUT', '/api/calendar/episodes']]);
  assert.match(nodes.releaseCalendarStatus.textContent, /^Episodes on\./);
  nodes.releaseCalendarEpisodes.checked = false;
  await module.saveCalendarEpisodes();
  assert.equal(nodes.releaseCalendarEpisodes.checked, true);
  assert.equal(nodes.releaseCalendarStatus.textContent, 'Nope');
});
