const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../app/static/pwa.js'), 'utf8');
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const IPAD = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15';
const CHROME_IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) CriOS/130.0 Mobile/15E148 Safari/604.1';
const DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130 Safari/537.36';

function setup({userAgent, touch = 0, standalone = false}) {
  const docListeners = {};
  const winListeners = {};
  const button = {id: 'installAppBtn', hidden: true};
  const close = {id: 'installAppDialogClose'};
  const dialog = {opened: false, showModal() { this.opened = true; }, close() { this.opened = false; }};
  const element = el => ({closest: sel => (sel === `#${el.id}` ? el : null)});
  const document = {
    readyState: 'complete',
    getElementById: id => ({installAppBtn: button, installAppDialog: dialog, installAppDialogClose: close}[id] || null),
    addEventListener: (name, fn) => { docListeners[name] = fn; },
  };
  const navigator = {userAgent, maxTouchPoints: touch, standalone: false};
  const window = {
    isSecureContext: false,
    navigator,
    matchMedia: () => ({matches: standalone}),
    addEventListener: (name, fn) => { winListeners[name] = fn; },
  };
  vm.runInContext(script, vm.createContext({window, document, navigator}));
  const click = target => docListeners.click({target: element(target), preventDefault() {}});
  return {button, close, dialog, click, winListeners};
}

test('iPhone Safari shows the button and opens Add to Home Screen steps', async () => {
  const ui = setup({userAgent: IPHONE});
  assert.equal(ui.button.hidden, false);
  await ui.click(ui.button);
  assert.equal(ui.dialog.opened, true);
  await ui.click(ui.close);
  assert.equal(ui.dialog.opened, false);
});

test('iPadOS Safari, which reports a Mac user agent, is recognised by touch support', () => {
  assert.equal(setup({userAgent: IPAD, touch: 5}).button.hidden, false);
  assert.equal(setup({userAgent: IPAD, touch: 0}).button.hidden, true);
});

test('other iOS browsers, desktop browsers and installed apps get no iOS help', async () => {
  for (const options of [{userAgent: CHROME_IOS}, {userAgent: DESKTOP}, {userAgent: IPHONE, standalone: true}]) {
    const ui = setup(options);
    assert.equal(ui.button.hidden, true);
    await ui.click(ui.button);
    assert.equal(ui.dialog.opened, false);
  }
});

test('browsers with a native install prompt still use it', async () => {
  const ui = setup({userAgent: DESKTOP});
  let prompted = false;
  ui.winListeners.beforeinstallprompt({preventDefault() {}, prompt() { prompted = true; }, userChoice: Promise.resolve({})});
  assert.equal(ui.button.hidden, false);
  await ui.click(ui.button);
  assert.equal(prompted, true);
  assert.equal(ui.dialog.opened, false);
});
