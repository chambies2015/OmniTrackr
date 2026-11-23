"""Minified scripts and stylesheets (Nov 23 2026): app/minify.py and the asset path in app/compression.py.

tests/test_minify_equivalence.cjs runs every file through esbuild's parser as well: the
minified copy must parse to the same program as the file on disk.
"""
import gzip
import json
import re
import shutil
import subprocess
from pathlib import Path

import brotli
import pytest

from app import compression, dashboard_assets, minify
from app.minify import MinifyError, minify_css, minify_js

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


@pytest.fixture
def minifying(monkeypatch):
    """conftest.py serves files as written; these tests look at what production serves."""
    monkeypatch.setenv("MINIFY_ASSETS", "on")
    monkeypatch.setenv("BROTLI_ASSETS", "on")


# ---------------------------------------------------------------- scripts

@pytest.mark.parametrize("source, expected", [
    # Text inside template literals, nested ones included, is never touched.
    ("const label = `${item.title}, ${item.year ? ` ${item.year}` : ''}`;",
     "const label=`${item.title}, ${item.year?` ${item.year}`:''}`;"),
    ("const html = `<div class=\"a\">\n    <span>${ name }</span>\n  </div>`;",
     "const html=`<div class=\"a\">\n    <span>${name}</span>\n  </div>`;"),
    ("const t = `${ {a: 1}.a } and ${ `${ x }` }`;", "const t=`${{a:1}.a} and ${`${x}`}`;"),
    ("const q = `a\\`b ${c} $d $`;", "const q=`a\\`b ${c} $d $`;"),
    # Comment markers inside strings stay; real comments go, keeping their line breaks.
    ("const url = 'https://example.com/a'; // it's a comment\nconst b = \"/* not a comment */\";",
     "const url='https://example.com/a';\nconst b=\"/* not a comment */\";"),
    ("/**\n * Docs\n */\nfunction g() {\n\n  return 1;\n}\n", "\n\n\nfunction g(){\n\nreturn 1;\n}\n"),
    # Regular expressions versus division.
    ("function f(a) {\n    return /[/\\]]+/g.test(a) ? a / 2 / 3 : a;\n}",
     "function f(a){\nreturn/[/\\]]+/g.test(a)?a/2/3:a;\n}"),
    ("if (ok) /^x/.test(s) && go();\nconst half = (a + b) / 2;", "if(ok)/^x/.test(s)&&go();\nconst half=(a+b)/2;"),
    ("list.forEach(item => /x/.test(item));\nswitch (k) { case /a/.source: break; }",
     "list.forEach(item=>/x/.test(item));\nswitch(k){case/a/.source:break;}"),
    ("x = typeof /re/; y = void /re/;", "x=typeof/re/;y=void/re/;"),
    ("let n = i++ / 2;", "let n=i++/2;"),
    # Spaces that keep tokens apart.
    ("const y = a + +b - -c;\nx = 1 .toFixed(2);\nhit = /re/ in z;", "const y=a+ +b- -c;\nx=1 .toFixed(2);\nhit=/re/ in z;"),
    ("return value instanceof Map", "return value instanceof Map"),
    # Line breaks stay, so semicolon insertion and line numbers are unchanged.
    ("let total = count\n++other;", "let total=count\n++other;"),
    ("a = b\n(c || d).go();", "a=b\n(c||d).go();"),
])
def test_scripts_lose_comments_and_spaces_but_nothing_else(source, expected):
    assert minify_js(source) == expected


@pytest.mark.parametrize("source", [
    'const s = "open',
    "const t = `x",
    "f(a]",
    "f(a",
    "x = /unterminated\n/",
    "const gap = a\u00a0+ b",  # A no-break space between tokens: served as written.
])
def test_scripts_it_cannot_read_are_refused(source):
    with pytest.raises(MinifyError):
        minify_js(source)


def test_a_refused_file_is_served_as_written_and_remembered():
    body = b'const s = "open'
    assert minify.minified(body, "js") is body
    assert minify.cached(body, "js") == body


# ---------------------------------------------------------------- stylesheets

