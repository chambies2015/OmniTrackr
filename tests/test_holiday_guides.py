"""Guides beside the holiday hub: Christmas 2026, the Thanksgiving weekend and December reading and listening (Nov 2026)."""
import re
from datetime import date
from pathlib import Path

import pytest

from app import models, pick, seasonal, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.discover_catalog import MONTHLY_EDITIONS, published_editions
from app.gift_guides import GUIDE as GIFT_GUIDE
from app.holiday_guides import GUIDES
from app.seasonal_guides import SEASONS

CHRISTMAS = GUIDES["christmas"]
THANKSGIVING = GUIDES["thanksgiving"]
LISTENING = GUIDES["reading-and-listening"]
HUB = SEASONS["holidays"]


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["intro"] + entry["method"] + [night["plan"] for night in entry["nights"]]
    texts += [question + " " + answer for question, answer in entry["faq"]]
    for shelf in entry["shelves"]:
        texts += shelf["intro"]
        texts += [item["why"] + " " + item["note"] + " " + item["caveat"] for item in shelf["picks"]]
    return sum(len(text.split()) for text in texts)


def keys(entry):
    return {(item["kind"], title_pages.slugify(item["title"])) for item in seasonal.picks(entry)}


def test_every_guide_is_complete_and_substantial():
    for slug, entry in GUIDES.items():
        assert entry["path"] == f"/holidays/{slug}" and entry["parent"] in SEASONS
        assert 60 <= len(entry["summary"]) <= 200 and entry["search_title"] and entry["card"] and entry["short"]
        assert words(entry) >= 3000, slug
        assert len(entry["shelves"]) == 4 and len(entry["faq"]) >= 5 and len(entry["nights"]) >= 5
        assert entry["published"] <= entry["reviewed"]
        seen = set()
        for shelf in entry["shelves"]:
            assert re.fullmatch(r"[a-z0-9-]{1,40}", shelf["key"]) and shelf["when"] and shelf["tagline"]
            assert len(shelf["picks"]) == 5
            for item in shelf["picks"]:
                assert item["kind"] in title_pages.KINDS and 1800 < item["year"] < 2030 and "level" not in item
                assert item["title"] and item["creator"] and item["time"] and item["why"] and item["note"] and item["caveat"]
                key = (item["kind"], title_pages.slugify(item["title"]))
                assert key not in seen
                seen.add(key)


def test_thanksgiving_covers_all_nine_formats_and_reading_sticks_to_ears_and_pages():
    assert {item["kind"] for item in seasonal.picks(THANKSGIVING)} == set(title_pages.KINDS)
    assert {item["kind"] for item in seasonal.picks(LISTENING)} == {"book", "audiobook", "podcast", "manga", "album"}


def test_no_pick_repeats_the_hub_the_gift_guide_or_each_other():
    gifts = {(item["kind"], title_pages.slugify(item["title"])) for section in GIFT_GUIDE["sections"] for item in section["gifts"]
             if item.get("title")}
    slugs = list(GUIDES)
    for index, slug in enumerate(slugs):
        for other in slugs[index + 1:]:
            assert not keys(GUIDES[slug]) & keys(GUIDES[other]), (slug, other)
    for entry in GUIDES.values():
        assert not keys(entry) & keys(HUB)
        assert not keys(entry) & gifts


def test_hub_picks_named_in_the_plans_are_on_the_hub():
    hub_titles = {item["title"] for item in seasonal.picks(HUB)}
    for title in ("Planes, Trains and Automobiles", "Sweetness and Lightning", "Overcooked! 2"):
        assert title in hub_titles
        assert any(title in night["plan"] for night in THANKSGIVING["nights"])
    for title in ("A Christmas Carol", "Vespertine"):
        assert title in hub_titles
        assert any(title in night["plan"] for night in LISTENING["nights"])
    for title in ("The Polar Express", "The Muppet Christmas Carol"):
        assert title in hub_titles
        assert any(title in night["plan"] for night in CHRISTMAS["nights"])


