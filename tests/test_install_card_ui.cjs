const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/pwa.js'), 'utf8');
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130 Safari/537.36';
const DAY = 24 * 60 * 60 * 1000;

function setup({userAgent = DESKTOP, standalone = false, signedIn = true, storage = new Map(), now = Date.UTC(2026, 9, 1, 12)} = {}) {
  const docListeners = {};
  const winListeners = {};
  const nodes = {
    installAppBtn: {id: 'installAppBtn', hidden: true},
    installAppCard: {id: 'installAppCard', hidden: true},
    installAppCardTitle: {textContent: ''},
    installAppCardSummary: {textContent: ''},
    installAppCardInstall: {id: 'installAppCardInstall'},
    installAppCardDismiss: {id: 'installAppCardDismiss'},
    installAppDialog: {opened: false, showModal() { this.opened = true; }, close() { this.opened = false; }},
  };
  const events = [];
  const badges = [];
  const clock = {now};
  const document = {
    readyState: 'complete',
    getElementById: id => nodes[id] || null,
    addEventListener: (name, fn) => { docListeners[name] = fn; },
  };
  const navigator = {
    userAgent, maxTouchPoints: 0, standalone: false,
    setAppBadge: value => { badges.push(value); return Promise.resolve(); },
    clearAppBadge: () => { badges.push(0); return Promise.resolve(); },
  };
  const window = {
    isSecureContext: false,
    navigator,
    localStorage: {getItem: key => (storage.has(key) ? storage.get(key) : null), setItem: (key, value) => storage.set(key, value)},
    matchMedia: query => ({matches: query.includes('standalone') ? standalone : false}),
    addEventListener: (name, fn) => { winListeners[name] = fn; },
    gtag: (kind, name) => events.push(name),
  };
  class FakeDate extends Date {
    constructor(...args) { super(...(args.length ? args : [clock.now])); }
    static now() { return clock.now; }
  }
  const context = vm.createContext({
    window, document, navigator, Date: FakeDate,
    isAuthenticated: () => signedIn,
    getUser: () => ({id: 7}),
  });
  vm.runInContext(script, context);
  const element = node => ({closest: sel => (sel === `#${node.id}` ? node : null)});
  const click = node => docListeners.click({target: element(node), preventDefault() {}});
  const nextDay = () => { clock.now += DAY; window.refreshInstallCard(); };
  const installable = (outcome = 'accepted') => {
    const prompt = {prompted: false, preventDefault() {}, prompt() { this.prompted = true; }, userChoice: Promise.resolve({outcome})};
    winListeners.beforeinstallprompt(prompt);
    return prompt;
  };
  return {nodes, events, badges, clock, storage, window, winListeners, click, nextDay, installable};
}

test('card waits for a third day of visits, never the first', () => {
  const ui = setup();
  ui.installable();
  ui.window.refreshInstallCard();
  ui.window.refreshInstallCard(); // same day twice counts once
  assert.equal(ui.nodes.installAppCard.hidden, true);
  ui.nextDay();
  assert.equal(ui.nodes.installAppCard.hidden, true);
  ui.nextDay();
  assert.equal(ui.nodes.installAppCard.hidden, false);
  assert.match(ui.nodes.installAppCardTitle.textContent, /own window/);
  assert.ok(ui.events.includes('install_card_shown'));
});

test('card appears when the browser reports installability after the dashboard drew', () => {
  const ui = setup();
  ui.window.refreshInstallCard();
  ui.nextDay();
  ui.nextDay();
  assert.equal(ui.nodes.installAppCard.hidden, true); // nothing to install with yet
  ui.installable();
  assert.equal(ui.nodes.installAppCard.hidden, false);
});

test('Install opens the browser prompt and an accepted install retires the card', async () => {
  const ui = setup();
  const prompt = ui.installable('accepted');
  ui.window.refreshInstallCard(); ui.nextDay(); ui.nextDay();
  await ui.click(ui.nodes.installAppCardInstall);
  assert.equal(prompt.prompted, true);
  assert.equal(ui.nodes.installAppCard.hidden, true);
  ui.installable();
  ui.clock.now += 365 * DAY;
  ui.window.refreshInstallCard();
  assert.equal(ui.nodes.installAppCard.hidden, true);
});

test('Not now rests for 30 days, and a second Not now is final', async () => {
  const ui = setup();
  ui.installable();
  ui.window.refreshInstallCard(); ui.nextDay(); ui.nextDay();
  await ui.click(ui.nodes.installAppCardDismiss);
  assert.equal(ui.nodes.installAppCard.hidden, true);
  ui.clock.now += 29 * DAY; ui.window.refreshInstallCard();
  assert.equal(ui.nodes.installAppCard.hidden, true);
  ui.clock.now += 2 * DAY; ui.window.refreshInstallCard();
  assert.equal(ui.nodes.installAppCard.hidden, false);
  await ui.click(ui.nodes.installAppCardDismiss);
  ui.clock.now += 400 * DAY; ui.window.refreshInstallCard();
  assert.equal(ui.nodes.installAppCard.hidden, true);
});

test('iPhone Safari gets the Add to Home Screen steps from the card', async () => {
  const ui = setup({userAgent: IPHONE});
  ui.window.refreshInstallCard(); ui.nextDay(); ui.nextDay();
  assert.equal(ui.nodes.installAppCard.hidden, false);
  assert.match(ui.nodes.installAppCardTitle.textContent, /home screen/);
  await ui.click(ui.nodes.installAppCardInstall);
  assert.equal(ui.nodes.installAppDialog.opened, true);
  assert.equal(ui.nodes.installAppCard.hidden, true);
});

test('no card for guests or inside the installed app, which marks this device as installed', () => {
  const guest = setup({signedIn: false});
  guest.installable();
  guest.window.refreshInstallCard(); guest.nextDay(); guest.nextDay();
  assert.equal(guest.nodes.installAppCard.hidden, true);

  const storage = new Map();
  const app = setup({standalone: true, storage});
  app.window.refreshInstallCard();
  assert.equal(JSON.parse(storage.get('omnitrackr_install_card_7')).installed, true);
});

test('logging out hides the card', () => {
  const ui = setup();
  ui.installable();
  ui.window.refreshInstallCard(); ui.nextDay(); ui.nextDay();
  ui.window.resetInstallCard();
  assert.equal(ui.nodes.installAppCard.hidden, true);
});

test('app icon badge follows the unread count', () => {
  const ui = setup();
  ui.window.setAppIconBadge(4);
  ui.window.setAppIconBadge(0);
  ui.window.setAppIconBadge('nonsense');
  assert.deepEqual(ui.badges, [4, 0, 0]);
});