@pytest.mark.parametrize("source, expected", [
    ("/* head */\n.a  .b ,\n.c > .d {\n  margin : calc(1px + 2px) 0 ;\n  color: red !important;\n}\n",
     ".a .b , .c > .d{margin : calc(1px + 2px) 0;color: red !important;}"),
    # "and (" keeps its space: "and(" would be a function and drop the whole rule.
    ("@media screen and (max-width: 600px) {\n  .x { display: none }\n}",
     "@media screen and (max-width: 600px){.x{display: none}}"),
    # A hex escape eats one following space; the next one is a real combinator.
    (".\\31 23 { width: 1px }\n.a\\:b{x:y}\n.\\31  a{x:y}", ".\\31 23{width: 1px}.a\\:b{x:y}.\\31  a{x:y}"),
    (".q::before { content: \"; { } /* x */\"; background: url(//cdn.example.com/a.png) }",
     ".q::before{content: \"; { } /* x */\";background: url(//cdn.example.com/a.png)}"),
    # A comment that separates two values is kept, or 1px2px would be one value.
    (".v { margin: 1px/**/2px; --gap:  4px   8px; }", ".v{margin: 1px/**/2px;--gap: 4px 8px;}"),
    (":is( .a , .b ) .c{x:y}", ":is( .a , .b ) .c{x:y}"),
])
def test_stylesheets_lose_comments_and_spare_whitespace(source, expected):
    assert minify_css(source) == expected


def test_unterminated_css_string_is_refused():
    with pytest.raises(MinifyError):
        minify_css('.a::before{content:"open}')


# ---------------------------------------------------------------- every file the site serves

def _served_sources():
    for path in sorted(STATIC.rglob("*")):
        if path.suffix in (".js", ".css") and path.is_file():
            yield str(path.relative_to(ROOT)), path.read_text(encoding="utf-8"), path.suffix[1:]
    yield "/app.js (dashboard bundle)", dashboard_assets.bundle()[0], "js"
    yield "/dashboard.css (stylesheet bundle)", dashboard_assets.stylesheet_bundle()[0], "css"


def test_every_script_and_stylesheet_minifies_without_falling_back():
    """A file the minifier can't read is served as written, which is safe but loses the saving.

    If this fails for a file you changed, look at the reason: usually a no-break space or
    another non-ASCII space between two tokens. Replace it with a normal space.
    """
    refused = []
    before = after = 0
    for name, source, kind in _served_sources():
        try:
            smaller = minify.minify_text(source, kind)
        except MinifyError as error:
            refused.append(f"{name}: {error}")
            continue
        before += len(source)
        after += len(smaller)
        if kind == "js":
            assert smaller.count("\n") == source.count("\n"), name  # Line numbers in error reports still match.
    assert not refused, refused
    assert after < before * 0.85


# ---------------------------------------------------------------- serving

