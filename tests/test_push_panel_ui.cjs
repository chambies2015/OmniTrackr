// Phone notifications outside the bell: the panel in Settings > Notifications (push.js)
// and the offer in the episode guide (episodes.js).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const pushScript = fs.readFileSync(path.join(__dirname, '../app/static/push.js'), 'utf8');
const episodesScript = fs.readFileSync(path.join(__dirname, '../app/static/episodes.js'), 'utf8');
const KEY = 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4';

class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.style = {};
    this.hidden = false; this._text = ''; this.className = ''; this.disabled = false; this.checked = false;
    this.classList = {add() {}, remove() {}};
    this.listeners = {};
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent ?? String(child)).join(''); }
  set innerHTML(_) { throw new Error('Server text must be set as textContent.'); }
  append(...nodes) { this.children.push(...nodes.map(node => (typeof node === 'string' ? {textContent: node} : node))); }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; this._text = ''; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  focus() {}
  showModal() { this.open = true; }
  closest(selector) { return selector === `#${this.id}` || selector === `[data-${selector.slice(6, -1)}]` ? this : null; }
  all() { return this.children.flatMap(child => (child instanceof Element ? [child, ...child.all()] : [])); }
  querySelectorAll(selector) {
    const match = /^(\w+)?(?:\[name="([^"]+)"\])?(?:\.([\w-]+))?$/.exec(selector) || [];
    return this.all().filter(node => (!match[1] || node.tagName === match[1]) && (!match[2] || node.name === match[2])
      && (!match[3] || node.className.split(' ').includes(match[3])));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function pushSetup({permission = 'granted', subscribed = true, signedIn = true} = {}) {
  const byId = new Map();
  const el = (id, tag = 'div') => { const node = new Element(tag); node.id = id; byId.set(id, node); return node; };
  // The bell's box and the Settings panel are both on the page.
  ['pushOptIn', 'pushOptInText', 'pushSettingsBtn', 'accountPush', 'accountPushText'].forEach(id => el(id));
  el('pushOptInBtn', 'button'); el('accountPushBtn', 'button');
  el('pushSettings', 'form'); el('accountPushSettings', 'form');
  byId.get('pushSettings').hidden = true; byId.get('accountPushSettings').hidden = true; byId.get('accountPush').hidden = true;
  const calls = [];
  const settings = {topics: [{key: 'episodes', label: 'New episodes', hint: 'When one is out.', on: true},
                             {key: 'reminders', label: 'When you\'ve been away', hint: 'One reminder.', on: true}],
                    quiet_hours: {on: true, start: 22, end: 8}, time_zone: null};
  let subscription = subscribed ? {endpoint: 'https://fcm.googleapis.com/fcm/send/d1', options: {},
                                   toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'p', auth: 'a'}}; },
                                   async unsubscribe() { subscription = null; return true; }} : null;
  const pushManager = {async getSubscription() { return subscription; }};
  const Notification = {permission, async requestPermission() { return 'granted'; }};
  const window = {isSecureContext: true, navigator: {userAgent: 'Chrome', serviceWorker: {ready: Promise.resolve({pushManager})}},
                  PushManager() {}, Notification, matchMedia: () => ({matches: false}), addEventListener() {},
                  atob: value => Buffer.from(value, 'base64').toString('binary')};
  const listeners = {};
  const document = {
    readyState: 'complete',
    getElementById: id => byId.get(id) || null,
    createElement: tag => new Element(tag),
    addEventListener: (name, fn) => { listeners[name] = fn; },
  };
  const authenticatedFetch = async (url, options = {}) => {
    calls.push([options.method || 'GET', url, options.body ? JSON.parse(options.body) : undefined]);
    return {ok: true, async json() { return url.endsWith('/key') ? {public_key: KEY, devices: 1} : settings; }};
  };
  const context = vm.createContext({window, document, navigator: window.navigator, Notification, authenticatedFetch,
    setTimeout, clearTimeout, Promise, Uint8Array, Intl, WeakSet, Date, isAuthenticated: () => signedIn, API_BASE: ''});
  vm.runInContext(pushScript, context);
  return {byId, calls, window, listeners, settle: () => new Promise(resolve => setTimeout(resolve, 0))};
}

test('Settings shows this device is on and lists the switches straight away', async () => {
  const ui = pushSetup();
  await ui.window.omniPush.refresh();
  await ui.settle();
  const panel = ui.byId.get('accountPush');
  assert.equal(panel.hidden, false);
  assert.equal(panel.dataset.state, 'on');
  assert.equal(ui.byId.get('accountPushText').textContent, 'Notifications are on for this device.');
  assert.equal(ui.byId.get('accountPushBtn').textContent, 'Turn off');
  const form = ui.byId.get('accountPushSettings');
  assert.equal(form.hidden, false);
  assert.deepEqual(form.querySelectorAll('input[name="topic"]').map(input => [input.value, input.checked]),
    [['episodes', true], ['reminders', true]]);
  assert.match(form.textContent, /New episodes/);
  // The bell got the same state, and its switches wait behind "Choose what to get" as before.
  assert.equal(ui.byId.get('pushOptIn').dataset.state, 'on');
  assert.equal(ui.byId.get('pushSettingsBtn').hidden, false);
  assert.equal(ui.byId.get('pushSettings').hidden, true);
  assert.equal(ui.window.omniPush.state(), 'on');
});

