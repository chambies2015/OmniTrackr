"""The reading layout added to written guides (app/guide_layout.py)."""
import re

from app import guide_layout
from app.html_finish import finish

PAGE = (
    '<html><head><script nonce="abc123" src="/static/x.js"></script></head><body><main>'
    '<article class="trail-guide yl-guide"><header class="hero hero--guide"><a href="/if-you-liked">Back</a>'
    '<h1>If you liked Something</h1><p class="guide-deck">Deck</p>'
    '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated <time datetime="2026-10-16">October 16, 2026</time></p>'
    '<nav class="guide-jump" aria-label="On this page"><a href="#picks">The picks</a><a href="#faq">Questions &amp; answers</a></nav>'
    '</header><div class="guide-intro"><p>' + "word " * 500 + '</p></div>'
    '<section id="picks"><article class="pick"><h3>One</h3></article><article class="pick"><h3>Two</h3></article></section>'
    '<section id="faq"><h2>Questions</h2></section></article></main></body></html>'
)


def test_wraps_body_and_adds_rail():
    html = guide_layout.add_reading_layout(PAGE)
    assert html.count(guide_layout.MARKER) == 1
    # The header stays first and untouched apart from the reading time.
    assert '<article class="trail-guide yl-guide"><header class="hero hero--guide">' in html
    assert '<span class="guide-readtime">· 3 min read</span></p>' in html
    body = html.split('<div class="guide-body">', 1)[1]
    assert body.index('id="picks"') < body.index('<aside class="guide-rail"')
    # Nested picks don't end the article early: the rail comes after the last section.
    assert body.index('id="faq"') < body.index('<aside class="guide-rail"')
    assert html.count("<article") == html.count("</article>")
    assert html.count("<div") == html.count("</div>")
    rail = re.search(r'<aside class="guide-rail".*?</aside>', html).group(0)
    assert '<a href="#picks">The picks</a>' in rail
    assert '<a href="#faq">Questions &amp; answers</a>' in rail
    assert 'Checked <time datetime="2026-10-16">October 16, 2026</time>' in rail
    assert '3 min read' in rail


def test_head_gets_styles_font_and_script_with_the_page_nonce():
    html = guide_layout.add_reading_layout(PAGE)
    head = html.split("</head>", 1)[0]
    assert f"/static/guide-reader.css?v={guide_layout.CSS_VERSION}" in head
    assert f'href="{guide_layout.SERIF_FONT}" as="font"' in head
    assert f'<script src="/static/guide-reader.js?v={guide_layout.JS_VERSION}" nonce="abc123" defer></script>' in head


def test_runs_once_and_leaves_other_pages_alone():
    once = guide_layout.add_reading_layout(PAGE)
    assert guide_layout.add_reading_layout(once) == once
    plain = '<html><head></head><body><main><header class="hero"><h1>Hub</h1></header></main></body></html>'
    assert guide_layout.add_reading_layout(plain) == plain
    unbalanced = PAGE.replace("</article></main>", "</main>")
    assert guide_layout.add_reading_layout(unbalanced) == unbalanced


def test_reading_time_ignores_scripts_and_tags():
    assert guide_layout.reading_minutes("<p>" + "word " * 230 + "</p><script>" + "x " * 5000 + "</script>") == 1
    assert guide_layout.reading_minutes("<p>" + "word " * 231 + "</p>") == 2


def test_finish_applies_layout():
    assert guide_layout.MARKER in finish(PAGE)


def test_live_guides_get_the_layout(client):
    for path in ("/if-you-liked/interstellar", "/in-order/star-wars", "/best-of/2026/movies",
                 "/new-releases/november-2026", "/holidays/gifts", "/holidays/black-friday",
                 "/discover/monthly/november-2026"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.text
        assert guide_layout.MARKER in html, path
        assert 'class="guide-readtime"' in html, path
        assert '<nav class="guide-toc" aria-label="Contents">' in html, path
        nonce = re.search(r"'nonce-([^']+)'", response.headers["content-security-policy"]).group(1)
        assert f'guide-reader.js?v={guide_layout.JS_VERSION}" nonce="{nonce}"' in html, path


def test_monthly_edition_has_a_byline_and_contents(client):
    html = client.get("/discover/monthly/november-2026").text
    assert '<article class="trail-guide trail-edition">' in html
    assert '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated <time datetime="2026-11-04">' in html
    for target in ("essay", "start-here", "picks", "take-away", "save-picks"):
        assert f'<a href="#{target}">' in html
        assert f'id="{target}"' in html


def test_browse_shelf_has_a_byline(client):
    html = client.get("/browse/manga").text
    assert '<p class="browse-byline">By <a href="/about">OmniTrackr</a>' in html
    assert 'id="method"' in html


def test_reader_assets_are_served(client):
    for path in ("/static/guide-reader.css", "/static/guide-reader.js", guide_layout.SERIF_FONT,
                 "/static/fonts/source-serif-4-latin-var-italic.woff2"):
        assert client.get(path).status_code == 200, path
