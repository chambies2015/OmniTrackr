// The dashboard script in its original single-file order: the eager modules
// listed in app/dashboard_assets.py with each `// @lazy-chunk` line replaced
// by that lazy file. Tests slice functions out of this text.
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', 'app');
const dashboardDir = path.join(root, 'static', 'dashboard');
const assets = fs.readFileSync(path.join(root, 'dashboard_assets.py'), 'utf8');
const modules = [...assets.match(/EAGER_MODULES = \(([^)]*)\)/)[1].matchAll(/"([\w.-]+)"/g)].map(match => match[1]);

module.exports = modules
  .map(name => fs.readFileSync(path.join(dashboardDir, name), 'utf8'))
  .join('')
  .replace(/^\/\/ @lazy-chunk lazy\/([\w.-]+)\r?\n/gm, (_, file) => fs.readFileSync(path.join(dashboardDir, 'lazy', file), 'utf8'));
