"""Trust signals for the guides (Nov 22 2026): the /corrections log, the change notes at
the end of each guide, the publisher record in structured data, and the In order
first-published dates."""
import json
import re
from datetime import date

import pytest

from app import corrections_log, editorial_index, in_order, publisher_data, site_chrome, switch_guides
from app.in_order_guides import GUIDES as IN_ORDER_GUIDES, NOVEMBER_GUIDES, NOVEMBER_PUBLISHED


def _ld(html):
    blocks = []
    for raw in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        data = json.loads(raw)
        for item in data if isinstance(data, list) else [data]:
            blocks.extend(item.get("@graph", [item]))
    return blocks


def _main(html):
    return html[html.index("<main"):html.index("</main>")]


def test_corrections_page_lists_every_logged_change(client):
    response = client.get("/corrections")
    assert response.status_code == 200
    html = response.text
    assert "<!--" not in _main(html)
    assert 'content="index, follow' in html and "x-robots-tag" not in response.headers
    assert "<h1>Corrections and updates</h1>" in html and 'id="send"' in html
    for change in corrections_log.guide_changes():
        assert f'href="{change.href}">{change.label}</a>' in html.replace("&amp;", "&").replace("&#x27;", "'")
        for page, _ in change.pages:
            assert f'href="{page}"' in html
    for day, name, path, _ in corrections_log.POLICY_CHANGES:
        assert f'href="{path}">{name}</a>' in html
    page = next(block for block in _ld(html) if block["@type"] == "WebPage")
    assert page["dateModified"] == corrections_log.latest_date()
    assert page["publisher"]["@id"] == publisher_data.ORG_ID


def test_log_entries_are_dated_known_kinds_and_point_at_real_guides():
    guides = {piece["href"] for piece in editorial_index.entries()}
    hubs = {"/if-you-liked", "/new-releases", "/challenges", "/browse"}
    guides |= {switch_guides.path(slug) for slug in switch_guides.GUIDES}
    for change in corrections_log.guide_changes():
        date.fromisoformat(change.date)
        assert change.date <= corrections_log.STARTED
        assert change.kind in corrections_log.KINDS
        assert change.pages and change.summary
        for page, line in change.pages:
            assert page in guides | hubs, page
            assert line.strip()
    dates = [change.date for change in corrections_log.guide_changes()]
    assert dates == sorted(dates, reverse=True)


def test_corrections_page_is_linked_from_the_footer_rail_and_trust_pages(client):
    assert ("Corrections", "/corrections") in dict(site_chrome.FOOTER_GROUPS)["OmniTrackr"]
    for path in ("/about", "/contact", "/content-quality"):
        assert 'href="/corrections' in _main(client.get(path).text), path
    html = client.get("/in-order/star-wars").text
    rail = html[html.index('<aside class="guide-rail"'):]
    assert 'href="/corrections#send">Send a correction</a>' in rail and 'href="/corrections">Corrections log</a>' in rail


def test_november_in_order_guides_give_the_day_they_went_up(client):
    assert len(NOVEMBER_GUIDES) == 24
    html = client.get("/in-order/marvel-cinematic-universe").text
    article = next(block for block in _ld(html) if block["@type"] == "Article")
    assert article["datePublished"] == NOVEMBER_PUBLISHED
    assert "First published November 14, 2026." in html and "First published October 17" not in html
    first_ten = client.get("/in-order/star-wars").text
    assert next(b for b in _ld(first_ten) if b["@type"] == "Article")["datePublished"] == "2026-10-17"
    for slug, guide in IN_ORDER_GUIDES.items():
        assert guide.get("published", "2026-10-17") <= guide["reviewed"], slug
        assert (guide.get("published") == NOVEMBER_PUBLISHED) == (slug in NOVEMBER_GUIDES)


def test_guide_with_logged_changes_lists_them_at_the_end(client):
    html = client.get("/in-order/marvel-cinematic-universe").text
    assert html.count("data-guide-changes") == 1
    note = html[html.index('<div class="guide-changes"'):]
    note = note[:note.index("</div>") + 6]
    assert "<h3>Changes to this guide</h3>" in note
    assert '<span class="fix-kind fix-kind--correction">Correction</span>' in note
    assert 'href="/corrections"' in note and 'href="/corrections#send"' in note
    # Inside the body column, after the "How we chose" note, not in the rail.
    body = html[html.index('class="guide-body"'):html.index('<aside class="guide-rail"')]
    assert note in body and body.index('id="method"') < body.index("guide-changes")


