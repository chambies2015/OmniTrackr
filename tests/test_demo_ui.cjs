const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/demo.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../app/templates/demo.html'), 'utf8');

function setup() {
  let activeElement = null;
  const sideEffects = [];
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.attributes = {};
      this.events = new Map(); this.hidden = false; this.disabled = false; this.value = ''; this.checked = false;
      this.validity = {badInput: false}; this._text = ''; this.id = ''; this.className = '';
    }
    set textContent(text) {this._text = String(text); this.children = [];}
    get textContent() {return this._text + this.children.map(child => child.textContent).join('');}
    set innerHTML(_) {throw new Error('The demo must never interpolate content as HTML');}
    append(...nodes) {this.children.push(...nodes);}
    replaceChildren(...nodes) {this._text = ''; this.children = [...nodes];}
    setAttribute(key, value) {this.attributes[key] = value;}
    addEventListener(name, handler) {this.events.set(name, handler);}
    querySelectorAll(selector) {return descendants(this).filter(node => selector === 'button' && node.tagName === 'BUTTON');}
    focus() {activeElement = this;}
    trigger(name, props = {}) {
      const event = {defaultPrevented: false, preventDefault() {this.defaultPrevented = true;}, ...props};
      this.events.get(name)?.(event);
      return event;
    }
  }
  function descendants(node) {return node.children.flatMap(child => [child, ...descendants(child)]);}
  const roots = [...template.matchAll(/\bid="([^"]+)"/g)].map(match => {const node = new Element(); node.id = match[1]; return node;});
  const get = id => roots.find(node => node.id === id) || roots.flatMap(descendants).find(node => node.id === id);
  const filters = ['all', 'movie', 'tv_show', 'anime', 'video_game', 'music', 'book'].map(category => {
    const node = new Element('button'); node.dataset.category = category; get('demoFilters').append(node); return node;
  });
  ['demoToolbar', 'demoFilters', 'demoCatalog', 'demoEditor', 'demoEditError'].forEach(id => {get(id).hidden = true;});
  const events = new Map();
  const forbidden = name => () => {sideEffects.push(name); throw Error(`Unexpected ${name}`);};
  const context = vm.createContext({
    document: {getElementById: get, createElement: tag => new Element(tag), addEventListener: (name, handler) => events.set(name, handler)},
    fetch: forbidden('fetch'), XMLHttpRequest: forbidden('XMLHttpRequest'),
    localStorage: {getItem: forbidden('localStorage read'), setItem: forbidden('localStorage write')},
    sessionStorage: {getItem: forbidden('sessionStorage read'), setItem: forbidden('sessionStorage write')},
    navigator: {sendBeacon: forbidden('beacon')},
  });
  vm.runInContext(script, context);
  return {
    get, events, sideEffects, descendants,
    filter(category) {filters.find(node => node.dataset.category === category).trigger('click');},
    filterButton: category => filters.find(node => node.dataset.category === category),
    cards: () => get('demoCards').children,
    card: id => get('demoCards').children.find(node => node.dataset.sampleId === id),
    edit(id) {get(`demoEdit-${id}`).trigger('click');},
    save() {return get('demoEditForm').trigger('submit');},
    add(id) {get('demoAdd').trigger('click'); get(`demoCatalogAdd-${id}`).trigger('click');},
    active: () => activeElement,
  };
}

test('enhancement starts with six fictional cards and statistics matching the static fallback', () => {
  const s = setup();
  assert.equal(s.cards().length, 6);
  assert.equal(s.get('demoTotal').textContent, '6');
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.equal(s.get('demoNext').textContent, '3');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  for (const card of s.cards()) {
    assert.ok(template.includes(`data-sample-id="${card.dataset.sampleId}"`));
    const heading = s.descendants(card).find(node => node.tagName === 'H3').textContent;
    assert.ok(template.includes(`<h3>${heading}</h3>`));
  }
  assert.equal(s.get('demoToolbar').hidden, false);
  assert.equal(s.get('demoFilters').hidden, false);
  assert.match(template, /href="\/\?start=demo#landing-auth"/);
  assert.match(template, /<noscript>/);
});