def test_every_pick_can_be_saved():
    for entry in GUIDES.values():
        for item in seasonal.picks(entry):
            pooled = seasonal.pool_entry(item)
            assert pooled is not None, item["title"]
            if item["kind"] in seasonal.EXTRA_KINDS:
                assert seasonal.find_extra(item["kind"], pooled["slug"])[1]["title"] == item["title"]
            else:
                assert pick.find_id(pooled["id"]) is pooled
    clue = pick.find("movie", "clue-1985")
    assert clue["source_label"] == "Thanksgiving weekend guide" and clue["source_url"] == "/holidays/thanksgiving#the-day-after"
    # Pick for me only suggests its six formats.
    assert not any(entry["kind"] in seasonal.EXTRA_KINDS for entry in pick.pool())


@pytest.mark.parametrize("slug", list(GUIDES))
def test_guide_reads_completely_without_an_account(client, slug):
    entry = GUIDES[slug]
    response = client.get(entry["path"])
    assert response.status_code == 200
    html = response.text
    assert f'<link rel="canonical" href="https://omnitrackr.xyz{entry["path"]}">' in html
    assert "noindex" not in html
    assert html.count('class="pick sn-pick"') == 20 and html.count("data-guest-kind=") == 20
    assert html.count("Before you start:") == 20 and "data-season-add=" not in html
    assert 'href="/holidays"' in html and '"@type": "FAQPage"' in html
    for shelf in entry["shelves"]:
        assert f'id="{shelf["key"]}"' in html
    assert "/static/ad-loader.js" in html and "/static/guest-list.js" in html
    assert "Festive 1 of 5" not in html


def test_members_get_add_buttons_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/holidays/thanksgiving").text
    assert html.count("data-season-add=") == 20 and html.count("data-season-add-shelf=") == 4
    assert 'data-season-progress="thanksgiving"' in html
    assert "/static/ad-loader.js" not in html and "/static/guest-list.js" not in html


def test_member_adds_picks_in_every_format(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    # An existing copy keeps its progress and rating.
    db_session.add(models.Podcast(user_id=user.id, title="serial", host="Someone", listened=True, rating=8))
    db_session.commit()
    before = authenticated_client.get("/api/seasonal/reading-and-listening/progress").json()
    assert before["total"] == 20 and before["tracked"] == 1 and before["done"] == 1

    ids = [seasonal.pool_entry(item)["id"] for item in LISTENING["shelves"][1]["picks"]]
    body = authenticated_client.post("/api/seasonal/reading-and-listening/add", json={"ids": ids}).json()
    assert [item["title"] for item in body["existing"]] == ["Serial"]
    assert len(body["added"]) == 4 and body["progress"]["tracked"] == 5
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id, title="The Thursday Murder Club").one()
    assert audiobook.author == "Richard Osman" and audiobook.narrator == "Lesley Manville" and not audiobook.listened
    manga = db_session.query(models.Manga).filter_by(user_id=user.id, title="Chi's Sweet Home").one()
    assert manga.author == "Konami Kanata" and manga.year == 2004
    podcasts = db_session.query(models.Podcast).filter_by(user_id=user.id).all()
    assert len(podcasts) == 1 and podcasts[0].rating == 8

    thanksgiving = [seasonal.pool_entry(item)["id"] for item in THANKSGIVING["shelves"][2]["picks"]]
    body = authenticated_client.post("/api/seasonal/thanksgiving/add", json={"ids": thanksgiving}).json()
    assert len(body["added"]) == 5
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Clue").one().director == "Jonathan Lynn"
    assert authenticated_client.post("/api/seasonal/thanksgiving/add", json={"ids": ids}).status_code == 404


def test_a_guest_saved_audiobook_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "audiobook", "slug": "the-hobbit-2020"}, {"kind": "movie", "slug": "clue-1985"}]})
    assert sorted(item["title"] for item in response.json()["added"]) == ["Clue", "The Hobbit"]
    audiobook = db_session.query(models.Audiobook).filter_by(title="The Hobbit").one()
    assert audiobook.narrator == "Andy Serkis" and audiobook.author == "J.R.R. Tolkien"


