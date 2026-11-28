// The installed app, Nov 2026: the phone note on a return visit, the steps for each browser,
// the counters sent to /api/app/event, and the once-a-day "opened from the icon" report.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/pwa.js'), 'utf8');
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const INSTAGRAM = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Instagram 300.0';
const ANDROID_CHROME = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36';
const ANDROID_FIREFOX = 'Mozilla/5.0 (Android 14; Mobile; rv:130.0) Gecko/130.0 Firefox/130.0';
const ANDROID_WEBVIEW = 'Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36';
const MAC_SAFARI_16 = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/16.6 Safari/605.1.15';
const DAY = 24 * 60 * 60 * 1000;
const ROUTES = ['ios_safari', 'ios_other', 'in_app', 'android_other', 'desktop_other'];

function setup({userAgent = IPHONE, phone = true, standalone = false, signedIn = true, storage = new Map(),
                now = Date.UTC(2026, 10, 18, 12), usesApp = [], openDialog = false} = {}) {
  const docListeners = {};
  const winListeners = {};
  const timers = [];
  const sent = [];
  const fetched = [];
  const blocks = ROUTES.map(route => ({
    hidden: route !== 'ios_safari',
    getAttribute: name => (name === 'data-install-steps' ? route : `Title for ${route}`),
  }));
  const pageButton = {hidden: true, getAttribute: () => 'page', closest: sel => (sel === '[data-install-app]' ? pageButton : null)};
  const nodes = {
    installAppBtn: {id: 'installAppBtn', hidden: true},
    installAppCard: {id: 'installAppCard', hidden: true},
    installAppCardTitle: {textContent: ''},
    installAppCardSummary: {textContent: ''},
    installAppSheet: {id: 'installAppSheet', hidden: true},
    installAppSheetSummary: {textContent: ''},
    installAppSheetInstall: {id: 'installAppSheetInstall', textContent: ''},
    installAppSheetDismiss: {id: 'installAppSheetDismiss'},
    installAppDialogTitle: {textContent: ''},
    installAppDialog: {open: false, showModal() { this.open = true; }, close() { this.open = false; }},
  };
  const clock = {now};
  const document = {
    readyState: 'complete',
    visibilityState: 'visible',
    getElementById: id => nodes[id] || null,
    addEventListener: (name, fn) => { docListeners[name] = fn; },
    querySelectorAll: sel => {
      if (sel === '[data-install-steps]') return blocks;
      if (sel === '[data-install-app]') return [pageButton];
      return [];
    },
    querySelector: sel => (openDialog && sel.includes('dialog[open]') ? {} : null),
  };
  const navigator = {
    userAgent, maxTouchPoints: phone ? 5 : 0, standalone: false,
    sendBeacon: (url, blob) => { sent.push(JSON.parse(blob.text)); return true; },
  };
  class FakeBlob { constructor(parts) { this.text = parts.join(''); } }
  const window = {
    isSecureContext: false,
    navigator,
    innerWidth: phone ? 390 : 1280,
    localStorage: {getItem: key => (storage.has(key) ? storage.get(key) : null), setItem: (key, value) => storage.set(key, value)},
    matchMedia: query => ({matches: query.includes('standalone') ? standalone : (query.includes('coarse') ? phone : false)}),
    addEventListener: (name, fn) => { winListeners[name] = fn; },
    location: {href: 'https://omnitrackr.xyz/'},
  };
  class FakeDate extends Date {
    constructor(...args) { super(...(args.length ? args : [clock.now])); }
    static now() { return clock.now; }
  }
  const fetch = url => {
    fetched.push(url);
    return Promise.resolve({ok: true, json: () => Promise.resolve({platforms: usesApp})});
  };
  const context = vm.createContext({
    window, document, navigator, Date: FakeDate, Blob: FakeBlob, fetch, Promise,
    setTimeout: fn => { timers.push(fn); return timers.length; },
    clearTimeout: () => {},
    isAuthenticated: () => signedIn,
    getUser: () => ({id: 9}),
  });
  vm.runInContext(script, context);
  const element = node => ({closest: sel => (sel === `#${node.id}` ? node : (sel === '[data-install-app]' && node === pageButton ? pageButton : null))});
  const click = node => docListeners.click({target: node === pageButton ? pageButton : element(node), preventDefault() {}});
  const runTimers = async () => {
    while (timers.length) await timers.shift()();
    await new Promise(resolve => setImmediate(resolve));
  };
  const nextDay = () => { clock.now += DAY; window.refreshInstallCard(); };
  const installable = (outcome = 'accepted') => {
    const prompt = {prompted: false, preventDefault() {}, prompt() { this.prompted = true; }, userChoice: Promise.resolve({outcome})};
    winListeners.beforeinstallprompt(prompt);
    return prompt;
  };
  const events = () => sent.map(item => item.event);
  return {nodes, blocks, pageButton, clock, storage, window, timers, sent, fetched, events, click, runTimers, nextDay, installable};
}