test('category filtering reports visible count while keeping whole-library statistics', () => {
  const s = setup();
  s.filter('book');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['letters-tomorrow']);
  assert.equal(s.get('demoTotal').textContent, '6');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  assert.match(s.get('demoStatus').textContent, /Books: 1 sample title.*whole sample library/);
  assert.equal(s.filterButton('book').attributes['aria-pressed'], 'true');
  assert.equal(s.filterButton('all').attributes['aria-pressed'], 'false');
  s.filter('all');
  assert.equal(s.cards().length, 6);
});

test('adding switches to the sample category and focuses its edit action without duplicates', () => {
  const s = setup();
  s.filter('movie');
  s.get('demoAdd').trigger('click');
  assert.equal(s.get('demoCatalog').hidden, false);
  assert.equal(s.active().id, 'demoCatalogHeading');
  const originalAdd = s.get('demoCatalogAdd-borrowed-summer');
  originalAdd.trigger('click');
  assert.equal(s.get('demoTotal').textContent, '7');
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.equal(s.get('demoNext').textContent, '4');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['letters-tomorrow', 'borrowed-summer']);
  assert.equal(s.active().id, 'demoEdit-borrowed-summer');
  assert.equal(s.filterButton('book').attributes['aria-pressed'], 'true');
  assert.equal(s.get('demoCatalog').hidden, true);
  assert.match(s.card('borrowed-summer').textContent, /Not finishedUnrated/);
  originalAdd.trigger('click');
  assert.equal(s.get('demoTotal').textContent, '7');
  s.get('demoAdd').trigger('click');
  assert.equal(s.get('demoCatalogAdd-borrowed-summer').disabled, true);
});

test('zero ratings count toward the average and edits change only the chosen sample', () => {
  const s = setup();
  const untouched = s.card('lantern-atlas').textContent;
  s.edit('northbound');
  assert.equal(s.active().id, 'demoEditFinished');
  s.get('demoEditFinished').checked = true;
  s.get('demoEditRating').value = '0';
  s.get('demoEditNote').value = 'A note about the ending';
  assert.equal(s.save().defaultPrevented, true);
  assert.equal(s.get('demoFinished').textContent, '4');
  assert.equal(s.get('demoNext').textContent, '2');
  assert.equal(s.get('demoAverage').textContent, '6.4 / 10');
  assert.match(s.card('northbound').textContent, /Watched0 \/ 10A note about the ending/);
  assert.equal(s.card('lantern-atlas').textContent, untouched);
  assert.equal(s.active().id, 'demoEdit-northbound');
  assert.equal(s.get('demoEditor').hidden, true);
});

test('invalid ratings cannot mutate completion, ratings, or notes', () => {
  const s = setup();
  const original = s.card('lantern-atlas').textContent;
  for (const value of ['-1', '11', '8.75', 'Infinity', 'not a number']) {
    s.edit('lantern-atlas');
    s.get('demoEditFinished').checked = false;
    s.get('demoEditRating').value = value;
    s.get('demoEditNote').value = 'Should not save';
    assert.equal(s.save().defaultPrevented, true);
    assert.equal(s.get('demoEditError').hidden, false);
    assert.equal(s.get('demoEditor').hidden, false);
    assert.equal(s.card('lantern-atlas').textContent, original);
    assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  }
  s.get('demoEditRating').value = '';
  s.get('demoEditRating').validity.badInput = true;
  s.save();
  assert.equal(s.card('lantern-atlas').textContent, original);
});

test('valid decimal and ten ratings work; clearing every rating shows an unrated average', () => {
  const s = setup();
  s.edit('lantern-atlas'); s.get('demoEditRating').value = '10'; s.save();
  assert.match(s.card('lantern-atlas').textContent, /10 \/ 10/);
  s.edit('lantern-atlas'); s.get('demoEditRating').value = '8.1'; s.save();
  assert.match(s.card('lantern-atlas').textContent, /8.1 \/ 10/);
  for (const id of ['lantern-atlas', 'quiet-observatory', 'after-rain']) {
    s.edit(id); s.get('demoEditRating').value = ''; s.save();
    assert.match(s.card(id).textContent, /Unrated/);
  }
  assert.equal(s.get('demoAverage').textContent, '—');
});

