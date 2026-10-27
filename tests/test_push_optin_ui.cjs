const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/push.js'), 'utf8');
const worker = fs.readFileSync(path.join(__dirname, '../app/static/sw.js'), 'utf8');
const KEY = 'BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4';
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130 Safari/537.36';

function keyBytes(value) {
  return new Uint8Array(Buffer.from(value.replace(/-/g, '+').replace(/_/g, '/'), 'base64'));
}

function setup({permission = 'default', grant = 'granted', subscribed = false, push = true, userAgent = DESKTOP,
                signedIn = true, standalone = false, removeFails = false} = {}) {
  const docListeners = {};
  const winListeners = {};
  const calls = [];
  const box = {hidden: true, dataset: {}};
  const text = {textContent: ''};
  const button = {id: 'pushOptInBtn', hidden: false, disabled: false, textContent: ''};
  const bell = {id: 'notificationBell'};
  const more = {id: 'pushSettingsBtn', hidden: true, textContent: '', setAttribute() {}};
  const dialog = {opened: false, showModal() { this.opened = true; }};
  let subscription = null;
  const makeSubscription = key => ({
    endpoint: 'https://fcm.googleapis.com/fcm/send/device-1',
    options: {applicationServerKey: key.buffer},
    unsubscribed: false,
    toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'p', auth: 'a'}}; },
    async unsubscribe() { this.unsubscribed = true; subscription = null; return true; },
  });
  if (subscribed) subscription = makeSubscription(keyBytes(KEY));
  const pushManager = {
    async getSubscription() { return subscription; },
    async subscribe(options) { calls.push(['subscribe', options.userVisibleOnly]); subscription = makeSubscription(options.applicationServerKey); return subscription; },
  };
  const Notification = {
    permission,
    async requestPermission() { calls.push(['permission']); Notification.permission = grant; return grant; },
  };
  const navigator = {userAgent, maxTouchPoints: 0, serviceWorker: {ready: Promise.resolve({pushManager})}};
  const window = {
    isSecureContext: true,
    navigator,
    atob: value => Buffer.from(value, 'base64').toString('binary'),
    matchMedia: () => ({matches: standalone}),
    addEventListener: (name, fn) => { winListeners[name] = fn; },
  };
  if (push) window.PushManager = function PushManager() {};
  if (push) window.Notification = Notification;
  const document = {
    readyState: 'loading',
    getElementById: id => ({pushOptIn: box, pushOptInText: text, pushOptInBtn: button, pushSettingsBtn: more, installAppDialog: dialog}[id] || null),
    addEventListener: (name, fn) => { docListeners[name] = fn; },
  };
  const authenticatedFetch = async (url, options = {}) => {
    calls.push([options.method || 'GET', url, options.body ? JSON.parse(options.body) : undefined]);
    if (removeFails && url.endsWith('/remove')) throw new TypeError('Failed to fetch');
    return {ok: true, async json() { return url.endsWith('/key') ? {public_key: KEY, devices: 0} : {enabled: true}; }};
  };
  const context = vm.createContext({
    window, document, navigator, Notification, authenticatedFetch, setTimeout, clearTimeout, Promise, Uint8Array, Intl,
    isAuthenticated: () => signedIn, API_BASE: '',
  });
  vm.runInContext(script, context);
  const element = el => ({closest: sel => (sel === `#${el.id}` ? el : null)});
  const click = target => docListeners.click({target: element(target), preventDefault() {}, stopPropagation() {}});
  return {box, text, button, more, bell, dialog, calls, click, winListeners, window, current: () => subscription};
}

test('the bell offers to turn notifications on, then subscribes and tells the server', async () => {
  const ui = setup();
  await ui.window.omniPush.refresh();
  assert.equal(ui.box.hidden, false);
  assert.equal(ui.button.textContent, 'Turn on');
  await ui.click(ui.button);
  assert.deepEqual(ui.calls.map(call => call[0]), ['permission', 'GET', 'subscribe', 'POST']);
  assert.equal(ui.calls[2][1], true);
  assert.equal(ui.calls[3][1], '/notifications/push/subscription');
  assert.equal(ui.calls[3][2].endpoint, 'https://fcm.googleapis.com/fcm/send/device-1');
  // Sent along so quiet hours follow this device's clock.
  assert.equal(ui.calls[3][2].time_zone, Intl.DateTimeFormat().resolvedOptions().timeZone);
  assert.equal(ui.box.dataset.state, 'on');
  assert.equal(ui.button.textContent, 'Turn off');
  assert.equal(ui.more.hidden, false);  // "Choose what to get" shows once it's on.
});

