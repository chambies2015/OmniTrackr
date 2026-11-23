// The site serves scripts and stylesheets minified (app/minify.py). This checks every one of them
// with esbuild's parser: printing the file on disk and its minified copy must give the same
// output, so they are the same program (or the same rules). Strings, template literals and
// regular expressions are compared character for character by this.
//
// CI installs esbuild for this test (.github/workflows/tests.yml). Locally it is skipped unless
// you run `npm install --no-save --no-package-lock esbuild@0.25.12` in the repository first.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT = path.join(__dirname, '..');

let esbuild = null;
try {
  esbuild = require('esbuild');
} catch (error) {
  esbuild = null;
}

const DUMP = `
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from app import dashboard_assets, minify
root = Path(sys.argv[1])
files = [(str(p.relative_to(root)), p.suffix[1:], p.read_text(encoding="utf-8"))
         for p in sorted((root / "app" / "static").rglob("*")) if p.suffix in (".js", ".css") and p.is_file()]
files.append(("/app.js (dashboard bundle)", "js", dashboard_assets.bundle()[0]))
files.append(("/dashboard.css (stylesheet bundle)", "css", dashboard_assets.stylesheet_bundle()[0]))
out = []
for name, kind, source in files:
    try:
        smaller = minify.minify_text(source, kind)
    except minify.MinifyError:
        smaller = None  # Served as written; tests/test_minify_assets.py reports these.
    out.append([name, kind, source, smaller])
json.dump(out, sys.stdout)
`;

function minifiedFiles() {
  for (const python of ['python3', 'python']) {
    const run = spawnSync(python, ['-c', DUMP, ROOT], { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
    if (run.error && run.error.code === 'ENOENT') continue;
    assert.equal(run.status, 0, run.stderr);
    return JSON.parse(run.stdout);
  }
  return null;
}

function printed(code, loader) {
  return esbuild.transformSync(code, { loader, minifyWhitespace: true, legalComments: 'none', charset: 'utf8' }).code;
}

test('every minified script and stylesheet parses to the same thing as the file on disk', { skip: esbuild ? false : 'esbuild is not installed' }, () => {
  const files = minifiedFiles();
  if (files === null) return; // No Python here.
  assert.ok(files.length > 200, `only ${files.length} files found`);
  const different = [];
  for (const [name, kind, source, smaller] of files) {
    if (smaller === null) continue;
    let expected;
    try {
      expected = printed(source, kind);
    } catch (error) {
      continue; // esbuild can't read the original either; nothing to compare.
    }
    let actual;
    try {
      actual = printed(smaller, kind);
    } catch (error) {
      different.push(`${name}: the minified copy doesn't parse (${error.message.split('\n')[0]})`);
      continue;
    }
    if (actual !== expected) {
      let at = 0;
      while (at < expected.length && expected[at] === actual[at]) at += 1;
      different.push(`${name}: differs near ${JSON.stringify(expected.slice(Math.max(0, at - 60), at + 60))}`);
    }
  }
  assert.deepEqual(different, [], 'app/minify.py changed what these files mean');
});
