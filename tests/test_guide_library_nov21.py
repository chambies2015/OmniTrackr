"""The /guides library (app/guide_library.py) and the guide-page trail that leads back to it."""
import json
import re
from html import unescape

import pytest

from app import editorial_index, guide_library, page_breadcrumbs


def _ld(html):
    blocks = []
    for raw in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        data = json.loads(raw)
        for item in data if isinstance(data, list) else [data]:
            blocks.extend(item.get("@graph", [item]))
    return blocks


def _library(html):
    start = html.index('<section class="privacy-section gl-section gl-library"')
    return html[start:html.index("</section>\n", html.index('data-gl-empty', start))]


def _rows(html):
    return re.findall(r'<li class="gl-row" data-formats="([^"]*)" data-name="[^"]*"( hidden)?><a href="([^"]+)">', html)


def test_every_dated_guide_is_listed_once(client):
    html = client.get("/guides").text
    hrefs = [href for _, _, href in _rows(html)]
    for piece in editorial_index.entries():
        assert hrefs.count(piece["href"]) == 1, piece["href"]
    # Switch guides, browse shelves, challenges and the help pages are on the list too.
    for href in ("/switch/letterboxd", "/browse/manga", "/movie-tracker", "/export-import-guide", "/faq"):
        assert href in hrefs, href
    assert len(hrefs) == len(guide_library.rows())
    assert f"Showing all {len(hrefs)} guides." in html


def test_shelves_follow_the_kinds_of_guide(client):
    html = client.get("/guides").text
    library = _library(html)
    for key, heading, _, hubs in guide_library.SHELVES:
        assert f'id="shelf-{key}"' in library, key
        assert re.search(rf'<h3 id="shelf-{key}-title">{re.escape(heading)}', library), key
        assert f'href="{hubs[0][0]}"' in library, key
    # The awards pages get their own shelf instead of sitting with Halloween.
    awards = library[library.index('id="shelf-awards"'):library.index('id="shelf-monthly"')]
    assert 'href="/awards/oscars-2027"' in awards and 'href="/halloween"' not in awards


def test_format_filter_works_without_javascript(client):
    html = client.get("/guides?format=anime").text
    rows = _rows(html)
    shown = [href for formats, hidden, href in rows if not hidden]
    assert all("anime" in formats.split() for formats, hidden, _ in rows if not hidden)
    assert all("anime" not in formats.split() for formats, hidden, _ in rows if hidden)
    assert "/in-order/monogatari" in shown and "/in-order/james-bond" not in shown
    assert f"Showing {len(shown)} of {len(rows)} guides that cover anime." in html
    assert '<a class="gl-chip" href="/guides?format=anime#guide-library-heading" data-format="anime" data-slug="anime" data-plural="anime" aria-current="true">' in html
    # The filtered view is the same page to search engines.
    assert '<link rel="canonical" href="https://omnitrackr.xyz/guides">' in html
    # A shelf with nothing in that format is hidden, not left empty.
    assert re.search(r'<section class="gl-shelf" id="shelf-switch"[^>]*>', client.get("/guides?format=audiobooks").text).group(0).endswith(" hidden>")


@pytest.mark.parametrize("value", ["", "everything", "<script>", "ANIME "])
def test_unknown_or_odd_format_values(client, value):
    html = client.get("/guides", params={"format": value}).text
    assert "<script>" not in _library(html)
    if value.strip().lower() == "anime":
        assert "guides that cover anime" in html
    else:
        assert "Showing all" in html and ' hidden><a href=' not in html


def test_formats_follow_the_titles_each_guide_covers():
    by_href = {row["href"]: row for row in guide_library.rows()}
    assert by_href["/in-order/star-wars"]["formats"] == ("movie", "tv")
    # One tie-in series is not enough to put Fast & Furious under TV.
    assert by_href["/in-order/fast-and-furious"]["formats"] == ("movie",)
    # Guides that mix formats on purpose belong to each of them.
    assert set(by_href["/valentines-day"]["formats"]) == set(guide_library.ALL_KINDS)
    # Book series "how long" guides count the audiobook too; film ones are films.
    assert by_href["/binge-calculator/the-wheel-of-time"]["formats"] == ("book", "audiobook")
    assert by_href["/binge-calculator/star-wars-films"]["formats"] == ("movie",)
    assert by_href["/awards/the-game-awards-2026"]["formats"] == ("game",)
    assert by_href["/awards/grammys-2027"]["main"] == "music"
    # Albums are counted as music.
    assert "music" in by_href["/best-of/2026/music"]["formats"]
    # Setup pages apply to every format, so they don't pad each format's count.
    assert by_href["/faq"]["formats"] == ()


