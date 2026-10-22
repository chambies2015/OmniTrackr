"""Best-of-the-year lists (/best-of): hand-written picks of each year's best new titles (Oct 2026)."""
import re

import pytest

from app import best_of, editorial_index, pick, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.best_of_guides import GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["start"] + entry["coming"] + [title + " " + text for title, text in entry["also"]]
    texts += [item["why"] + " " + item["note"] + " " + item["caveat"] for item in entry["picks"]]
    return sum(len(text.split()) for text in texts)


def test_every_list_is_complete_and_substantial():
    assert {GUIDES[slug]["format"] for slug in best_of.for_year(2026)} == set(best_of.FORMAT_ORDER)
    for slug, entry in GUIDES.items():
        assert slug == f"{entry['year']}-{entry['format']}"
        assert entry["format"] in best_of.FORMAT_ORDER and entry["kind"] in title_pages.KINDS
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["reviewed"])
        assert 60 <= len(entry["summary"]) <= 170 and entry["search_title"] and entry["name"]
        assert len(entry["lead"]) >= 2 and entry["start"] and len(entry["sources"]) >= 5
        assert 7 <= len(entry["picks"]) <= 10
        assert words(entry) >= 1000, slug
        for label, url in entry["sources"]:
            assert label and url.startswith("https://")
        seen = set()
        for item in entry["picks"]:
            assert item["kind"] == entry["kind"], item["title"]
            assert item["title"] and item["released"] and item["why"] and item["note"] and item["caveat"]
            # Returning shows are filed under their first season; festival films under their premiere.
            assert 2000 < item["year"] <= entry["year"]
            assert (item["creator"] is None) == (title_pages.KINDS[item["kind"]][4] is None)
            key = title_pages.slugify(item["title"])
            assert key not in seen
            seen.add(key)


def test_every_pick_joins_pick_for_me_so_it_can_be_saved():
    for slug, entry in GUIDES.items():
        for item in entry["picks"]:
            pooled = best_of.pool_entry(item)
            assert pooled is not None, item["title"]
            assert pick.find_id(pooled["id"]) is pooled
    # A pick only these lists recommend keeps the list as its source and links to the pick.
    heron = pick.find("movie", "blue-heron-2025")
    assert heron["source_label"] == "The best movies of 2026 so far"
    assert heron["source_url"] == "/best-of/2026/movies#pick-blue-heron"


def test_list_page_reads_completely_without_an_account(client):
    response = client.get("/best-of/2026/movies")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/best-of/2026/movies">' in html
    assert "<title>Best movies of 2026 so far" in html
    assert "<h1>The best movies of 2026 so far</h1>" in html
    assert "Also worth a look" in html and "Still to come in 2026" in html and "How we chose" in html
    assert "Sources we checked" in html and 'href="https://www.metacritic.com/' in html
    for item in GUIDES["2026-movies"]["picks"]:
        assert f'id="pick-{title_pages.slugify(item["title"])}"' in html
    assert html.count("Save to my list") == len(GUIDES["2026-movies"]["picks"])
    assert 'data-guest-kind="movie" data-guest-slug="project-hail-mary-2026"' in html
    assert "/static/guest-list.js" in html and "/static/if-you-liked.js" in html and "/static/best-of.css" in html
    assert "/static/ad-loader.js" in html
    assert '"@type": "Article"' in html and '"ItemList"' in html
    # The other formats, the hub and the related guides are linked.
    for other in ("tv", "anime", "games", "books"):
        assert f'href="/best-of/2026/{other}"' in html
    assert 'href="/best-of"' in html and 'href="/if-you-liked/interstellar"' in html
    assert "Cookie" in response.headers["vary"]


def test_lists_without_extras_skip_those_sections(client):
    html = client.get("/best-of/2026/anime").text
    assert 'id="also"' not in html and 'id="coming"' not in html
    assert 'href="#also"' not in html and 'href="#coming"' not in html


def test_members_get_add_buttons_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/best-of/2026/games").text
    assert html.count("data-liked-add=") == len(GUIDES["2026-games"]["picks"])
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html
    assert "/static/ad-loader.js" not in html


@pytest.mark.parametrize("path", ["/best-of/2026/music", "/best-of/1999/movies", "/best-of/1999"])
def test_unknown_lists_are_not_found(client, path):
    assert client.get(path).status_code == 404


def test_year_path_points_at_the_hub(client):
    response = client.get("/best-of/2026", follow_redirects=False)
    assert response.status_code == 301 and response.headers["location"] == "/best-of#bo-2026"


def test_hub_lists_every_guide(client):
    response = client.get("/best-of")
    assert response.status_code == 200
    for slug in GUIDES:
        assert f'href="{best_of.path(slug)}"' in response.text
    assert '<meta name="robots" content="index, follow' in response.text
    assert "public" in response.headers["cache-control"]


def test_every_related_link_resolves(client):
    for entry in GUIDES.values():
        for _, href in entry["related"]:
            assert client.get(href).status_code == 200, href


def test_sitemap_site_map_and_guide_index_include_the_lists(client):
    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://omnitrackr.xyz/best-of</loc>" in sitemap
    for slug, entry in GUIDES.items():
        assert f"<loc>https://omnitrackr.xyz{best_of.path(slug)}</loc><lastmod>{entry['reviewed']}</lastmod>" in sitemap
    assert 'href="/best-of/2026/books"' in client.get("/site-map").text
    sections = {piece["section"] for piece in editorial_index.entries()}
    assert "best-of" in sections
    assert 'href="/best-of"' in client.get("/about").text