def test_binge_guide_note_names_its_own_new_section(client):
    from app.binge_guides import GUIDES
    html = client.get("/binge-calculator/breaking-bad").text
    heading = GUIDES["breaking-bad"]["sections"][2][1]
    assert f"Added the section “{heading}”" in html
    two_sections = client.get("/binge-calculator/one-piece").text
    assert "data-guide-changes" not in two_sections


def test_guides_without_a_first_published_line_get_one(client):
    for path in ("/discover/monthly/november-2026", "/awards/grammys-2027"):
        html = client.get(path).text
        note = html[html.index('<div class="guide-changes"'):]
        note = note[:note.index("</div>")]
        assert 'First published <time datetime="' in note, path
    awards = client.get("/awards/oscars-2027").text  # nothing logged, so dates only
    note = awards[awards.index('<div class="guide-changes"'):]
    assert "<h3>About this guide</h3>" in note[:note.index("</div>")]


def test_guide_with_nothing_logged_and_its_own_dates_is_unchanged(client):
    html = client.get("/in-order/star-wars").text
    assert "data-guide-changes" not in html and "First published October 17, 2026." in html


def test_note_step_leaves_other_pages_alone():
    page = ('<html><head><link rel="canonical" href="https://omnitrackr.xyz/privacy"></head><body>'
            '<article class="trail-guide"><header></header><section class="guide-sources"></section></article></body></html>')
    assert corrections_log.add_change_notes(page) == page
    assert corrections_log.add_change_notes("<html><body>plain</body></html>") == "<html><body>plain</body></html>"


def test_guide_data_points_at_the_publisher_record(client):
    html = client.get("/if-you-liked/dune").text
    article = next(block for block in _ld(html) if block["@type"] == "Article")
    assert article["publisher"]["@id"] == publisher_data.ORG_ID
    assert article["publisher"]["logo"] == publisher_data.LOGO
    assert article["publishingPrinciples"] == publisher_data.STANDARDS
    assert article["author"]["url"] == "https://omnitrackr.xyz/about"


def test_publisher_step_keeps_other_data_and_bad_json_untouched():
    compact = ('<script type="application/ld+json">{"@type":"WebSite","name":"OmniTrackr",'
               '"publisher":{"@type":"Organization","name":"OmniTrackr","url":"https://omnitrackr.xyz/"}}</script>')
    data = json.loads(re.search(r">(.*)</script>", publisher_data.link_publisher(compact)).group(1))
    assert data["publisher"]["@id"] == publisher_data.ORG_ID and data["name"] == "OmniTrackr"
    other = '<script type="application/ld+json">{"@type":"Review","author":{"@type":"Person","name":"x"}}</script>'
    assert publisher_data.link_publisher(other) == other
    broken = ('<script type="application/ld+json">{"publisher": {"@type": "Organization", "name": "OmniTrackr", '
              '"url": "https://omnitrackr.xyz/"}, </script>')
    assert publisher_data.link_publisher(broken) == broken


def test_homepage_and_about_carry_the_same_publisher_record(client):
    home = next(b for b in _ld(client.get("/").text) if b["@type"] == "Organization")
    assert home == {"@context": "https://schema.org", **publisher_data.organization()}
    about = next(b for b in _ld(client.get("/about").text) if b["@type"] == "AboutPage")
    assert about["mainEntity"] == publisher_data.organization()
    contact = next(b for b in _ld(client.get("/contact").text) if b["@type"] == "ContactPage")
    assert contact["mainEntity"]["@id"] == publisher_data.ORG_ID
    assert contact["mainEntity"]["contactPoint"] == publisher_data.organization()["contactPoint"]


def test_about_page_history_and_counts(client):
    html = client.get("/about").text
    main = _main(html)
    assert 'id="history-heading"' in main and "<!--GUIDE_COUNT-->" not in main
    assert f"There are {len(editorial_index.entries()):,} written guides today." in main
    assert "connect four titles in different formats" in main
    assert "a film, a show, a game, an album and a book" not in main
    assert "github.com/chambies2015/OmniTrackr" in main and "AI writing tools" in main


def test_llms_txt_lists_the_corrections_page(client):
    assert "- Corrections and Updates: https://omnitrackr.xyz/corrections" in client.get("/llms.txt").text


def test_corrections_page_stays_out_of_the_sitemap_like_the_other_trust_pages(client):
    assert "/corrections" not in client.get("/sitemap.xml").text
