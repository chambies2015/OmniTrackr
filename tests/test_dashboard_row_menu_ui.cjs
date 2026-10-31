// Library rows keep Edit visible and move the other actions into a "More" menu.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = require('./helpers/dashboard_source.cjs');
const start = source.indexOf('function groupRowActions(cell) {');
const end = source.indexOf("\n['scroll', 'resize']", start);
assert.ok(start > 0 && end > start);

class El {
  constructor(tag, className = '') { this.tagName = tag.toUpperCase(); this.className = className; this.children = []; this.parent = null; this.attrs = {}; this.listeners = {}; this.textContent = ''; }
  matches(selector) {
    if (selector === 'button.action-btn') return this.tagName === 'BUTTON' && this.className.split(' ').includes('action-btn');
    return false;
  }
  querySelector(selector) {
    const cls = selector.replace('.', '');
    const walk = node => node.children.find(child => child.className.split(' ').includes(cls) || walk(child));
    const found = (function find(node) { for (const child of node.children) { if (child.className.split(' ').includes(cls)) return child; const deep = find(child); if (deep) return deep; } return null; })(this);
    return found;
  }
  appendChild(child) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = this; this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  insertBefore(child, ref) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = this; this.children.splice(this.children.indexOf(ref), 0, child); return child; }
  setAttribute(name, value) { this.attrs[name] = value; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
}

function run(cell) {
  const context = vm.createContext({ document: { createElement: tag => new El(tag) }, window: { innerWidth: 1200, innerHeight: 800 } });
  vm.runInContext(source.slice(start, end), context);
  context.groupRowActions(cell);
}

function row(...classes) {
  const cell = new El('td');
  classes.forEach(cls => cell.appendChild(new El('button', cls)));
  cell.appendChild(new El('button', 'library-card-details'));
  return cell;
}

test('Edit stays visible and every other action moves into the menu', () => {
  const cell = row('action-btn edit-movie-btn', 'action-btn next', 'action-btn collect', 'action-btn delete-movie-btn');
  run(cell);
  const wrapper = cell.children[0];
  assert.equal(wrapper.className, 'row-actions');
  assert.equal(wrapper.children[0].className, 'action-btn edit-movie-btn');
  const menu = wrapper.children[1];
  assert.equal(menu.tagName, 'DETAILS');
  const panel = menu.children[1];
  assert.deepEqual(panel.children.map(button => button.className), ['action-btn next', 'action-btn collect', 'action-btn delete-movie-btn']);
  assert.equal(cell.children[1].className, 'library-card-details', 'mobile detail toggle stays outside the menu');
});

test('grouping is idempotent', () => {
  const cell = row('action-btn edit-tv-btn', 'action-btn delete-tv-btn');
  run(cell);
  run(cell);
  assert.equal(cell.children.filter(child => child.className === 'row-actions').length, 1);
});

test('edit mode rows (Save/Cancel) are left alone', () => {
  const cell = row('action-btn save-movie-btn', 'action-btn cancel-movie-btn');
  run(cell);
  assert.equal(cell.children[0].className, 'action-btn save-movie-btn');
  assert.equal(cell.querySelector('.row-actions'), null);
});
