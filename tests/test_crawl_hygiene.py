"""Sign-in and save links are actions, not pages: they carry rel="nofollow" so search engines
don't crawl homepage variants like /?next=… (Search Console: "Alternate page with proper
canonical tag", Oct 2026) or the noindex save screens."""
import re

import pytest

from app import release_radar as radar
from app.routers import release_radar as radar_router
from app.routers import reviews as reviews_router

ACTION = re.compile(r'href="(/\?[^"]*|[^"]*/save(\?[^"]*)?)"')


def action_anchors(html):
    return [a for a in re.findall(r"<a\b[^>]*>", html) if ACTION.search(a)]


def assert_all_nofollow(html):
    anchors = action_anchors(html)
    assert anchors, "expected at least one sign-in or save link"
    missing = [a for a in anchors if 'rel="nofollow"' not in a]
    assert not missing, missing


@pytest.mark.parametrize("path", ["/demo", "/discover/finding-your-feet", "/discover/monthly/october-2026"])
def test_static_pages_mark_action_links_nofollow(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert_all_nofollow(response.text)


def test_review_cards_mark_save_links_nofollow():
    review = {"id": 7, "category": "movie", "title": "Arrival", "review": "x " * 200, "rating": 9, "username": "ann",
              "search_ready": True, "community_ready": True, "director": "Denis Villeneuve", "year": 2016}
    assert_all_nofollow(reviews_router._review_card_html(review))


def test_radar_cards_mark_guest_track_links_nofollow():
    item = radar.make_item(category="tv", key="tvm-1-s1", title="Show", release_date="2026-10-02", source_url=None, popularity=5)
    assert_all_nofollow(radar_router.render_card(item, 0, "/release-radar/tv"))


def test_save_screens_mark_signin_links_nofollow():
    for name in ("review_save.html", "collection_save.html"):
        with open(f"app/templates/{name}", encoding="utf-8") as handle:
            assert_all_nofollow(handle.read().replace("{{SIGNIN_URL}}", "/?next=%2Fx#landing-auth"))


def test_homepage_variants_point_to_the_real_homepage(client):
    for path in ("/?next=/release-radar", "/?start=demo"):
        assert '<link rel="canonical" href="https://omnitrackr.xyz/">' in client.get(path).text