test('practice notes are literal text, preserve line breaks, and respect the 500 character limit', () => {
  const s = setup();
  const note = '<img src=x onerror="alert(1)">\n<script>steal()</script>';
  s.edit('northbound'); s.get('demoEditNote').value = note; s.save();
  const rendered = s.descendants(s.card('northbound')).find(node => node.className === 'demo-note');
  assert.equal(rendered.textContent, note);
  assert.equal(rendered.children.length, 0);
  s.edit('northbound'); s.get('demoEditNote').value = 'n'.repeat(500); s.save();
  assert.match(s.card('northbound').textContent, /n{500}/);
  s.edit('northbound'); s.get('demoEditNote').value = 'n'.repeat(501); s.save();
  assert.equal(s.get('demoEditor').hidden, false);
  assert.match(s.get('demoEditError').textContent, /500/);
});

test('cancel, Escape, and changing filters discard unsaved edits and preserve keyboard focus', () => {
  const s = setup();
  s.edit('northbound'); s.get('demoEditNote').value = 'Unsaved'; s.get('demoEditCancel').trigger('click');
  assert.equal(s.active().id, 'demoEdit-northbound');
  assert.doesNotMatch(s.card('northbound').textContent, /Unsaved/);
  s.edit('northbound'); s.get('demoEditRating').value = '9'; s.events.get('keydown')({key: 'Escape'});
  assert.equal(s.get('demoEditor').hidden, true);
  assert.equal(s.active().id, 'demoEdit-northbound');
  s.get('demoAdd').trigger('click'); s.events.get('keydown')({key: 'Escape'});
  assert.equal(s.get('demoCatalog').hidden, true);
  assert.equal(s.get('demoAdd').attributes['aria-expanded'], 'false');
  assert.equal(s.active().id, 'demoAdd');
  s.edit('northbound'); s.get('demoEditRating').value = '9'; s.filter('book');
  s.save(); s.filter('tv_show');
  assert.match(s.card('northbound').textContent, /Unrated/);
});

test('reset removes additions and edits, restores initial filters and statistics, and hides panels', () => {
  const s = setup();
  s.add('tideline');
  s.edit('tideline'); s.get('demoEditFinished').checked = true; s.get('demoEditRating').value = '10'; s.save();
  s.get('demoReset').trigger('click');
  assert.equal(s.cards().length, 6);
  assert.equal(s.card('tideline'), undefined);
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  assert.equal(s.filterButton('all').attributes['aria-pressed'], 'true');
  assert.equal(s.get('demoEditor').hidden, true);
  assert.equal(s.get('demoCatalog').hidden, true);
  assert.match(s.get('demoStatus').textContent, /Demo reset/);
  s.get('demoAdd').trigger('click');
  assert.equal(s.get('demoCatalogAdd-tideline').disabled, false);
});

test('all six extra samples are unique and stay in memory without any network or storage access', () => {
  const s = setup();
  for (const id of ['last-lighthouse', 'midnight-diner', 'paper-moons', 'tideline', 'small-hours', 'borrowed-summer']) s.add(id);
  s.filter('all');
  assert.equal(s.cards().length, 12);
  assert.equal(new Set(s.cards().map(card => card.dataset.sampleId)).size, 12);
  assert.equal(s.get('demoNext').textContent, '9');
  assert.deepEqual(s.sideEffects, []);
  const reloaded = setup();
  assert.equal(reloaded.cards().length, 6);
  assert.equal(reloaded.get('demoTotal').textContent, '6');
});

test('unexpected filter values do not enter the rendering path', () => {
  const s = setup();
  s.filterButton('book').dataset.category = '__proto__';
  s.filterButton('all').trigger('click');
  s.get('demoFilters').children.at(-1).trigger('click');
  assert.equal(s.cards().length, 6);
});