test('each browser gets the right route', () => {
  assert.equal(setup({userAgent: IPHONE}).window.omniInstall.route(), 'ios_safari');
  assert.equal(setup({userAgent: INSTAGRAM}).window.omniInstall.route(), 'in_app');
  assert.equal(setup({userAgent: ANDROID_FIREFOX}).window.omniInstall.route(), 'android_other');
  assert.equal(setup({userAgent: ANDROID_WEBVIEW}).window.omniInstall.route(), 'in_app');
  // Chrome on Android offers its own dialog when it can install, so no dialog means nothing to offer.
  assert.equal(setup({userAgent: ANDROID_CHROME}).window.omniInstall.route(), '');
  assert.equal(setup({userAgent: MAC_SAFARI_16, phone: false}).window.omniInstall.route(), '');
  assert.equal(setup({userAgent: IPHONE, standalone: true}).window.omniInstall.route(), '');
});

test('phones get the note on the second day, not a card, and only after a pause', async () => {
  const ui = setup();
  ui.window.refreshInstallCard();
  await ui.runTimers();
  assert.equal(ui.nodes.installAppSheet.hidden, true); // first day: never
  ui.nextDay();
  assert.equal(ui.nodes.installAppSheet.hidden, true); // waits for the home screen to settle
  assert.equal(ui.timers.length, 1);
  await ui.runTimers();
  assert.equal(ui.nodes.installAppSheet.hidden, false);
  assert.equal(ui.nodes.installAppCard.hidden, true);
  assert.equal(ui.nodes.installAppSheetInstall.textContent, 'Show me how');
  assert.match(ui.nodes.installAppSheetSummary.textContent, /alerts/);
  assert.ok(ui.events().includes('offer_sheet'));
});

test('the note waits when a dialog is open, and skips members who already opened the app on this kind of phone', async () => {
  const busy = setup({openDialog: true});
  busy.window.refreshInstallCard(); busy.nextDay();
  await busy.runTimers();
  assert.equal(busy.nodes.installAppSheet.hidden, true);

  const storage = new Map();
  const uses = setup({usesApp: ['ios'], storage});
  uses.window.refreshInstallCard(); uses.nextDay();
  await uses.runTimers();
  assert.equal(uses.nodes.installAppSheet.hidden, true);
  assert.deepEqual(uses.fetched, ['/api/app/status']);
  assert.equal(JSON.parse(storage.get('omnitrackr_install_card_9')).installed, true);

  const other = setup({usesApp: ['android']});
  other.window.refreshInstallCard(); other.nextDay();
  await other.runTimers();
  assert.equal(other.nodes.installAppSheet.hidden, false);
});