def test_scripts_are_served_minified_with_the_right_length(client, minifying):
    script, version = dashboard_assets.bundle()
    response = client.get(f"/app.js?v={version}", headers={"Accept-Encoding": "identity"})
    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert response.text == minify_js(script)
    assert int(response.headers["content-length"]) == len(response.content) < len(script.encode())
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_static_files_keep_their_headers_and_answer_304(client, minifying):
    path = "/static/episodes.js?v=test"
    first = client.get(path, headers={"Accept-Encoding": "gzip"})
    assert first.status_code == 200 and first.headers["content-encoding"] == "gzip"
    assert first.text == minify_js((STATIC / "episodes.js").read_text(encoding="utf-8"))
    assert first.headers["content-type"].startswith("text/javascript")
    assert "etag" in first.headers and "accept-ranges" not in first.headers
    assert first.headers["x-content-type-options"] == "nosniff"
    again = client.get(path, headers={"Accept-Encoding": "gzip", "If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b""


def test_a_range_request_gets_the_whole_minified_file(client, minifying):
    response = client.get("/static/episodes.js", headers={"Accept-Encoding": "identity", "Range": "bytes=0-9"})
    assert response.status_code == 200
    assert response.text == minify_js((STATIC / "episodes.js").read_text(encoding="utf-8"))


def test_stylesheets_are_served_minified(client, minifying):
    css, version, _ = dashboard_assets.stylesheet_bundle()
    response = client.get(f"/dashboard.css?v={version}", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/css")
    assert response.text == minify_css(css)
    assert len(response.text) < len(css) * 0.9
    site = client.get("/static/site.css", headers={"Accept-Encoding": "identity"})
    assert site.text == minify_css((STATIC / "site.css").read_text(encoding="utf-8"))


def test_the_service_worker_and_other_files_stay_as_written(client, minifying):
    worker = client.get("/sw.js", headers={"Accept-Encoding": "identity"})
    assert worker.status_code == 200
    assert worker.content == (STATIC / "sw.js").read_bytes()
    assert client.get("/credentials.js").text.startswith("// API Keys are now proxied")
    manifest = client.get("/manifest.webmanifest", headers={"Accept-Encoding": "identity"})
    if manifest.status_code == 200:
        json.loads(manifest.text)
    font = client.get("/static/fonts/inter-var-latin.woff2", headers={"Accept-Encoding": "gzip, br"})
    assert font.status_code == 200 and "content-encoding" not in font.headers


def test_minifying_can_be_switched_off(client, monkeypatch):
    monkeypatch.setenv("MINIFY_ASSETS", "off")
    response = client.get("/static/episodes.js", headers={"Accept-Encoding": "identity"})
    assert response.content == (STATIC / "episodes.js").read_bytes()
    partial = client.get("/static/episodes.js", headers={"Accept-Encoding": "identity", "Range": "bytes=0-9"})
    assert partial.status_code == 206 and len(partial.content) == 10


def test_brotli_is_made_in_the_background_then_served(client, minifying):
    compression.brotli_copies.clear()
    path = "/static/rankings.js?v=test"
    expected = minify_js((STATIC / "rankings.js").read_text(encoding="utf-8")).encode()
    headers = {"Accept-Encoding": "gzip, deflate, br"}
    first = client.get(path, headers=headers)
    assert first.headers["content-encoding"] == "gzip"  # No waiting on level 11 for the first visitor.
    compression.wait_for_brotli()
    second = client.get(path, headers=headers)
    assert second.headers["content-encoding"] == "br"
    assert "Accept-Encoding" in second.headers["vary"]
    assert second.content == expected  # The client decodes it.
    stored = compression.brotli_copies.get(compression.CompressedCopies.key(expected))
    assert brotli.decompress(stored) == expected
    assert int(second.headers["content-length"]) == len(stored) < len(gzip.compress(expected, 9))


def test_brotli_can_be_switched_off_and_respects_q_zero(client, minifying, monkeypatch):
    path = "/static/streaming.js?v=test"
    client.get(path, headers={"Accept-Encoding": "br"})
    compression.wait_for_brotli()
    assert client.get(path, headers={"Accept-Encoding": "gzip, br;q=0"}).headers["content-encoding"] == "gzip"
    monkeypatch.setenv("BROTLI_ASSETS", "off")
    assert client.get(path, headers={"Accept-Encoding": "gzip, br"}).headers["content-encoding"] == "gzip"
    assert compression.accepted_encodings("gzip, deflate, br, zstd") == {"gzip", "deflate", "br", "zstd"}
    assert compression.accepted_encodings("br;q=0, gzip;q=0.5") == {"gzip"}


def test_pages_are_not_minified(client, minifying):
    page = client.get("/about", headers={"Accept-Encoding": "gzip, br"})
    assert page.status_code == 200 and page.headers["content-encoding"] == "gzip"
    assert "<html" in page.text


# ---------------------------------------------------------------- the signed-in app still loads

def _page_assets(html: str) -> tuple[list[str], list[str]]:
    scripts = re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    styles = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
    local = lambda url: url.startswith(("/", "./")) and not url.startswith("//")  # noqa: E731
    served = lambda url: "/" + url[2:] if url.startswith("./") else url  # noqa: E731
    return [served(u) for u in scripts if local(u)], [served(u) for u in styles if local(u)]


def test_signed_in_app_scripts_and_styles_all_load_minified(authenticated_client, minifying, tmp_path):
    """Every script and stylesheet the dashboard links, plus its lazy chunks, served minified."""
    html = authenticated_client.get("/").text
    scripts, styles = _page_assets(html)
    assert "/dashboard.css?v=" + dashboard_assets.stylesheet_bundle()[1] in styles
    assert any(src.startswith("/app.js?v=") for src in scripts)
    assert "/preauth.js?v=20261120-settle-1" in scripts
    _, version = dashboard_assets.bundle()
    scripts += [f"/static/dashboard/lazy/{name}?v={version}"
                for files in dashboard_assets.LAZY_CHUNKS.values() for name in files]
    assert len(scripts) > 60

    written = []
    for url in scripts + styles:
        response = authenticated_client.get(url, headers={"Accept-Encoding": "gzip, br"})
        assert response.status_code == 200, url
        kind = "css" if url in styles else "js"
        expected_type = "text/css" if kind == "css" else "javascript"
        assert expected_type in response.headers["content-type"], url
        if kind == "js":
            target = tmp_path / f"{len(written)}.js"
            target.write_text(response.text, encoding="utf-8")
            written.append((url, str(target)))
        else:
            assert response.text.count("{") == response.text.count("}"), url

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed, so the served scripts can't be compiled here")
    # Compile each served script the way a browser would (a classic script), without running it.
    check = (
        "const fs=require('fs'),vm=require('vm');const bad=[];"
        "for(const [url,file] of JSON.parse(process.argv[1])){"
        "try{new vm.Script(fs.readFileSync(file,'utf8'),{filename:url})}catch(e){bad.push(url+': '+e.message)}}"
        "if(bad.length){console.log(bad.join('\\n'));process.exit(1)}"
    )
    result = subprocess.run([node, "-e", check, json.dumps(written)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
