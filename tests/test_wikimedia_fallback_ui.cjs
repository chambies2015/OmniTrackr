// Wikipedia posters on public pages are Wikimedia thumbnails (app/image_sizes.py). When
// Wikimedia refuses one (it rate-limits thumbnail requests), site.js shows the original.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'static', 'site.js'), 'utf8');
const block = source.slice(source.indexOf('/* Wikipedia posters arrive as Wikimedia thumbnails'));

function image(src, state = {}) {
  return {
    tagName: 'IMG', dataset: {}, complete: false, naturalWidth: 0, currentSrc: '', ...state,
    attrs: { src },
    getAttribute(name) { return this.attrs[name] || null; },
    set src(value) { this.attrs.src = value; },
    get src() { return this.attrs.src; },
  };
}

function page(images) {
  const listeners = {};
  const document = {
    addEventListener(type, fn, capture) { listeners[type] = { fn, capture }; },
    querySelectorAll() { return images.filter(img => img.attrs.src.includes('/thumb/')); },
  };
  vm.runInContext(block, vm.createContext({ document }));
  return listeners;
}

const THUMB = 'https://upload.wikimedia.org/wikipedia/en/thumb/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg/250px-Kiki%27s_Delivery_Service_%28Movie%29.jpg';
const ORIGINAL = 'https://upload.wikimedia.org/wikipedia/en/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg';

test('a thumbnail that fails later is swapped for the original, once', () => {
  const img = image(THUMB);
  const listeners = page([img]);
  assert.equal(listeners.error.capture, true, 'error events do not bubble');
  listeners.error.fn({ target: img });
  assert.equal(img.attrs.src, ORIGINAL);
  img.attrs.src = 'https://upload.wikimedia.org/wikipedia/en/thumb/0/07/X.jpg/250px-X.jpg';
  listeners.error.fn({ target: img });
  assert.notEqual(img.attrs.src, 'https://upload.wikimedia.org/wikipedia/en/0/07/X.jpg', 'never loops');
});

test('a thumbnail that failed before the script ran is fixed straight away', () => {
  const broken = image(THUMB, { complete: true, naturalWidth: 0, currentSrc: THUMB });
  const fine = image(THUMB, { complete: true, naturalWidth: 250, currentSrc: THUMB });
  const waiting = image(THUMB);  // lazy, not loaded yet
  page([broken, fine, waiting]);
  assert.equal(broken.attrs.src, ORIGINAL);
  assert.equal(fine.attrs.src, THUMB);
  assert.equal(waiting.attrs.src, THUMB);
});

test('other images and originals are left alone', () => {
  const other = image('https://image.tmdb.org/t/p/w780/x.jpg');
  const original = image(ORIGINAL);
  const listeners = page([other, original]);
  listeners.error.fn({ target: other });
  listeners.error.fn({ target: original });
  listeners.error.fn({ target: { tagName: 'SCRIPT', dataset: {} } });
  assert.equal(other.attrs.src, 'https://image.tmdb.org/t/p/w780/x.jpg');
  assert.equal(original.attrs.src, ORIGINAL);
});
