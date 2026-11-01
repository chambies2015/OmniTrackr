"""Release guides (/new-releases): hand-written picks from a month's or a season's new releases (Nov 2026)."""
import re
from datetime import date

import pytest

from app import editorial_index, new_releases, pick, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.release_guides import GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["plan"] + [title + " " + text for title, text in entry["also"]]
    texts += [paragraph for section in entry["sections"] for paragraph in section["intro"]]
    texts += [" ".join((item["why"], item["note"], item.get("first", ""), item["caveat"]))
              for item in new_releases.picks(entry)]
    return sum(len(text.split()) for text in texts)


def test_every_guide_is_complete_and_substantial():
    for slug, entry in GUIDES.items():
        for field in ("published", "reviewed", "starts", "ends"):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry[field]), (slug, field)
        assert entry["starts"] <= entry["ends"] and entry["published"] <= entry["reviewed"]
        assert 60 <= len(entry["summary"]) <= 170 and entry["search_title"] and entry["name"] and entry["period"]
        assert len(entry["lead"]) >= 2 and entry["plan"] and entry["plan_heading"] and len(entry["sources"]) >= 8
        assert words(entry) >= 2500, slug
        formats = [section["format"] for section in entry["sections"]]
        assert len(formats) == len(set(formats)) >= 4
        assert all(fmt in new_releases.FORMAT_ORDER for fmt in formats)
        for label, url in entry["sources"]:
            assert label and url.startswith("https://")
        for label, href in entry["related"]:
            assert label and href.startswith("/")
        seen = set()
        for section in entry["sections"]:
            assert section["heading"] and section["intro"] and len(section["picks"]) >= 2
            for item in section["picks"]:
                assert item["kind"] in title_pages.KINDS
                assert item["title"] and item["released"] and item["why"] and item["note"] and item["caveat"]
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["date"]), item["title"]
                # Every pick is out (or out again, for a returning series) by the end of the guide's stretch.
                assert item["date"] <= entry["ends"], item["title"]
                assert 1950 < item["year"] <= int(entry["ends"][:4])
                assert (item["creator"] is None) == (title_pages.KINDS[item["kind"]][4] is None), item["title"]
                assert bool(item.get("first_link")) == bool(item.get("first_label"))
                key = (item["kind"], title_pages.slugify(item["title"]))
                assert key not in seen
                seen.add(key)


def test_guides_publish_on_their_date():
    assert new_releases.published(date(2026, 10, 31)) == {}
    live = new_releases.published(date(2026, 11, 1))
    assert set(live) == {"november-2026", "winter-2026-27"}
    assert new_releases.current(date(2026, 11, 15)) == "november-2026"
    assert new_releases.current(date(2027, 1, 20)) == "winter-2026-27"
    # Once every stretch has passed, the newest guide still counts as current.
    assert new_releases.current(date(2027, 6, 1)) in live


def test_every_pick_can_be_saved_but_is_only_suggested_once_out():
    for entry in GUIDES.values():
        for item in new_releases.picks(entry):
            pooled = new_releases.pool_entry(item)
            assert pooled is not None, item["title"]
            assert pick.find_id(pooled["id"]) is pooled
    gta = pick.find("game", "grand-theft-auto-vi-2026")
    assert gta["source_url"] == "/new-releases/november-2026#pick-grand-theft-auto-vi"
    assert gta["out"] == "2026-11-19"
    assert not pick.is_available(gta, date(2026, 11, 18))
    assert pick.is_available(gta, date(2026, 11, 19))
    assert gta not in pick.candidates("game", today=date(2026, 11, 1))
    assert gta in pick.candidates("game", today=date(2026, 12, 1))
    # Picks from the other guides have no release date and are always available.
    assert all(pick.is_available(entry, date(2000, 1, 1)) for entry in pick.pool() if not entry["out"])


def test_guide_page_reads_completely_without_an_account(client):
    response = client.get("/new-releases/november-2026")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/new-releases/november-2026">' in html
    assert "<h1>November 2026 releases worth your time</h1>" in html
    entry = GUIDES["november-2026"]
    for item in new_releases.picks(entry):
        assert f'id="{new_releases.anchor_id(item)}"' in html
    assert html.count("Save to my list") == len(new_releases.picks(entry))
    for section in entry["sections"]:
        assert f'id="section-{section["format"]}"' in html
    assert "Also on the calendar" in html and "A plan for the month" in html and "How we chose" in html
    assert "Sources we checked" in html and "with AI assistance" in html
    assert 'href="/in-order/hunger-games"' in html and 'href="/new-releases/winter-2026-27"' in html
    assert "/static/new-releases.css" in html and "/static/ad-loader.js" in html
    assert '"@type": "Article"' in html and '"ItemList"' in html


def test_members_get_add_buttons_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/new-releases/winter-2026-27").text
    client.cookies.clear()
    assert html.count("Add to my library") == len(new_releases.picks(GUIDES["winter-2026-27"]))
    assert "/static/ad-loader.js" not in html and "Save to my list" not in html


@pytest.mark.parametrize("path", ["/new-releases/october-2026", "/new-releases/winter-2027"])
def test_unknown_guides_are_not_found(client, path):
    assert client.get(path).status_code == 404


def test_hub_lists_every_live_guide(client):
    html = client.get("/new-releases").text
    for slug, entry in new_releases.published().items():
        assert f'href="{new_releases.path(slug)}"' in html
        assert entry["name"] in html
    assert 'href="/release-radar"' in html


def test_every_related_link_resolves(client):
    for entry in GUIDES.values():
        for _, href in entry["related"]:
            assert client.get(href).status_code == 200, href
        for item in new_releases.picks(entry):
            if item.get("first_link"):
                assert client.get(item["first_link"]).status_code == 200, item["first_link"]


def test_sitemap_site_map_menu_and_guide_index_include_the_guides(client):
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/new-releases</loc>" in sitemap
    for slug in new_releases.published():
        assert f"https://omnitrackr.xyz/new-releases/{slug}</loc>" in sitemap
    site_map = client.get("/site-map").text
    assert 'href="/new-releases/november-2026"' in site_map
    assert any(piece["section"] == "new-releases" for piece in editorial_index.entries())
    assert 'href="/new-releases"' in client.get("/best-of/2026/movies").text


def test_release_radar_points_at_this_months_guide():
    from app.routers.release_radar import _guide_note

    note = _guide_note()
    slug = new_releases.current()
    assert f'href="/new-releases/{slug}"' in note