def test_guides_are_linked_from_the_hub_card_sitemap_and_loader(authenticated_client, client, monkeypatch):
    hub = client.get("/holidays").text
    for entry in GUIDES.values():
        assert f'href="{entry["path"]}"' in hub
        assert f"https://omnitrackr.xyz{entry['path']}</loc>" in client.get("/sitemap.xml").text
        assert f'href="{entry["path"]}"' in client.get("/site-map").text
    monkeypatch.setattr(seasonal, "current", lambda today=None: "holidays")
    from datetime import datetime
    from app import advent_calendar, friend_tools
    from app.routers import seasonal as seasonal_router
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: False)  # Pick swap's chip: test_friend_tools.py
    monkeypatch.delenv("ADVENT_CALENDAR_OPENS", raising=False)
    monkeypatch.setattr(advent_calendar, "_now", lambda: datetime(2026, 11, 20, 12))  # before the calendar opens
    monkeypatch.setattr(seasonal_router, "_today", lambda: date(2026, 11, 20))
    paths = [link["path"] for link in authenticated_client.get("/api/seasonal/current").json()["links"]]
    assert paths == ["/holidays/gifts", "/holidays/black-friday", "/holidays/christmas", "/holidays/thanksgiving",
                     "/holidays/reading-and-listening"]
    loader = (Path(__file__).parents[1] / "app" / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert "christmas|thanksgiving|reading-and-listening" in loader


def test_the_home_card_drops_black_friday_and_thanksgiving_once_they_are_over(monkeypatch):
    from datetime import datetime
    from app import advent_calendar
    from app.routers.seasonal import _card_links, extra_links
    monkeypatch.delenv("ADVENT_CALENDAR_OPENS", raising=False)
    monkeypatch.setattr(advent_calendar, "_now", lambda: datetime(2026, 12, 5, 12))
    november = [link["path"] for link in _card_links("holidays", date(2026, 11, 29))]
    assert "/holidays/black-friday" in november and "/holidays/thanksgiving" in november
    assert "/holidays/thanksgiving" not in [link["path"] for link in _card_links("holidays", date(2026, 11, 30))]
    december = _card_links("holidays", date(2026, 12, 5))
    paths = [link["path"] for link in december]
    assert "/holidays/black-friday" not in paths and "/holidays/thanksgiving" not in paths
    assert paths[0] == "/holidays/advent-calendar" and "/holidays/christmas" in paths
    assert all("until" not in link for link in december)
    # The guides' own cards keep both, after the ones still to come.
    cards = [link["path"] for link in extra_links("holidays", date(2026, 12, 5))]
    assert cards[-2:] == ["/holidays/black-friday", "/holidays/thanksgiving"]
    assert THANKSGIVING["until"] == "2026-11-29" and date.fromisoformat(THANKSGIVING["until"]).weekday() == 6


def test_edition_cards_say_this_month_only_for_this_month():
    from app.routers.seasonal import _companion_related, _related
    from html import unescape
    hub = unescape(_related("holidays", HUB, date(2026, 12, 10)))
    assert hub.index("december-2026") < hub.index("november-2026")
    assert "The November Discover edition" in hub and hub.count("This month's Discover edition") == 1
    # In January the guides beside the hub point to December, the season's last month, not November.
    january = unescape(_companion_related("christmas", CHRISTMAS, date(2027, 1, 15)))
    assert 'href="/discover/monthly/december-2026"' in january and "november-2026" not in january
    assert "The December Discover edition" in january and "This month's" not in january


def test_related_cards_link_back_and_follow_the_month():
    from app.routers.seasonal import _companion_related
    november = _companion_related("thanksgiving", THANKSGIVING, date(2026, 11, 10))
    assert 'href="/holidays"' in november and 'href="/holidays/gifts"' in november
    assert 'href="/holidays/reading-and-listening"' in november and 'href="/holidays/thanksgiving"' not in november
    assert 'href="/discover/monthly/november-2026"' in november
    december = _companion_related("reading-and-listening", LISTENING, date(2026, 12, 10))
    assert 'href="/discover/monthly/december-2026"' in december and "December 2026 challenge" in december


def test_december_edition_goes_live_on_the_first():
    edition = MONTHLY_EDITIONS["december-2026"]
    assert "december-2026" not in published_editions(date(2026, 11, 30))
    assert "december-2026" in published_editions(date(2026, 12, 1))
    assert len(edition["items"]) == 6 and len({item["category"] for item in edition["items"]}) == 6
    assert all(item["source"].startswith("https://") for item in edition["items"])
    others = {title_pages.slugify(item["title"]) for slug, other in MONTHLY_EDITIONS.items() if slug != "december-2026"
              for item in other["items"]}
    assert not others & {title_pages.slugify(item["title"]) for item in edition["items"]}


# ---------------------------------------------------------------- the Christmas guide

def _christmas_picks():
    return seasonal.picks(CHRISTMAS)


def test_christmas_new_releases_are_dated_and_on_the_calendar():
    calendar = CHRISTMAS["calendar"]
    assert calendar["after"] in {shelf["key"] for shelf in CHRISTMAS["shelves"]}
    rows = {row["title"]: row for row in calendar["items"]}
    assert len(rows) == len(calendar["items"]) >= 15
    for row in calendar["items"]:
        assert "2026-11-01" <= row["date"] <= "2026-12-31", row["title"]
        date.fromisoformat(row["date"])
        assert row["format"] and row["where"] and row["note"]
    dated = [item for item in _christmas_picks() if "release" in item]
    assert len(dated) == 5 and all(item["year"] == 2026 for item in dated)
    for item in dated:
        assert rows[item["title"]]["date"] == item["release"]["date"], item["title"]
        assert item["release"]["where"]
    # The older picks are older, and the plans and FAQ only name films that are on the calendar or the page.
    assert all(item["year"] < 2026 for item in _christmas_picks() if "release" not in item)
    assert CHRISTMAS["sources"] and all(url.startswith("https://") for _, url in CHRISTMAS["sources"])


def test_christmas_covers_six_formats_and_repeats_no_other_holiday_page():
    from app.advent_calendar_data import EDITIONS
    from app.deal_guides import GUIDE as DEALS_GUIDE
    assert {item["kind"] for item in _christmas_picks()} == {"movie", "tv", "book", "audiobook", "album", "game"}
    taken = {(door["kind"], title_pages.slugify(door["title"])) for door in EDITIONS[2026]["doors"]}
    taken |= {(item["kind"], title_pages.slugify(item["title"])) for section in DEALS_GUIDE["sections"]
              for item in section.get("picks", []) if item.get("title")}
    taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
              for item in MONTHLY_EDITIONS["december-2026"]["items"]}
    assert not keys(CHRISTMAS) & taken


