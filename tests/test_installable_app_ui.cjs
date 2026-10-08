const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/pwa.js'), 'utf8');

function setup({standalone = false, userAgent = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130', protocol = 'https:', hasSW = true} = {}) {
  const windowListeners = {};
  const registered = [];
  const button = {hidden: true, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }};
  const dialog = {opened: false, showModal() { this.opened = true; }, close() { this.opened = false; }};
  const closeBtn = {listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }};
  const classes = new Set();
  const document = {
    readyState: 'complete',
    documentElement: {classList: {add: c => classes.add(c)}},
    getElementById: id => ({installAppBtn: button, installAppDialog: dialog, installAppDialogClose: closeBtn}[id] || null),
    addEventListener() {},
  };
  const navigator = {userAgent, maxTouchPoints: 0, standalone: false};
  if (hasSW) navigator.serviceWorker = {register: (url, opts) => { registered.push([url, opts]); return Promise.resolve(); }};
  const window = {
    location: {hostname: 'www.omnitrackr.xyz', protocol},
    navigator,
    matchMedia: () => ({matches: standalone}),
    addEventListener: (name, fn) => { windowListeners[name] = fn; },
  };
  vm.runInContext(script, vm.createContext({window, document, navigator}));
  return {window, windowListeners, registered, button, dialog, closeBtn, classes};
}

test('registers the root-scoped worker on load over https', () => {
  const ui = setup();
  ui.windowListeners.load();
  assert.equal(JSON.stringify(ui.registered), JSON.stringify([['/sw.js', {scope: '/'}]]));
});

test('does not register over plain http on a public host', () => {
  const ui = setup({protocol: 'http:'});
  assert.equal(ui.windowListeners.load, undefined);
});

test('install button stays hidden until the browser offers installation, then prompts', async () => {
  const ui = setup();
  assert.equal(ui.button.hidden, true);
  let prompted = false;
  const event = {
    preventDefault() { this.prevented = true; },
    prompt() { prompted = true; },
    userChoice: Promise.resolve({outcome: 'accepted'}),
  };
  ui.windowListeners.beforeinstallprompt(event);
  assert.equal(event.prevented, true);
  assert.equal(ui.button.hidden, false);
  await ui.button.listeners.click();
  assert.equal(prompted, true);
  assert.equal(ui.button.hidden, true);
});

test('an installed app never shows the button', () => {
  const ui = setup({standalone: true});
  ui.windowListeners.beforeinstallprompt({preventDefault() {}});
  assert.equal(ui.button.hidden, true);
  assert.equal(ui.classes.has('is-installed-app'), true);
});

test('iOS Safari shows Add to Home Screen help instead of a prompt', async () => {
  const ui = setup({userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1'});
  assert.equal(ui.button.hidden, false);
  await ui.button.listeners.click();
  assert.equal(ui.dialog.opened, true);
  ui.closeBtn.listeners.click();
  assert.equal(ui.dialog.opened, false);
});

test('appinstalled hides the button', () => {
  const ui = setup();
  ui.windowListeners.beforeinstallprompt({preventDefault() {}});
  ui.windowListeners.appinstalled();
  assert.equal(ui.button.hidden, true);
});
