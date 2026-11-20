// Find people: cards are drawn from text, links stay on the site, and empty states say why.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag) {
  return {
    tagName: tag, children: [], attributes: {}, dataset: {}, className: '', textContent: '', hidden: false, style: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    addEventListener() {},
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name]; },
  };
}

function load(nodes = {}) {
  const module = { exports: {} };
  const document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    createElement: element,
    createTextNode: text => ({ textContent: text }),
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  const context = vm.createContext({ module, window: { addEventListener() {}, location: { hash: '' } }, document,
    setTimeout: () => 0, clearTimeout() {}, Date });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/find-people.js'), 'utf8'), context);
  return module.exports;
}

function text(node) {
  return (node.textContent || '') + (node.children || []).map(text).join('');
}

function find(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children || []) {
    const hit = find(child, predicate);
    if (hit) return hit;
  }
  return null;
}

test('initial avatars get a stable colour from the name', () => {
  const { hue } = load();
  assert.equal(hue('dana'), hue('dana'));
  assert.ok(hue('dana') >= 0 && hue('dana') < 8);
});

test('only same-site links and https images are used', () => {
  const { safePath, safeImage } = load();
  assert.equal(safePath('/u/twin'), '/u/twin');
  assert.equal(safePath('//evil.example'), null);
  assert.equal(safePath('javascript:alert(1)'), null);
  assert.equal(safeImage('https://img.example/a.jpg'), 'https://img.example/a.jpg');
  assert.equal(safeImage('http://img.example/a.jpg'), null);
});

test('a card keeps server text as text and drops off-site links', () => {
  const { card } = load();
  const node = card({ id: 4, username: '<b>twin</b>', profile_url: '//evil.example', source: 'taste',
    reason: 'You both loved <img src=x>', bio: 'Hi', compare_url: '/u/twin/match',
    titles: [{ title: 'Dune', url: '/titles/movie/dune-2021', image: 'javascript:x' }] });
  assert.ok(text(node).includes('<b>twin</b>') && text(node).includes('You both loved <img src=x>'));
  const name = find(node, n => n.className === 'people-card__name');
  assert.equal(name.tagName, 'span');
  const poster = find(node, n => n.className === 'people-title__art');
  assert.equal(poster.children.length, 0);
  assert.equal(poster.textContent, 'D');
  const dismiss = find(node, n => n.className === 'people-card__dismiss');
  assert.equal(dismiss.attributes['aria-label'], 'Not for me: hide <b>twin</b>');
  assert.ok(find(node, n => n.className === 'people-card__link' && n.textContent === 'Compare tastes'));
});

test('a follower without a public profile gets a friend request button', () => {
  const { backRow } = load();
  const open = backRow({ id: 1, username: 'fan', profile_url: '/u/fan', source: 'back', reason: 'Followed you today', can_follow: true });
  assert.ok(find(open, n => n.textContent === 'Follow back'));
  const closed = backRow({ id: 2, username: 'lurker', profile_url: null, source: 'back', reason: 'Followed you yesterday',
    can_follow: false, can_friend: true });
  assert.ok(find(closed, n => n.textContent === 'Add as friend'));
  const pending = backRow({ id: 3, username: 'asked', source: 'back', reason: '', can_follow: false, friend_pending: true });
  const sent = find(pending, n => n.textContent === 'Request sent');
  assert.ok(sent && sent.disabled);
});

test('empty results say why, and the profile prompt shows when the profile is off', () => {
  const nodes = { peoplePanel: element('section'), peopleGroups: element('div'), peopleStatus: element('p'),
    peopleBack: element('section'), peopleBackList: element('ul'), peopleYou: element('div'), peopleTasteHint: element('p') };
  const { render } = load(nodes);
  render({ follow_back: [], groups: [], you: { profile_enabled: false, library: 2, needs_titles: 3 } });
  assert.match(nodes.peopleStatus.textContent, /Rate a few more titles/);
  assert.equal(nodes.peopleYou.hidden, false);
  assert.ok(text(nodes.peopleYou).includes('Turn on my public profile'));
  assert.match(nodes.peopleTasteHint.textContent, /Add 3 more titles/);
  assert.equal(nodes.peopleBack.hidden, true);
  render({ follow_back: [], groups: [{ key: 'taste', title: 'Similar taste', people: [{ id: 5, username: 'twin', reason: 'x', titles: [] }] }],
    you: { profile_enabled: true, allow_followers: true, suggest_me: true, library: 9, needs_titles: 0 } });
  assert.equal(nodes.peopleStatus.textContent, '');
  assert.equal(nodes.peopleYou.hidden, true);
  assert.equal(nodes.peopleGroups.children.length, 1);
  assert.equal(nodes.peopleTasteHint.hidden, true);
});

test('the rail card hides when there is nobody to show', () => {
  const nodes = { followSuggestions: element('section'), followSuggestionsList: element('ul') };
  const { renderRail } = load(nodes);
  renderRail({ people: [] });
  assert.equal(nodes.followSuggestions.hidden, true);
  renderRail({ people: [{ id: 1, username: 'fan', profile_url: '/u/fan', source: 'back', reason: 'Followed you today' }] });
  assert.equal(nodes.followSuggestions.hidden, false);
  assert.ok(find(nodes.followSuggestionsList, n => n.textContent === 'Follow back'));
});