test('a switch flipped in Settings is saved, and the bell rebuilds its list next time', async () => {
  const ui = pushSetup();
  await ui.window.omniPush.refresh();
  await ui.settle();
  const form = ui.byId.get('accountPushSettings');
  const reminders = form.querySelectorAll('input[name="topic"]')[1];
  reminders.checked = false;
  ui.listeners.change({target: {closest: selector => (selector === '#accountPushSettings' ? form : null)}});
  await ui.window.omniPush.saveSettings(form);
  const save = ui.calls.find(call => call[0] === 'PUT');
  assert.equal(save[1], '/notifications/push/settings');
  assert.deepEqual(save[2].topics, {episodes: true, reminders: false});
  assert.equal(form.querySelector('.push-settings__status').textContent, 'Saved.');
});

test('when this device is off, Settings offers to turn it on and hides the switches', async () => {
  const ui = pushSetup({permission: 'default', subscribed: false});
  await ui.window.omniPush.refresh();
  await ui.settle();
  assert.equal(ui.byId.get('accountPush').dataset.state, 'off');
  assert.equal(ui.byId.get('accountPushBtn').textContent, 'Turn on');
  assert.equal(ui.byId.get('accountPushSettings').hidden, true);
  assert.equal(ui.window.omniPush.state(), 'off');
});

test('a browser without push gets a plain explanation in Settings and nothing in the bell', async () => {
  const ui = pushSetup();
  delete ui.window.PushManager;
  await ui.window.omniPush.refresh();
  assert.equal(ui.byId.get('accountPush').hidden, false);
  assert.match(ui.byId.get('accountPushText').textContent, /can’t show notifications/);
  assert.equal(ui.byId.get('accountPushBtn').hidden, true);
  assert.equal(ui.byId.get('pushOptIn').hidden, true);
});

// ------------------------------------------------------------- the episode guide offer

function guideSetup(pushState, turnOnResult = 'on') {
  const byId = new Map();
  const created = [];
  const refreshes = [];
  const document = {
    createElement: tag => { const node = new Element(tag); created.push(node); return node; },
    addEventListener() {},
    getElementById: id => byId.get(id) || null,
    body: new Element('body'),
    activeElement: null,
  };
  // Elements get ids after creation; look them up by that.
  document.getElementById = id => created.find(node => node.id === id) || null;
  const omniPush = {
    state: () => pushState,
    refresh: async () => { refreshes.push(1); pushState = 'off'; },
    turnOn: async () => { pushState = turnOnResult; return turnOnResult; },
  };
  const window = {addEventListener() {}, setTimeout: () => 1, clearTimeout() {}, omniPush};
  const context = vm.createContext({Promise, console, document, window, setTimeout, Number, String, Array});
  vm.runInContext(episodesScript, context);
  const payload = {category: 'tv-shows', item_id: 7, title: 'Severance', revision: 3, layout: {seasons: [{number: 1, episodes: 9}, {number: 2, episodes: 10}], source: null},
                   episodes: {total: 19, watched: 13, percent: 68, season_count: 2, current: {season: 2, episode: 4},
                              next: {season: 2, episode: 5}, caught_up: false, revision: 3}, checkpoint: {}};
  context.window.OmniEpisodes.configure({sessionKey: () => 'account',
    request: async () => ({ok: true, status: 200, json: async () => payload})});
  return {api: context.window.OmniEpisodes, document, refreshes, payload, settle: () => new Promise(resolve => setTimeout(resolve, 0))};
}

test('the episode guide offers notifications when this device is off', async () => {
  const ui = guideSetup('off');
  ui.api.open('tv-shows', 7, 'Severance');
  await ui.settle();
  const body = ui.document.getElementById('episodeDialogBody');
  const offer = body.querySelector('.episode-dialog__push');
  assert.ok(offer, 'offer is shown');
  assert.match(offer.textContent, /Get a notification when a new episode is out/);
  assert.match(offer.textContent, /Turn it off any time from the bell/);
});

test('no offer once notifications are on, when they are blocked, or for a finished show', async () => {
  for (const state of ['on', 'blocked', 'unsupported', undefined]) {
    const ui = guideSetup(state);
    ui.api.open('tv-shows', 7, 'Severance');
    await ui.settle();
    assert.equal(ui.document.getElementById('episodeDialogBody').querySelector('.episode-dialog__push'), null, String(state));
  }
  const done = guideSetup('off');
  done.payload.episodes.next = null;
  done.payload.episodes.percent = 100;
  done.api.open('tv-shows', 7, 'Severance');
  await done.settle();
  assert.equal(done.document.getElementById('episodeDialogBody').querySelector('.episode-dialog__push'), null);
});

test('an unknown state is checked once, then the offer appears if the device is off', async () => {
  const ui = guideSetup(null);
  ui.api.open('tv-shows', 7, 'Severance');
  await ui.settle();
  await ui.settle();
  assert.equal(ui.refreshes.length, 1);
  assert.ok(ui.document.getElementById('episodeDialogBody').querySelector('.episode-dialog__push'));
});

test('taking the offer turns this device on and says so', async () => {
  const ui = guideSetup('off');
  ui.api.open('tv-shows', 7, 'Severance');
  await ui.settle();
  const dialog = ui.document.getElementById('episodeDialog');
  const button = ui.document.getElementById('episodeDialogBody').querySelector('.episode-dialog__push-btn');
  const offer = ui.document.getElementById('episodeDialogBody').querySelector('.episode-dialog__push');
  button.closest = selector => (selector === '[data-episode-push]' ? offer : selector === '[data-guide-push]' ? button : null);
  await dialog.listeners.click({target: button});
  await ui.settle();
  assert.equal(offer.textContent, 'Done. New episodes of your shows will show up on this device.');
});