test('turning off removes the device on the server and in the browser', async () => {
  const ui = setup({permission: 'granted', subscribed: true});
  await ui.window.omniPush.refresh();
  assert.equal(ui.text.textContent, 'Notifications are on for this device.');
  await ui.click(ui.button);
  assert.deepEqual(ui.calls.at(-1).slice(0, 2), ['POST', '/notifications/push/subscription/remove']);
  assert.equal(ui.current(), null);
  assert.equal(ui.button.textContent, 'Turn on');
});

test('turning off while offline still turns this device off', async () => {
  const ui = setup({permission: 'granted', subscribed: true, removeFails: true});
  await ui.window.omniPush.refresh();
  await ui.click(ui.button);
  assert.equal(ui.current(), null);
  assert.equal(ui.box.dataset.state, 'off');
  assert.equal(ui.button.textContent, 'Turn on');
});

test('a declined or blocked permission subscribes nothing', async () => {
  const declined = setup({grant: 'denied'});
  await declined.window.omniPush.refresh();
  await declined.click(declined.button);
  assert.equal(declined.calls.some(call => call[0] === 'subscribe'), false);
  assert.equal(declined.box.dataset.state, 'blocked');
  assert.equal(declined.button.hidden, true);

  const blocked = setup({permission: 'denied'});
  await blocked.window.omniPush.refresh();
  assert.match(blocked.text.textContent, /blocked/);
});

test('iPhone Safari outside the installed app is pointed to Add to Home Screen', async () => {
  const ui = setup({push: false, userAgent: IPHONE});
  await ui.window.omniPush.refresh();
  assert.equal(ui.box.dataset.state, 'install');
  await ui.click(ui.button);
  assert.equal(ui.dialog.opened, true);
  assert.equal(ui.calls.length, 0);
});

test('browsers without push and signed-out visitors see nothing', async () => {
  for (const options of [{push: false}, {signedIn: false}]) {
    const ui = setup(options);
    await ui.window.omniPush.refresh();
    assert.equal(ui.box.hidden, true);
  }
});

test('a returning device re-sends its subscription so it follows whoever is signed in', async () => {
  const ui = setup({permission: 'granted', subscribed: true});
  await ui.winListeners.load();
  assert.deepEqual(ui.calls.map(call => call.slice(0, 2)), [['GET', '/notifications/push/key'], ['POST', '/notifications/push/subscription']]);
});

test('signing out forgets this device', async () => {
  const ui = setup({permission: 'granted', subscribed: true});
  await ui.window.omniPush.forgetDevice();
  assert.deepEqual(ui.calls.at(-1).slice(0, 2), ['POST', '/notifications/push/subscription/remove']);
  assert.equal(ui.current(), null);
});

function workerSetup() {
  const listeners = {};
  const shown = [];
  const opened = [];
  const self = {
    location: {origin: 'https://omnitrackr.xyz'},
    addEventListener: (name, fn) => { listeners[name] = fn; },
    registration: {showNotification: async (title, options) => shown.push({title, options})},
    clients: {matchAll: async () => [], openWindow: async url => opened.push(url), claim: async () => {}},
  };
  vm.runInContext(worker, vm.createContext({self, caches: {}, URL, fetch: () => {}}));
  const dispatch = async (name, event) => {
    let pending;
    listeners[name]({...event, waitUntil: promise => { pending = promise; }});
    await pending;
  };
  return {dispatch, shown, opened};
}

test('the service worker shows pushed notifications and opens their page on tap', async () => {
  const sw = workerSetup();
  const data = {title: 'Out today', body: 'Out today: Dune', url: '/release-radar/movies#item-dune'};
  await sw.dispatch('push', {data: {json: () => data}});
  assert.equal(sw.shown[0].title, 'Out today');
  assert.equal(sw.shown[0].options.body, 'Out today: Dune');
  let closed = false;
  await sw.dispatch('notificationclick', {notification: {data: sw.shown[0].options.data, close() { closed = true; }}});
  assert.equal(closed, true);
  assert.deepEqual(sw.opened, ['https://omnitrackr.xyz/release-radar/movies#item-dune']);
});

test('the service worker never opens another site from a push', async () => {
  const sw = workerSetup();
  await sw.dispatch('push', {data: {json: () => ({body: 'hi', url: '//evil.example/x'})}});
  assert.equal(sw.shown[0].title, 'OmniTrackr');
  assert.equal(sw.shown[0].options.data.url, '/');
});
