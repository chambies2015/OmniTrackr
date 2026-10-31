"""Poster-sized CDN images, page breadcrumbs and the hub sign-up prompt (Oct 31 landing page pass)."""
import json
import re

import pytest
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app import image_sizes, page_breadcrumbs, site_chrome
from app.html_finish import HtmlFinishMiddleware, finish

RAWG = "https://media.rawg.io/media/games/734/7342a1cd82c8997ec620084ae4c2e7e4.jpg"
SHOT = "https://media.rawg.io/media/screenshots/bb7/bb7fca4136eccec5e2e82b8a19849489.jpg"
MAL = "https://cdn.myanimelist.net/images/anime/10/47347l.jpg"


def ld_blocks(html):
    return [json.loads(block) for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


# Images

def test_rawg_covers_ask_for_a_size_rawg_serves():
    assert image_sizes.sized(RAWG) == "https://media.rawg.io/media/resize/420/-/games/734/7342a1cd82c8997ec620084ae4c2e7e4.jpg"
    assert image_sizes.sized(SHOT, 1280).startswith("https://media.rawg.io/media/resize/1280/-/screenshots/")
    assert image_sizes.sized(RAWG, 300).startswith("https://media.rawg.io/media/resize/420/")  # 300 is not a RAWG size
    assert image_sizes.sized(RAWG, 5000).startswith("https://media.rawg.io/media/resize/1280/")
    resized = image_sizes.sized(RAWG)
    assert image_sizes.sized(resized) == resized
    for other in (None, "", "/static/poster-placeholder.svg", "http://media.rawg.io/media/games/734/x.jpg",
                  "https://static.tvmaze.com/uploads/images/medium_portrait/648/1622443.jpg"):
        assert image_sizes.sized(other) == other


def test_only_img_tags_are_rewritten():
    html = (f'<meta property="og:image" content="{RAWG}"><a href="{SHOT}">full size</a>'
            f'<script type="application/ld+json">{{"image": "{RAWG}"}}</script>'
            f'<img src="{RAWG}" alt="" width="200" height="300" loading="lazy">'
            f'<img class="title-hero__backdrop" src="{SHOT}" alt="">'
            f'<img class="title-hero__poster" src="{RAWG}" fetchpriority="high">'
            f'<img src="{RAWG}" srcset="{RAWG} 1x, {SHOT} 2x">')
    out = image_sizes.shrink_html(html)
    assert f'content="{RAWG}"' in out and f'href="{SHOT}"' in out and f'"image": "{RAWG}"' in out
    assert '<img src="https://media.rawg.io/media/resize/420/-/games/' in out
    assert 'class="title-hero__backdrop" src="https://media.rawg.io/media/resize/1280/-/screenshots/' in out
    assert 'class="title-hero__poster" src="https://media.rawg.io/media/resize/640/-/games/' in out
    assert "srcset=\"https://media.rawg.io/media/resize/420/-/games/734/7342a1cd82c8997ec620084ae4c2e7e4.jpg 1x, " \
           "https://media.rawg.io/media/resize/420/-/screenshots/" in out


def test_large_myanimelist_covers_shrink_only_for_small_thumbnails():
    small = image_sizes.shrink_html(f'<img src="{MAL}" width="64" height="88">')
    assert "47347.jpg" in small and "47347l.jpg" not in small
    assert image_sizes.shrink_html(f'<img src="{MAL}" width="200" height="300">') == f'<img src="{MAL}" width="200" height="300">'


def _app(body, media_type="text/html; charset=utf-8"):
    async def page(request):
        if media_type.startswith("application/json"):
            return JSONResponse({"image": RAWG})
        return HTMLResponse(body, media_type=media_type)

    app = Starlette(routes=[Route("/", page, methods=["GET", "POST"])])
    app.add_middleware(HtmlFinishMiddleware)
    return TestClient(app)


def test_middleware_rewrites_html_and_fixes_the_length():
    client = _app(f'<html><body><img src="{RAWG}"></body></html>')
    response = client.get("/")
    assert "/media/resize/420/-/games/" in response.text
    assert int(response.headers["content-length"]) == len(response.content)


def test_middleware_leaves_json_and_other_methods_alone():
    assert _app("", "application/json").get("/").json() == {"image": RAWG}
    assert RAWG in _app(f'<img src="{RAWG}">').post("/").text


def test_title_search_results_use_small_covers():
    from app import title_search
    entry = {"kind": "video_game", "label": "Game", "title": "Hades", "year": 2020, "slug": "hades-2020",
             "image": RAWG, "members": 3, "words": ["hades"], "base": "hades"}
    results = title_search.search([entry], "hades")
    assert results[0]["image"].startswith("https://media.rawg.io/media/resize/200/-/games/")
    assert entry["image"] == RAWG  # the cached index keeps the original


# Breadcrumbs

def page(canonical, title, robots="index, follow, max-image-preview:large", extra=""):
    return (f'<!DOCTYPE html><html><head><title>{title}</title><meta name="robots" content="{robots}">'
            f'<link rel="canonical" href="{canonical}">{extra}</head><body><h1>x</h1></body></html>')


@pytest.mark.parametrize("path, title, names", [
    ("/if-you-liked/interstellar", "Movies like Interstellar: 7 to watch, play, read and hear next | OmniTrackr",
     ["Home", "If you liked", "Movies like Interstellar"]),
    ("/in-order", "Franchises in order: what to watch, read and play first | OmniTrackr", ["Home", "Franchises in order"]),
    ("/best-of/2026/movies", "Best movies of 2026 so far: 8 films worth your evening | OmniTrackr",
     ["Home", "Best of the year", "Best movies of 2026 so far"]),
    ("/new-this-week/2026-10-19", "New releases for the week of October 19 to 25, 2026 | OmniTrackr",
     ["Home", "New this week", "New releases for the week of October 19 to 25, 2026"]),
    ("/collections/public/3", "Cozy Games for Slow Evenings | OmniTrackr Collection",
     ["Home", "Public lists", "Cozy Games for Slow Evenings"]),
    ("/daily/archive", "OmniTrackr Daily archive: every past puzzle | OmniTrackr",
     ["Home", "OmniTrackr Daily", "OmniTrackr Daily archive"]),
    ("/reviews?category=movie", "Movie Reviews &amp; Ratings - OmniTrackr", ["Home", "Reviews", "Movie Reviews & Ratings"]),
    ("/discover/monthly/september-2026", "September 2026: Begin small | Discover | OmniTrackr",
     ["Home", "Discover", "September 2026: Begin small"]),
])
def test_breadcrumbs_follow_the_section_hubs(path, title, names):
    out = page_breadcrumbs.add_breadcrumbs(page("https://omnitrackr.xyz" + path, title))
    crumbs = [block for block in ld_blocks(out) if block["@type"] == "BreadcrumbList"]
    assert len(crumbs) == 1
    items = crumbs[0]["itemListElement"]
    assert [item["name"] for item in items] == names
    assert [item["position"] for item in items] == list(range(1, len(names) + 1))
    assert items[0]["item"] == "https://omnitrackr.xyz/" and items[-1]["item"] == "https://omnitrackr.xyz" + path


@pytest.mark.parametrize("html", [
    page("https://omnitrackr.xyz/discover/x", "Trail", robots="noindex, follow"),
    page("https://omnitrackr.xyz/", "Home"),
    page("https://omnitrackr.xyz/discover/x", "Trail", extra='<script type="application/ld+json">{"@type":"BreadcrumbList"}</script>'),
    "<html><head><title>No canonical</title><meta name=\"robots\" content=\"index, follow\"></head></html>",
])
def test_pages_that_should_not_get_breadcrumbs(html):
    assert page_breadcrumbs.add_breadcrumbs(html) == html


def test_breadcrumb_names_cannot_close_the_script_block():
    out = page_breadcrumbs.add_breadcrumbs(page("https://omnitrackr.xyz/collections/public/9", "&lt;/script&gt;&lt;b&gt;x"))
    block = out[out.index('<script type="application/ld+json">'):]
    assert "</script><b>" not in block
    assert ld_blocks(out)[0]["itemListElement"][-1]["name"] == "</script><b>x"


@pytest.mark.parametrize("path", ["/discover", "/in-order", "/if-you-liked/dune", "/best-of"])
def test_indexed_pages_carry_one_breadcrumb_trail(client, path):
    html = client.get(path).text
    assert sum(1 for block in ld_blocks(html) if block.get("@type") == "BreadcrumbList") == 1


# Sign-up prompt

@pytest.mark.parametrize("path, heading", [
    ("/discover", "Keep the ones that catch your eye"),
    ("/in-order", "Keep your place in the series"),
    ("/if-you-liked", "Keep the ones that catch your eye"),
    ("/best-of", "Keep the ones that catch your eye"),
    ("/guides", "Try it with your own list"),
])
def test_hubs_ask_signed_out_readers_to_join(client, path, heading):
    html = client.get(path).text
    assert html.count("data-site-join") == 1 and heading in html
    join = html[html.index('<section class="site-join"'):]
    join = join[:join.index("</section>")]
    assert 'href="/#signup"' in join and 'href="/demo"' in join and "data-guest-only" in join
    assert html.index("data-site-join") < html.index('<footer class="site-footer"')
    assert "SITE_JOIN" not in html


@pytest.mark.parametrize("path", ["/in-order/star-wars", "/best-of/2026/movies", "/if-you-liked/dune", "/tier-list", "/faq"])
def test_pages_with_their_own_prompt_or_other_sections_get_none(client, path):
    html = client.get(path).text
    assert "data-site-join" not in html and "SITE_JOIN" not in html


def test_members_never_get_the_prompt():
    html = site_chrome.apply_site_chrome("<body><!--SITE_NAV:discover--><main></main><!--SITE_FOOTER--></body>", member=True)
    assert "SITE_JOIN" not in html and "data-site-join" not in finish(html)
    guest = site_chrome.apply_site_chrome("<body><!--SITE_NAV:discover--><main></main><!--SITE_FOOTER--></body>")
    assert "data-site-join" in finish(guest)


def test_stored_sign_in_hides_guest_only_sections():
    js = open("app/static/site-nav.js", encoding="utf-8").read()
    assert "[data-guest-only]" in js
    css = open("app/static/site.css", encoding="utf-8").read()
    assert ".site-join[hidden] { display: none; }" in css


def test_top_landing_descriptions_fit_in_a_result_snippet(client):
    for path in ("/", "/reviews", "/tier-list", "/discover"):
        description = re.search(r'<meta name="description" content="([^"]*)"', client.get(path).text).group(1)
        assert 70 <= len(description) <= 160, (path, len(description))


# Release Radar cards link to title pages

from tests.test_release_radar import fixture_radar, user_by_name  # noqa: E402,F401  (fixture)


def test_radar_cards_link_to_title_pages_members_track(client, db_session, fixture_radar, authenticated_client):
    from app import models
    user = user_by_name(db_session)
    db_session.add(models.TVShow(user_id=user.id, title="War", year=2026, watched=True, rating=9))
    db_session.commit()
    client.headers = {}
    html = client.get("/release-radar/tv").text
    war = html[html.index('id="item-tvm-86587-s1"'):]
    war = war[: war.index("</article>")]
    assert '<a class="radar-title-link" href="/titles/tv/war-2026">' in war
    eden = html[html.index('id="item-tvm-90001-s1"'):]
    assert "radar-title-link" not in eden[: eden.index("</article>")]


def test_breadcrumbs_carry_the_page_nonce():
    html = page("https://omnitrackr.xyz/discover/x", "Trail", extra='<script nonce="abc_123" src="/a.js"></script>')
    assert '<script type="application/ld+json" nonce="abc_123">' in page_breadcrumbs.add_breadcrumbs(html)
