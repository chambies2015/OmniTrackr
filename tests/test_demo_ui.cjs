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
  const completionFilters = ['all', 'unfinished', 'finished'].map(completion => {
    const node = completion === 'all' ? get('demoCompletionAll') : new Element('button');
    node.tagName = 'BUTTON'; node.dataset.completion = completion;
    get('demoCompletionFilters').append(node); return node;
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
    completion(value) {completionFilters.find(node => node.dataset.completion === value).trigger('click');},
    completionButton: value => completionFilters.find(node => node.dataset.completion === value),
    cards: () => get('demoCards').children,
    card: id => get('demoCards').children.find(node => node.dataset.sampleId === id),
    edit(id) {get(`demoEdit-${id}`).trigger('click');},
    save() {return get('demoEditForm').trigger('submit');},
    saveProgress() {return get('demoProgressForm').trigger('submit');},
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

test('completion and unrated filters combine across categories without changing whole-library statistics', () => {
  const s = setup();
  s.completion('finished');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['lantern-atlas', 'after-rain', 'letters-tomorrow']);
  s.get('demoUnrated').trigger('click');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['letters-tomorrow']);
  assert.equal(s.get('demoResultCount').textContent, 'Showing 1 of 6 sample titles');
  assert.equal(s.get('demoTotal').textContent, '6');
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  s.filter('book');
  assert.equal(s.get('demoResultCount').textContent, 'Showing 1 of 1 sample title');
  assert.equal(s.completionButton('finished').textContent, 'Read');
  assert.equal(s.completionButton('unfinished').textContent, 'Unread');
  assert.equal(s.completionButton('finished').attributes['aria-pressed'], 'true');
  assert.equal(s.get('demoUnrated').attributes['aria-pressed'], 'true');
  assert.match(template, /Books → Read → Unrated/);
  assert.deepEqual(s.sideEffects, []);
});

test('empty results offer a category-preserving reset with usable focus and no lost edits', () => {
  const s = setup();
  s.filter('book');
  s.edit('letters-tomorrow');
  s.get('demoEditNote').value = 'Keep this practice note';
  s.save();
  s.completion('unfinished');
  assert.equal(s.cards().length, 0);
  assert.equal(s.get('demoEmpty').hidden, false);
  assert.equal(s.get('demoResultCount').textContent, 'Showing 0 of 1 sample title');
  assert.equal(s.get('demoClearFilters').disabled, false);
  s.get('demoEmptyClear').trigger('click');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['letters-tomorrow']);
  assert.match(s.card('letters-tomorrow').textContent, /Keep this practice note/);
  assert.equal(s.get('demoEmpty').hidden, true);
  assert.equal(s.get('demoClearFilters').disabled, true);
  assert.equal(s.filterButton('book').attributes['aria-pressed'], 'true');
  assert.equal(s.active().id, 'demoCompletionAll');
});

test('saved progress filtering is available only in supported categories and combines with completion', () => {
  const s = setup();
  assert.equal(s.get('demoHasProgress').hidden, true);
  s.get('demoHasProgress').trigger('click');
  assert.equal(s.cards().length, 6);
  s.add('midnight-diner');
  assert.equal(s.get('demoHasProgress').hidden, false);
  s.get('demoHasProgress').trigger('click');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['northbound']);
  s.completion('unfinished');
  assert.equal(s.cards().length, 1);
  s.completion('finished');
  assert.equal(s.cards().length, 0);
  s.completion('all');
  s.filter('movie');
  assert.equal(s.get('demoHasProgress').hidden, true);
  assert.equal(s.get('demoHasProgress').attributes['aria-pressed'], 'false');
  assert.equal(s.cards().length, 1);
  s.filter('tv_show');
  assert.equal(s.cards().length, 2);
  s.get('demoHasProgress').trigger('click');
  s.edit('northbound');
  s.get('demoProgressClear').trigger('click');
  assert.equal(s.cards().length, 0);
  assert.equal(s.get('demoEmpty').hidden, false);
  s.get('demoProgressPosition').value = '5';
  s.saveProgress();
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['northbound']);
});