def test_unreleased_christmas_films_are_saved_but_not_suggested_early():
    violent_night = pick.find("movie", "violent-night-2-2026")
    assert violent_night["source_url"] == "/holidays/christmas#new-this-year"
    assert violent_night["out"] == "2026-12-04"
    assert not pick.is_available(violent_night, date(2026, 12, 3))
    assert pick.is_available(violent_night, date(2026, 12, 4))
    assert pick.find("movie", "home-alone-1990")["out"] is None


def test_christmas_page_shows_the_calendar_dates_and_sources(client):
    html = client.get("/holidays/christmas").text
    assert 'id="release-calendar"' in html and 'href="#release-calendar"' in html
    assert html.count('class="sn-calendar__row') == len(CHRISTMAS["calendar"]["items"])
    assert html.count('class="sn-pick__release"') == 5
    # A calendar row for a pick on the page links down to it.
    assert '<a href="#pick-violent-night-2">Violent Night 2</a>' in html
    assert html.index('id="new-this-year"') < html.index('id="release-calendar"') < html.index('id="christmas-episodes"')
    assert "Sources we checked" in html and "https://www.avclub.com/doctor-who-christmas-special-2026-cancelled" in html
    assert "<span>New in 2026</span>" in html and "<span>December 24</span>" in html


def test_christmas_release_lines_follow_the_date():
    from app.routers.seasonal import _calendar_html, _release_line
    ebenezer = next(item for item in _christmas_picks() if item["title"] == "Ebenezer")
    assert ">Out November 13</time>" in _release_line(ebenezer, date(2026, 11, 12))
    assert ">Released November 13</time>" in _release_line(ebenezer, date(2026, 11, 20))
    early = _calendar_html(CHRISTMAS, date(2026, 10, 1))
    late = _calendar_html(CHRISTMAS, date(2027, 1, 1))
    assert "Out now" not in early and late.count("Out now") == len(CHRISTMAS["calendar"]["items"])
    assert early.index("November 2026") < early.index("December 2026")
