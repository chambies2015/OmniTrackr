"""Nov 24 2026 sweep of #332 (minified scripts and stylesheets, Brotli) and #333 (sign-up code step after a reload).

Both fixes are in serving minified files:
- The minified copy went out under the file's own ETag, so a browser holding it got "304 not
  modified" even after MINIFY_ASSETS=off, and kept a possibly broken copy for as long as the
  file stayed the same. The kill switch couldn't reach the browsers it was meant to fix.
- "--flag: ;" (a custom property set to a space) was minified to "--flag:;", an empty value
  that older browsers drop.
"""
from pathlib import Path

import pytest

from app import compression, minify
from app.minify import minify_css, minify_js

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
PATH = "/static/episodes.js"


@pytest.fixture
def minifying(monkeypatch):
    monkeypatch.setenv("MINIFY_ASSETS", "on")
    monkeypatch.setenv("BROTLI_ASSETS", "on")


def test_the_minified_copy_has_its_own_etag_and_still_answers_304(client, minifying):
    first = client.get(PATH, headers={"Accept-Encoding": "gzip"})
    assert first.status_code == 200
    assert first.text == minify_js((STATIC / "episodes.js").read_text(encoding="utf-8"))
    etag = first.headers["etag"]
    assert etag.endswith(minify.ETAG_MARK + '"')

    again = client.get(PATH, headers={"Accept-Encoding": "gzip", "If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == etag  # The browser's copy keeps its name.
    assert "Accept-Encoding" in again.headers["vary"]
    weak = client.get(PATH, headers={"Accept-Encoding": "gzip", "If-None-Match": f'"other", W/{etag}'})
    assert weak.status_code == 304


def test_switching_minifying_off_reaches_browsers_that_hold_the_minified_copy(client, minifying, monkeypatch):
    etag = client.get(PATH, headers={"Accept-Encoding": "identity"}).headers["etag"]
    monkeypatch.setenv("MINIFY_ASSETS", "off")
    answer = client.get(PATH, headers={"Accept-Encoding": "identity", "If-None-Match": etag})
    assert answer.status_code == 200
    assert answer.content == (STATIC / "episodes.js").read_bytes()
    assert not answer.headers["etag"].endswith(minify.ETAG_MARK + '"')


def test_a_copy_from_an_older_minifier_is_sent_again(client, minifying):
    plain = client.get(PATH, headers={"Accept-Encoding": "identity"}).headers["etag"].replace(minify.ETAG_MARK, "")
    older = plain[:-1] + '-m00000000"'
    assert client.get(PATH, headers={"If-None-Match": older}).status_code == 200


def test_a_browser_holding_the_file_as_written_keeps_it(client, minifying):
    """Copies fetched before minifying, or while it was off: same program, no need to send it again."""
    plain = client.get(PATH, headers={"Accept-Encoding": "identity"}).headers["etag"].replace(minify.ETAG_MARK, "")
    answer = client.get(PATH, headers={"Accept-Encoding": "gzip", "If-None-Match": plain})
    assert answer.status_code == 304 and answer.headers["etag"] == plain


def test_a_date_alone_cannot_say_which_copy_the_browser_has(client, minifying):
    first = client.get(PATH, headers={"Accept-Encoding": "identity"})
    answer = client.get(PATH, headers={"Accept-Encoding": "identity", "If-Modified-Since": first.headers["last-modified"]})
    assert answer.status_code == 200 and answer.text == first.text


def test_files_that_are_not_minified_keep_their_etag_and_304(client, minifying):
    worker = client.get("/static/sw.js", headers={"Accept-Encoding": "identity"})
    assert worker.status_code == 200 and minify.ETAG_MARK not in worker.headers.get("etag", "")
    icon = client.get("/static/icons/icon-192.png") if (STATIC / "icons" / "icon-192.png").exists() else None
    if icon is not None and icon.status_code == 200:
        assert minify.ETAG_MARK not in icon.headers.get("etag", "")
        assert client.get("/static/icons/icon-192.png", headers={"If-None-Match": icon.headers["etag"]}).status_code == 304


def test_switching_minifying_off_gives_the_dashboard_bundles_new_urls(monkeypatch):
    """/app.js and /dashboard.css are kept a year under ?v=, so no ETag reaches them: their URLs change instead."""
    from app import dashboard_assets

    def versions():
        dashboard_assets.bundle.cache_clear()
        dashboard_assets.stylesheet_bundle.cache_clear()
        return dashboard_assets.bundle()[1], dashboard_assets.stylesheet_bundle()[1]

    try:
        monkeypatch.setenv("MINIFY_ASSETS", "on")
        on = versions()
        monkeypatch.setenv("MINIFY_ASSETS", "off")
        off = versions()
    finally:
        dashboard_assets.bundle.cache_clear()
        dashboard_assets.stylesheet_bundle.cache_clear()
    assert on[0] != off[0] and on[1] != off[1]
    assert all(len(version) == 16 for version in on + off)


def test_minified_etag_is_only_added_once():
    tag = '"abc"'
    assert compression.minified_etag(tag) == f'"abc{minify.ETAG_MARK}"'
    assert compression.minified_etag(compression.minified_etag(tag)) == f'"abc{minify.ETAG_MARK}"'
    assert compression.minified_etag("abc") == "abc"  # Not a quoted tag: left alone.


@pytest.mark.parametrize("source, expected", [
    ("a { --flag: ; }", "a{--flag: ;}"),
    ("a { --flag:  ; color: red }", "a{--flag: ;color: red}"),
    ("a{--flag: }", "a{--flag: }"),
    ("a { color: red ; }", "a{color: red;}"),  # Other declarations still lose the space.
])
def test_a_custom_property_set_to_a_space_keeps_it(source, expected):
    assert minify_css(source) == expected