test('editing a filtered sample immediately reevaluates results and treats a zero rating as rated', () => {
  const s = setup();
  s.filter('book');
  s.completion('finished');
  s.get('demoUnrated').trigger('click');
  s.edit('letters-tomorrow');
  s.get('demoEditRating').value = '0';
  s.save();
  assert.equal(s.cards().length, 0);
  assert.equal(s.get('demoResultCount').textContent, 'Showing 0 of 1 sample title');
  assert.equal(s.active().id, 'demoAdd');
  s.get('demoUnrated').trigger('click');
  assert.match(s.card('letters-tomorrow').textContent, /Read0 \/ 10/);
  s.edit('letters-tomorrow');
  s.get('demoEditFinished').checked = false;
  s.save();
  assert.equal(s.cards().length, 0);
  s.completion('unfinished');
  assert.equal(s.cards().length, 1);
});

test('adding reveals the new sample and resetting restores data and every quick filter', () => {
  const s = setup();
  s.filter('book');
  s.completion('finished');
  s.get('demoUnrated').trigger('click');
  s.get('demoHasProgress').trigger('click');
  s.add('borrowed-summer');
  assert.deepEqual(s.cards().map(card => card.dataset.sampleId), ['letters-tomorrow', 'borrowed-summer']);
  assert.equal(s.completionButton('all').attributes['aria-pressed'], 'true');
  assert.equal(s.get('demoUnrated').attributes['aria-pressed'], 'false');
  assert.equal(s.get('demoHasProgress').attributes['aria-pressed'], 'false');
  assert.equal(s.active().id, 'demoEdit-borrowed-summer');
  s.completion('unfinished');
  s.get('demoUnrated').trigger('click');
  s.get('demoHasProgress').trigger('click');
  s.get('demoReset').trigger('click');
  assert.equal(s.cards().length, 6);
  assert.equal(s.get('demoResultCount').textContent, 'Showing 6 of 6 sample titles');
  assert.equal(s.get('demoClearFilters').disabled, true);
  assert.equal(s.get('demoHasProgress').hidden, true);
  assert.equal(s.completionButton('all').attributes['aria-pressed'], 'true');
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

test('show and book checkpoints match the static fallback and only supported samples expose progress', () => {
  const s = setup();
  for (const [id, summary] of [
    ['northbound', 'Last watched: season 1, episode 4'],
    ['quiet-observatory', 'Last watched: season 1, episode 12'],
    ['letters-tomorrow', 'Last read: page 84'],
  ]) {
    assert.ok(s.card(id).textContent.includes(summary));
    assert.ok(template.includes(summary));
    s.edit(id);
    assert.equal(s.get('demoProgressForm').hidden, false);
  }
  for (const id of ['lantern-atlas', 'garden-circuit', 'after-rain']) {
    s.edit(id);
    assert.equal(s.get('demoProgressForm').hidden, true);
    const before = s.card(id).textContent;
    s.saveProgress();
    assert.equal(s.card(id).textContent, before);
  }
});

test('updating a checkpoint preserves completion, rating, note, and unsaved general edits', () => {
  const s = setup();
  s.edit('northbound');
  s.get('demoEditFinished').checked = true;
  s.get('demoEditRating').value = '10';
  s.get('demoEditNote').value = 'An unsaved review';
  s.get('demoProgressPosition').value = '5';
  s.get('demoProgressSeason').value = '2';
  s.get('demoProgressNote').value = 'Continue with the reunion.';
  s.saveProgress();
  assert.match(s.card('northbound').textContent, /Last watched: season 2, episode 5/);
  assert.match(s.card('northbound').textContent, /Continue with the reunion/);
  assert.match(s.card('northbound').textContent, /Not finishedUnrated/);
  assert.doesNotMatch(s.card('northbound').textContent, /An unsaved review/);
  assert.equal(s.get('demoEditNote').value, 'An unsaved review');
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.equal(s.get('demoAverage').textContent, '8.5 / 10');
  assert.equal(s.get('demoEditor').hidden, false);
  s.get('demoEditCancel').trigger('click');
  s.edit('northbound');
  assert.equal(s.get('demoEditFinished').checked, false);
  assert.equal(s.get('demoEditRating').value, '');
  assert.equal(s.get('demoEditNote').value, '');
  assert.equal(s.get('demoProgressPosition').value, '5');
});

test('season zero, optional season, page and chapter progress are accepted without finishing samples', () => {
  const s = setup();
  s.edit('quiet-observatory');
  s.get('demoProgressSeason').value = '0';
  s.get('demoProgressPosition').value = '2';
  s.saveProgress();
  assert.match(s.card('quiet-observatory').textContent, /Last watched: season 0, episode 2/);
  s.get('demoProgressSeason').value = '';
  s.get('demoProgressPosition').value = '1000000';
  s.saveProgress();
  assert.match(s.card('quiet-observatory').textContent, /Last watched: episode 1000000/);
  s.edit('letters-tomorrow');
  assert.equal(s.get('demoProgressSeasonField').hidden, true);
  assert.equal(s.get('demoProgressUnitField').hidden, false);
  s.get('demoProgressUnit').value = 'chapter';
  s.get('demoProgressUnit').trigger('change');
  assert.equal(s.get('demoProgressPositionLabel').textContent, 'Last read chapter');
  s.get('demoProgressPosition').value = '9';
  s.saveProgress();
  assert.match(s.card('letters-tomorrow').textContent, /Last read: chapter 9/);
  assert.doesNotMatch(s.card('letters-tomorrow').textContent, /Last read: page/);
  assert.match(s.card('letters-tomorrow').textContent, /ReadUnrated/);
  assert.equal(s.get('demoFinished').textContent, '3');
  assert.deepEqual(s.sideEffects, []);
});

test('invalid checkpoint values never replace the saved checkpoint or other sample fields', () => {
  const s = setup();
  const original = s.card('northbound').textContent;
  for (const position of ['', '0', '-1', '1.5', '1e3', 'Infinity', 'no', '1000001']) {
    s.edit('northbound');
    s.get('demoProgressPosition').value = position;
    s.saveProgress();
    assert.equal(s.card('northbound').textContent, original, position);
    assert.equal(s.get('demoProgressError').hidden, false);
  }
  for (const season of ['-1', '0.5', '1e2', '10001', 'Infinity']) {
    s.edit('northbound');
    s.get('demoProgressSeason').value = season;
    s.saveProgress();
    assert.equal(s.card('northbound').textContent, original, season);
    assert.equal(s.active().id, 'demoProgressSeason');
  }
  s.edit('northbound');
  s.get('demoProgressPosition').validity.badInput = true;
  s.saveProgress();
  assert.equal(s.card('northbound').textContent, original);
  s.get('demoProgressPosition').validity.badInput = false;
  s.edit('letters-tomorrow');
  const book = s.card('letters-tomorrow').textContent;
  s.get('demoProgressUnit').value = 'episode';
  s.saveProgress();
  assert.equal(s.card('letters-tomorrow').textContent, book);
});

test('checkpoint reminders are literal text and limited to 300 characters', () => {
  const s = setup();
  s.edit('northbound');
  const note = '<img src=x onerror=alert(1)>\n<script>no()</script>';
  s.get('demoProgressNote').value = note;
  s.saveProgress();
  const rendered = s.descendants(s.card('northbound')).find(node => node.className === 'demo-progress-reminder');
  assert.equal(rendered.textContent, note);
  assert.equal(rendered.children.length, 0);
  s.get('demoProgressNote').value = 'n'.repeat(300);
  s.saveProgress();
  assert.match(s.card('northbound').textContent, /n{300}/);
  s.get('demoProgressNote').value = 'n'.repeat(301);
  s.saveProgress();
  assert.match(s.get('demoProgressError').textContent, /300/);
  assert.doesNotMatch(s.card('northbound').textContent, /n{301}/);
});

test('clearing progress preserves all other fields and reset or reload restores original checkpoints', () => {
  const s = setup();
  s.edit('quiet-observatory');
  s.get('demoProgressClear').trigger('click');
  assert.match(s.card('quiet-observatory').textContent, /Not finished8 \/ 10Loved the quiet moments/);
  assert.match(s.card('quiet-observatory').textContent, /No checkpoint yet/);
  assert.equal(s.get('demoProgressPosition').value, '');
  assert.equal(s.get('demoProgressNote').value, '');
  assert.equal(s.get('demoProgressClear').disabled, true);
  assert.equal(s.active().id, 'demoProgressPosition');
  s.edit('letters-tomorrow');
  s.get('demoProgressPosition').value = '200';
  s.saveProgress();
  s.get('demoReset').trigger('click');
  assert.match(s.card('quiet-observatory').textContent, /Last watched: season 1, episode 12/);
  assert.match(s.card('letters-tomorrow').textContent, /Last read: page 84/);
  const reloaded = setup();
  assert.match(reloaded.card('letters-tomorrow').textContent, /Last read: page 84/);
  assert.deepEqual(s.sideEffects, []);
});