test('Show me how opens this browser\'s steps; Not now rests the note and counts it', async () => {
  const ui = setup();
  ui.window.refreshInstallCard(); ui.nextDay();
  await ui.runTimers();
  await ui.click(ui.nodes.installAppSheetInstall);
  assert.equal(ui.nodes.installAppDialog.open, true);
  assert.equal(ui.blocks.find(block => !block.hidden).getAttribute('data-install-steps'), 'ios_safari');
  assert.ok(ui.events().includes('install_sheet') && ui.events().includes('steps_ios_safari'));
  assert.equal(ui.nodes.installAppSheet.hidden, true);

  const later = setup();
  later.window.refreshInstallCard(); later.nextDay();
  await later.runTimers();
  await later.click(later.nodes.installAppSheetDismiss);
  assert.ok(later.events().includes('later_sheet'));
  later.clock.now += 10 * DAY; later.window.refreshInstallCard();
  await later.runTimers();
  assert.equal(later.nodes.installAppSheet.hidden, true);
});

test('Android with the browser dialog installs from the note and counts the answer', async () => {
  const ui = setup({userAgent: ANDROID_CHROME});
  const prompt = ui.installable('accepted');
  ui.window.refreshInstallCard(); ui.nextDay();
  await ui.runTimers();
  assert.equal(ui.nodes.installAppSheetInstall.textContent, 'Install app');
  assert.match(ui.nodes.installAppSheetSummary.textContent, /share a link/);
  await ui.click(ui.nodes.installAppSheetInstall);
  assert.equal(prompt.prompted, true);
  assert.ok(ui.events().includes('install_sheet') && ui.events().includes('prompt_accepted'));
  assert.equal(JSON.parse(ui.storage.get('omnitrackr_install_card_9')).installed, true);
});

test('in-app browsers get "open in your browser" steps from the menu but never an offer', async () => {
  const ui = setup({userAgent: INSTAGRAM});
  ui.window.refreshInstallCard(); ui.nextDay(); ui.nextDay();
  await ui.runTimers();
  assert.equal(ui.nodes.installAppSheet.hidden, true);
  assert.equal(ui.nodes.installAppBtn.hidden, false);
  await ui.click(ui.nodes.installAppBtn);
  assert.equal(ui.blocks.find(block => !block.hidden).getAttribute('data-install-steps'), 'in_app');
  assert.equal(ui.nodes.installAppDialogTitle.textContent, 'Title for in_app');
  assert.ok(ui.events().includes('install_menu') && ui.events().includes('steps_in_app'));
});

test('the Get the app page button shows where something can install and counts as the page', async () => {
  const ui = setup({userAgent: ANDROID_FIREFOX, signedIn: false});
  assert.equal(ui.pageButton.hidden, false);
  await ui.click(ui.pageButton);
  assert.ok(ui.events().includes('install_page') && ui.events().includes('steps_android_other'));
  assert.equal(setup({userAgent: ANDROID_CHROME, signedIn: false}).pageButton.hidden, true);
});

test('the installed app reports an open once a day, and once more if a guest signs in', () => {
  const storage = new Map();
  const ui = setup({standalone: true, storage, signedIn: false});
  assert.deepEqual(ui.sent.map(item => [item.event, item.platform, Boolean(item.repeat)]), [['opened', 'ios', false]]);
  ui.window.refreshInstallCard(); // still a guest the same day: nothing more
  assert.equal(ui.sent.length, 1);
  const member = setup({standalone: true, storage, signedIn: true});
  assert.deepEqual(member.sent.map(item => [item.event, Boolean(item.repeat)]), [['opened', true]]);
  member.window.refreshInstallCard();
  assert.equal(member.sent.length, 1);
  member.clock.now += DAY;
  member.window.refreshInstallCard();
  assert.deepEqual(member.sent.map(item => [item.event, Boolean(item.repeat)]), [['opened', true], ['opened', false]]);
});

test('a page outside the app never reports an open', () => {
  const ui = setup({standalone: false});
  ui.window.refreshInstallCard();
  assert.ok(!ui.events().includes('opened'));
});
