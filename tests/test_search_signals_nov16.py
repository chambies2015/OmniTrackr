"""Search signals pass, November 16 2026.

Small technical fixes found by crawling the live sitemap and every page it links to:
- sitemap lastmod for reviews and public lists said "today" on every build, which
  teaches Google to ignore lastmod for the whole file; they now carry real dates or none,
- /about/ answered with a temporary 307 to /about; slash-only redirects are now 301,
- "How long" guides had a two-step breadcrumb (no Binge calculator hub) and named the
  page with the whole title, answer included; browse shelves had no Home step,
- a few indexed pages sent plain "index, follow" without max-image-preview:large,
- the HTML site map linked the switch guides, browse shelves and monthly challenges
  only through their hubs.
"""
import json
import re
from datetime import datetime

from app import models
from app.page_breadcrumbs import trail, _page_name
from app.page_hints import allow_large_image_previews
from tests.test_thin_pages_oct20 import LONG_REVIEW, member, review


def _sitemap_entry(text, loc_fragment):
    for block in re.findall(r"<url>.*?</url>", text, re.S):
        if loc_fragment in block:
            return block
    return None


def test_review_lastmod_is_when_the_review_changed_not_today(client, db_session):
    movie = review(db_session, member(db_session, "datedwriter"), LONG_REVIEW)
    state = db_session.query(models.PublicReviewState).filter_by(category="movie", item_id=movie.id).first()
    if state is None:
        state = models.PublicReviewState(user_id=movie.user_id, category="movie", item_id=movie.id, content_hash="x")
        db_session.add(state)
    state.updated_at = datetime(2026, 9, 14, 8, 30)
    db_session.commit()
    entry = _sitemap_entry(client.get("/sitemap.xml").text, f"/reviews/{movie.id}?category=movie</loc>")
    assert entry is not None
    assert "<lastmod>2026-09-14</lastmod>" in entry


def test_review_without_a_change_record_has_no_lastmod(client, db_session):
    movie = review(db_session, member(db_session, "undatedwriter"), LONG_REVIEW)
    db_session.query(models.PublicReviewState).filter_by(category="movie", item_id=movie.id).delete()
    db_session.commit()
    entry = _sitemap_entry(client.get("/sitemap.xml").text, f"/reviews/{movie.id}?category=movie</loc>")
    assert entry is not None
    assert "<lastmod>" not in entry


def test_no_member_entry_claims_todays_date(client, db_session):
    review(db_session, member(db_session, "todaycheck"), LONG_REVIEW)
    today = datetime.now().strftime("%Y-%m-%d")
    for block in re.findall(r"<url>.*?</url>", client.get("/sitemap.xml").text, re.S):
        if "/reviews/" in block or "/collections/public/" in block:
            assert f"<lastmod>{today}</lastmod>" not in block


def test_trailing_slash_redirects_are_permanent(client):
    response = client.get("/about/", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"].endswith("/about")
    head = client.head("/in-order/star-wars/", follow_redirects=False)
    assert head.status_code == 301


def test_other_redirects_keep_their_status(client):
    # The weekly roundup hub sends readers to this week's page on purpose (temporary).
    response = client.get("/new-this-week", follow_redirects=False)
    assert response.status_code in (302, 307)


def test_binge_guides_sit_under_the_calculator_in_the_trail():
    steps = trail("https://omnitrackr.xyz/binge-calculator/breaking-bad", "How long does it take to watch Breaking Bad?")
    assert [name for name, _ in steps] == ["Home", "Binge calculator", "How long does it take to watch Breaking Bad?"]


def test_question_titles_are_named_by_the_question():
    head = "<title>How long to watch Fullmetal Alchemist: Brotherhood? 26 hours | OmniTrackr</title>"
    assert _page_name(head) == "How long to watch Fullmetal Alchemist: Brotherhood?"
    assert _page_name("<title>Movies like Interstellar: 7 to watch, play and read next | OmniTrackr</title>") == "Movies like Interstellar"


def test_binge_guide_page_breadcrumb(client):
    page = client.get("/binge-calculator/breaking-bad")
    assert page.status_code == 200
    crumbs = [json.loads(block) for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page.text, re.S)
              if "BreadcrumbList" in block]
    assert crumbs
    names = [item["name"] for item in crumbs[0]["itemListElement"]]
    assert names[:2] == ["Home", "Binge calculator"] and len(names) == 3


def test_browse_shelf_trail_starts_at_home(client):
    page = client.get("/browse/manga")
    assert page.status_code == 200
    block = next(b for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page.text, re.S)
                 if "BreadcrumbList" in b)
    names = [item["name"] for item in json.loads(block)["itemListElement"]]
    assert names == ["Home", "Browse", "Manga"]


def test_plain_index_pages_get_large_image_previews(client):
    page = client.get("/terms")
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in page.text


def test_large_previews_leave_noindex_alone():
    html = '<html><head><meta name="robots" content="noindex, follow"></head><body></body></html>'
    assert allow_large_image_previews(html) == html
    done = '<html><head><meta name="robots" content="index, follow, max-image-preview:large"></head></html>'
    assert allow_large_image_previews(done) == done


def test_site_map_links_every_switch_guide_shelf_and_challenge(client):
    from app import browse, challenges, switch_guides
    text = client.get("/site-map").text
    for slug in switch_guides.GUIDES:
        assert f'href="{switch_guides.path(slug)}"' in text
    for kind in browse.KINDS:
        assert f'href="{browse.path(kind)}"' in text
    for month in challenges.public_months():
        assert f'href="/challenges/{challenges.slug_for(month)}"' in text
