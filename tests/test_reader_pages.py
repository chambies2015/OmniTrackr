"""Shared reading layout for guides, help and policy pages (app/reader_pages.py)."""
import json
import re
from pathlib import Path

import pytest

from app import reader_pages

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = sorted((name, page.path) for name, page in reader_pages.PAGES.items())


def _json_ld(html):
    return [json.loads(block) for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


@pytest.mark.parametrize("template, path", PAGES)
def test_every_reader_page_gets_the_shared_layout(client, template, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.text
    assert '<html lang="en" data-reader>' in html
    assert html.count('class="reader-crumbs"') == 1
    assert html.count('id="related-heading"') == 1
    assert 'class="back-link"' not in html
    # Search basics survive the rewrite.
    assert html.count('<link rel="canonical" href="https://omnitrackr.xyz') == 1
    assert re.search(r"<title>[^<]{10,}</title>", html)
    assert re.search(r'<meta name="description" content="[^"]{50,}"', html)
    # Every heading anchor is unique, and every in-page link has a target.
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for anchor in re.findall(r'href="#([^"]+)"', html):
        assert anchor in ids, (path, anchor)


@pytest.mark.parametrize("template, path", PAGES)
def test_breadcrumb_data_matches_the_visible_trail(client, template, path):
    html = client.get(path).text
    trails = [item for item in _json_ld(html) if item.get("@type") == "BreadcrumbList"]
    assert len(trails) == 1
    items = trails[0]["itemListElement"]
    assert items[0]["item"] == "https://omnitrackr.xyz/"
    assert items[-1]["item"] == f"https://omnitrackr.xyz{path}"
    assert [item["position"] for item in items] == list(range(1, len(items) + 1))
    nav = html[html.index('class="reader-crumbs"'):html.index("</nav>", html.index('class="reader-crumbs"'))]
    assert f'<span aria-current="page">{items[-1]["name"]}</span>'.replace("'", "&#x27;") in nav


def test_related_cards_point_at_live_pages(client):
    targets = {p.path for p in reader_pages.PAGES.values()} | {p.path for p in reader_pages.OTHER_PAGES.values()}
    for target in targets:
        assert client.get(target).status_code == 200, target
    for name, page in reader_pages.PAGES.items():
        assert len(page.related) == 3 and name not in page.related, name
        for other in page.related:
            assert other in reader_pages.PAGES or other in reader_pages.OTHER_PAGES, (name, other)


def test_a_page_keeps_its_own_related_paragraph_above_the_cards(client):
    html = client.get("/movie-tracker").text
    block = html[html.index('class="reader-related"'):]
    assert 'class="reader-related__lead"' in block and 'href="/reviews"' in block
    assert block.index("reader-related__lead") < block.index("reader-related__grid")
    assert block.count('class="reader-related__card"') == 3


def test_reading_line_is_drawn_by_the_server(client):
    html = client.get("/movie-tracker").text
    header = html[html.index('<header class="content-header">'):html.index("</header>", html.index('<header class="content-header">'))]
    assert re.search(r'<p class="reader-meta">By OmniTrackr · \d+ min read · Updated <time datetime="2026-06-23">June 23, 2026</time></p>', header)
    # Policy pages keep their own "Last Updated" line and show only the reading time.
    privacy = client.get("/privacy").text
    assert re.search(r'<p class="reader-meta">\d+ min read</p>', privacy)


def test_changelog_date_and_month_index_follow_the_entries(client):
    html = client.get("/changelog").text
    newest = max(
        reader_pages.datetime.strptime(m, "%B %d, %Y").date()
        for m in re.findall(r'<h2 id="[^"]+">([A-Z][a-z]+ \d{1,2}, \d{4}):', html)
    )
    assert f'Updated <time datetime="{newest.isoformat()}">' in html
    months = html[html.index('<details class="reader-contents reader-contents--months">'):]
    months = months[:months.index("</details>")]
    assert "October 2026" in months and "June 2026" in months
    assert months.count("<a ") < 12


def test_long_pages_without_contents_get_one(client):
    html = client.get("/privacy").text
    start = html.index('<details class="reader-contents">')
    contents = html[start:html.index("</details>", start)]
    assert contents.count("<a ") >= 10
    assert '<h2 id="1-introduction">1. Introduction</h2>' in html
    faq = client.get("/faq").text
    start = faq.index('<details class="reader-contents">')
    faq_contents = faq[start:faq.index("</details>", start)]
    # Topic card titles stay out; the questions are listed.
    assert "Is OmniTrackr free?" in faq_contents and ">Tracking</a>" not in faq_contents


def test_styles_are_inlined_with_the_csp_nonce(client):
    response = client.get("/guides")
    html = response.text
    nonce = re.search(r"'nonce-([^']+)'", response.headers["content-security-policy"]).group(1)
    for name in ("fonts.css", "public-reader.css", "site.css"):
        assert f'<style data-from="{name}" nonce="{nonce}">' in html, name
        assert f'href="/static/{name}' not in html, name
    assert re.search(rf'<script nonce="{nonce}">\(function \(\) {{\n  var root = document.documentElement', html)


def test_other_reader_layout_pages_keep_linked_styles_and_stay_dark(client):
    for path in ("/supporters", "/sample-library"):
        html = client.get(path).text
        assert "data-reader" not in html.split("<head>")[0]
        assert "/static/public-reader.css?v=" in html
        assert "data-reader-theme" not in html


def test_light_theme_is_opt_in_and_scoped(client):
    css = (APP / "static" / "public-reader.css").read_text(encoding="utf-8")
    light = css[css.index("@media (prefers-color-scheme: light)"):]
    assert 'html[data-reader]:not([data-theme="dark"]) .public-reader .reader-shell' in light
    assert 'html[data-reader][data-theme="light"] .public-reader .reader-shell' in light
    # The site header keeps its dark look; only the reading area changes.
    assert "--site-text: #16132b" in light and ".site-header { background: rgba(11, 10, 24, .96); }" in light
    # The switch is invisible until the script sets it up, so the row never shifts.
    assert '.reader-theme:not([data-next]) { visibility: hidden; }' in css
    script = reader_pages.THEME_SCRIPT
    assert "localStorage" in script and "prefers-color-scheme: light" in script
    assert "localStorage" not in (APP / "static" / "site.js").read_text(encoding="utf-8")


def test_inter_has_a_size_matched_fallback():
    fonts = (APP / "static" / "fonts.css").read_text(encoding="utf-8")
    block = fonts[fonts.index("font-family: 'Inter Fallback'"):]
    block = block[:block.index("}")]
    assert "size-adjust: 107.12%" in block and "local('Arial')" in block
    site = (APP / "static" / "site.css").read_text(encoding="utf-8")
    assert '--site-font: Inter, "Inter Fallback",' in site


def test_compare_and_faq_no_longer_load_the_legacy_stylesheet():
    for name in ("compare.html", "faq.html"):
        assert "public-legacy.css" not in (APP / "templates" / name).read_text(encoding="utf-8")


def test_guides_list_all_eight_media_types():
    # The changelog is left out: its older entries were right when they were written.
    for name in set(reader_pages.PAGES) - {"changelog.html"}:
        text = (APP / "templates" / name).read_text(encoding="utf-8")
        assert not re.search(r"\bsix (built-in |media )?(categories|media types|types)\b", text), name
        assert not re.search(r"games, music, and books\b(?!, manga)", text), name


def test_faq_and_ads_pages_name_every_ad_eligible_page(client):
    faq = client.get("/faq").text
    questions = next(item for item in _json_ld(faq) if item.get("@type") == "FAQPage")["mainEntity"]
    names = [q["name"] for q in questions]
    assert "Is OmniTrackr free?" in names and "Where can ads appear?" in names
    ads = client.get("/advertising").text
    for href in ("/in-order", "/if-you-liked", "/media-tracking", "/export-import-guide", "/review-guidelines",
                 "/sample-library", "/binge-calculator", "/halloween", "/holidays"):
        assert f'href="{href}"' in ads, href
    loader = (APP / "static" / "ad-loader.js").read_text(encoding="utf-8")
    for path in ("/media-tracking", "/review-guidelines", "/binge-calculator", "/halloween", "/holidays"):
        assert path in loader, path


def test_pages_outside_the_list_are_untouched():
    page = '<html lang="en"><head></head><body><main id="reader-main"><a href="/" class="back-link">Back</a></main></body></html>'
    assert reader_pages.enhance(page, "public_landing.html") == page


def test_import_guide_lists_everything_the_exports_hold():
    html = (APP / "templates" / "export_import_guide.html").read_text(encoding="utf-8")
    for phrase in ("<code>tags.csv</code>", "<code>why-added.csv</code>", "saved shelf views", "stops at 10 tags per title",
                   "Why you added a title"):
        assert phrase in html, phrase