def test_start_here_and_format_desks(client):
    html = client.get("/guides").text
    picks = re.findall(r'<a class="gl-pick" href="([^"]+)">', html)
    assert picks == [href for href, _ in guide_library.START_HERE]
    known = {piece["href"] for piece in editorial_index.entries()}
    assert set(picks) <= known
    desks = re.findall(r'<article class="gl-desk" id="format-([a-z]+)">(.*?)</article>', html, re.S)
    assert [slug for slug, _ in desks] == [row[0] for row in guide_library.FORMATS]
    for slug, body in desks:
        assert len(re.findall(r"<li><a href=", body)) >= 2, slug
        assert f'href="/guides?format={slug}#guide-library-heading"' in body
    films = dict(desks)["films"]
    assert 'href="/essentials/movies"' in films and 'href="/best-of/2026/movies"' in films


def test_header_counts_and_dates_match_the_catalog(client):
    html = client.get("/guides").text
    total = len(editorial_index.entries())
    newest = max(piece["updated"] for piece in editorial_index.entries())
    assert f"<p>{total} guides to films, TV, anime" in html
    assert f"<strong>{total}</strong> dated reading guides" in html
    page = next(block for block in _ld(html) if block.get("@type") == "CollectionPage")
    assert page["dateModified"] == newest
    assert f'Updated <time datetime="{newest}">' in html
    assert "2099-01-01" not in html
    recent = re.search(r'<ol class="gl-recent">(.*?)</ol>', html, re.S).group(1)
    assert len(re.findall(r"<li>", recent)) == 8


def test_how_to_part_keeps_its_anchors_and_follows_the_library(client):
    html = client.get("/guides").text
    assert html.index('id="guide-library-heading"') < html.index('id="choose-path-heading"') < html.index('id="tips-heading"')
    assert 'id="standards-heading"' in html and 'href="/content-quality"' in html
    assert "Drafts are written with the help of AI writing tools" in html


def test_library_assets_are_served_and_styles_inlined(client):
    html = client.get("/guides").text
    assert '<style data-from="guide-library.css"' in html
    assert re.search(r'<script src="/static/guide-library\.js\?v=[\w-]+"[^>]*defer', html)
    assert client.get("/static/guide-library.js").status_code == 200


def test_hub_pages_sit_under_guides_in_the_trail():
    for hub in ("/in-order", "/binge-calculator", "/valentines-day", "/awards", "/essentials"):
        steps = page_breadcrumbs.trail("https://omnitrackr.xyz" + hub, "x")
        assert [name for name, _ in steps][:2] == ["Home", "Guides"], hub
    christmas = page_breadcrumbs.trail("https://omnitrackr.xyz/holidays/christmas", "Christmas 2026 guide")
    assert [name for name, _ in christmas] == ["Home", "Guides", "Holiday picks", "Christmas 2026"]
    # Sections that aren't guides keep their old trail.
    assert [name for name, _ in page_breadcrumbs.trail("https://omnitrackr.xyz/daily/3", "Daily #3")] == ["Home", "OmniTrackr Daily", "Daily #3"]


@pytest.mark.parametrize("path, crumbs, shelf", [
    ("/in-order/star-wars", ["Home", "Guides", "Franchises in order"], "Series in order"),
    ("/binge-calculator/breaking-bad", ["Home", "Guides", "Binge calculator"], "How long it takes"),
    ("/holidays/christmas", ["Home", "Guides", "Holiday picks"], "Holidays and seasons"),
    ("/valentines-day", ["Home", "Guides"], "Holidays and seasons"),
    ("/discover/monthly/november-2026", ["Home", "Guides", "Discover"], "Monthly editions and challenges"),
])
def test_guide_pages_show_the_trail_and_the_library(client, path, crumbs, shelf):
    html = client.get(path).text
    header = re.search(r'<article class="trail-guide[^"]*"[^>]*><header[^>]*>(.*?)</header>', html, re.S).group(1)
    nav = re.search(r'<nav class="guide-crumbs" aria-label="Breadcrumb"><ol>(.*?)</ol></nav>', header).group(1)
    assert [unescape(name) for name in re.findall(r'<a href="[^"]+">([^<]+)</a>', nav)] == crumbs
    assert "←" not in header
    # The visible trail is the structured one minus the page itself.
    data = next(block for block in _ld(html) if block.get("@type") == "BreadcrumbList")
    assert [item["name"] for item in data["itemListElement"]][:-1] == crumbs
    rail = re.search(r'<nav class="guide-rail__library".*?</nav>', html, re.S).group(0)
    assert f">{shelf}</a>" in unescape(rail)
    assert '<a href="/guides">The whole library</a>' in rail


def test_rail_links_to_the_guides_format():
    rail = guide_library.rail_html("/in-order/monogatari")
    assert '<a href="/guides?format=anime#guide-library-heading">Every anime guide</a>' in rail
    assert guide_library.rail_html("/not-a-guide") == ""


def test_trust_pages_and_homepage_point_to_the_library(client):
    assert '<a href="/guides">the guide library</a> lists every guide' in client.get("/about").text
    assert 'href="/guides#guide-library-heading">guide library</a>' in client.get("/content-quality").text
    assert '<a href="/guides">Every guide</a>' in editorial_index.homepage_section()
