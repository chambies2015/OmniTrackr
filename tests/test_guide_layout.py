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


def _with_picks(*arts: str, saves: bool = False, header_class: str = "hero hero--guide") -> str:
    picks = "".join(
        f'<article class="pick yl-pick"><div class="yl-pick__head">{art}<div><h3>Pick {n}</h3></div></div>'
        + ('<button type="button" class="button yl-save" data-guest-kind="movie" data-guest-slug="x">Save</button>' if saves else "")
        + '</article>' for n, art in enumerate(arts))
    return PAGE.replace('<header class="hero hero--guide">', f'<header class="{header_class}">').replace(
        '<section id="picks"><article class="pick"><h3>One</h3></article><article class="pick"><h3>Two</h3></article></section>',
        f'<section id="picks">{picks}</section>')


def _img(name: str) -> str:
    return f'<img class="yl-pick__art" src="https://image.tmdb.org/t/p/w185/{name}.jpg" alt="" width="96" height="144" loading="lazy">'


def test_cover_fan_uses_the_first_three_pick_covers():
    html = guide_layout.add_reading_layout(_with_picks(_img("a"), _img("b"), _img("a"), _img("c"), _img("d")))
    header = html.split("</header>", 1)[0]
    fan = re.search(r'<div class="guide-fan" aria-hidden="true">.*?</div>', header).group(0)
    # In page order, a repeated cover counted once, and lazy so a phone (where it is hidden) never loads them.
    assert re.findall(r'w185/(\w)\.jpg', fan) == ["a", "b", "c"]
    assert fan.count('loading="lazy"') == 3 and 'alt=""' in fan
    assert 'guide-fan__card--1' in fan and 'guide-fan__card--3' in fan


def test_cover_fan_needs_three_covers_and_skips_seasonal_headers():
    assert "guide-fan" not in guide_layout.add_reading_layout(_with_picks(_img("a"), _img("b")))
    seasonal = _with_picks(_img("a"), _img("b"), _img("c"), header_class="hero hero--guide sn-hero")
    assert "guide-fan" not in guide_layout.add_reading_layout(seasonal)
    # Covers on cards that point at other guides don't count.
    other = '<img class="io-card__art" src="https://image.tmdb.org/t/p/w185/z.jpg" alt="">'
    assert "guide-fan" not in guide_layout.add_reading_layout(_with_picks(_img("a"), _img("b"), other))


def test_cover_fan_copies_drawn_covers_whole():
    drawn = ('<span class="x-art" data-kind="anime" aria-hidden="true"><span class="x-cover"><span class="x-cover__kind">Anime</span>'
             '<b>{}</b></span></span>')
    html = guide_layout.add_reading_layout(_with_picks(drawn.format("Kiki"), drawn.format("Mushishi"), drawn.format("Ping Pong")))
    fan = html.split("</header>", 1)[0].split('<div class="guide-fan"', 1)[1]
    assert fan.count('<span class="x-art"') == 3 and "<b>Ping Pong</b></span></span></span>" in fan
    assert html.count("<span") == html.count("</span>")


def test_keep_a_list_note_only_where_visitors_can_save():
    with_saves = guide_layout.add_reading_layout(_with_picks(_img("a"), saves=True))
    rail = re.search(r'<aside class="guide-rail".*?</aside>', with_saves).group(0)
    assert '<div class="guide-rail__keep" data-guest-only>' in rail
    assert '<a class="guide-rail__join" href="/#signup" data-guide-signup>Start a free library</a>' in rail
    assert "guide-rail__keep" not in guide_layout.add_reading_layout(_with_picks(_img("a")))


def test_drawn_cover_for_picks_without_art():
    art = guide_layout.drawn_cover("yl-pick", "Apollo: Atmospheres & Soundtracks", "album")
    assert art.startswith('<span class="yl-pick__art guide-drawn guide-drawn--long" data-kind="album" aria-hidden="true">')
    assert "<small>Album</small><b>Apollo: Atmospheres &amp; Soundtracks</b>" in art
    assert 'guide-drawn--' not in guide_layout.drawn_cover("io-entry", "Alien", "movie")


def test_live_guides_draw_a_cover_when_a_pick_has_no_art(client):
    html = client.get("/if-you-liked/interstellar").text
    assert 'class="yl-pick__art guide-drawn' in html
    html = client.get("/in-order/alien").text
    assert 'class="io-entry__art guide-drawn' in html and "io-entry__initial" not in html


def test_guides_for_title_matches_format_and_year():
    from app import guide_links
    hrefs = [entry["href"] for entry in guide_links.guides_for_title("movie", "Arrival", 2016)]
    assert "/if-you-liked/interstellar" in hrefs
    # Same name, other format or a remake decades apart: not the same title.
    assert "/if-you-liked/interstellar" not in [e["href"] for e in guide_links.guides_for_title("book", "Arrival", 2016)]
    assert "/if-you-liked/interstellar" not in [e["href"] for e in guide_links.guides_for_title("movie", "Arrival", 1970)]
    assert guide_links.guides_for_title("movie", "Arrival", 2016, skip={"/if-you-liked/interstellar"}) == [
        e for e in guide_links.guides_for_title("movie", "Arrival", 2016) if e["href"] != "/if-you-liked/interstellar"]
    # Albums are "album" on title pages and "music" in the guides.
    assert any(e["section"] == "essentials" for e in guide_links.guides_for_title("album", "Rumours", 1977))
    assert guide_links.guides_for_title("movie", "", None) == []
