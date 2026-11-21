"""The Valentine's Day hub (/valentines-day): nine formats on every shelf, a romance scale, the 2027 calendar (Nov 2026)."""
from datetime import date
from pathlib import Path

import pytest

from app import models, new_releases, pick, seasonal, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.discover_catalog import MONTHLY_EDITIONS, published_editions
from app.holiday_guides import GUIDES as COMPANIONS
from app.seasonal_guides import SEASONS

VALENTINES = SEASONS["valentines"]


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def keys(items):
    return {(item["kind"], title_pages.slugify(item["title"])) for item in items}


def test_every_shelf_has_one_pick_in_each_of_the_nine_formats():
    assert VALENTINES["path"] == "/valentines-day" and VALENTINES["theme"] == "valentine"
    assert [shelf["key"] for shelf in VALENTINES["shelves"]] == ["date-night-in", "galentines", "table-for-one", "long-distance"]
    for shelf in VALENTINES["shelves"]:
        assert sorted(item["kind"] for item in shelf["picks"]) == sorted(title_pages.KINDS), shelf["key"]
        for item in shelf["picks"]:
            assert item["creator"], item["title"]
    assert len(seasonal.picks(VALENTINES)) == 36 == len(keys(seasonal.picks(VALENTINES)))
    assert [label for _, label, _ in VALENTINES["scale"]][0] == "Barely a love story"


def test_no_pick_repeats_the_february_edition_or_the_other_seasonal_pages():
    from app.advent_calendar_data import EDITIONS
    from app.discover_catalog import TRAILS
    taken = set()
    for slug, entry in SEASONS.items():
        if slug != "valentines":
            taken |= keys(seasonal.picks(entry))
    for entry in COMPANIONS.values():
        taken |= keys(seasonal.picks(entry))
    for edition in MONTHLY_EDITIONS.values():
        taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in edition["items"]}
    for trail in TRAILS.values():
        taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in trail["items"]}
    for edition in EDITIONS.values():
        taken |= {(door["kind"], title_pages.slugify(door["title"])) for door in edition["doors"]}
    assert not keys(seasonal.picks(VALENTINES)) & taken


def test_the_hub_is_written_for_2027_and_shows_in_the_first_half_of_february():
    assert seasonal.season_year(VALENTINES, date(2026, 11, 21)) == 2027
    assert seasonal.season_year(VALENTINES, date(2027, 2, 14)) == 2027
    assert seasonal.current(date(2027, 1, 31)) is None
    assert seasonal.current(date(2027, 2, 1)) == "valentines" and seasonal.current(date(2027, 2, 15)) == "valentines"
    assert seasonal.current(date(2027, 2, 16)) is None
    assert seasonal.days_left(VALENTINES, date(2027, 2, 14)) == 1
    # 2027 facts the page leans on: Valentine's Day is a Sunday and Presidents' Day is the Monday after it.
    assert date(2027, 2, 14).strftime("%A") == "Sunday" and date(2027, 2, 13).strftime("%A") == "Saturday"
    mondays = [day for day in range(1, 29) if date(2027, 2, day).weekday() == 0]
    assert mondays[2] == 15


def test_every_pick_can_be_saved_and_only_six_formats_join_pick_for_me():
    for item in seasonal.picks(VALENTINES):
        pooled = seasonal.pool_entry(item)
        assert pooled is not None, item["title"]
        if item["kind"] in seasonal.EXTRA_KINDS:
            assert seasonal.find_extra(item["kind"], pooled["slug"])[1]["title"] == item["title"]
        else:
            assert pick.find_id(pooled["id"]) is pooled
    moonstruck = pick.find("movie", "moonstruck-1987")
    assert moonstruck["source_label"] == "Valentine's Day picks" and moonstruck["source_url"] == "/valentines-day#date-night-in"
    assert not any(entry["kind"] in seasonal.EXTRA_KINDS for entry in pick.pool())


def test_calendar_rows_are_dated_and_link_to_release_guides_that_exist():
    calendar = VALENTINES["calendar"]
    assert calendar["after"] == "long-distance" and len(calendar["items"]) >= 5
    for row in calendar["items"]:
        assert "2027-01-01" <= row["date"] <= "2027-02-28", row["title"]
        assert row["format"] and row["where"] and row["note"]
        if row.get("href"):
            path, anchor = row["href"].split("#")
            slug = path.removeprefix(new_releases.BASE_PATH + "/")
            guide = new_releases.GUIDES[slug]
            found = next(item for item in new_releases.picks(guide) if new_releases.anchor_id(item) == anchor)
            assert found["date"] == row["date"], row["title"]
    assert all(url.startswith("https://") for _, url in VALENTINES["sources"])


def test_hub_reads_completely_without_an_account(client):
    response = client.get("/valentines-day")
    assert response.status_code == 200
    html = response.text
    assert '<link rel="canonical" href="https://omnitrackr.xyz/valentines-day">' in html and "noindex" not in html
    assert "<h1>Valentine&#x27;s Day, as romantic as you like</h1>" in html
    assert 'data-season-theme="valentine"' in html and "SEASONAL · VALENTINE&#x27;S DAY 2027" in html
    assert html.count('class="pick sn-pick"') == 36 and html.count("data-guest-kind=") == 36
    assert 'data-guest-kind="audiobook" data-guest-slug="the-time-traveler-s-wife-2003"' in html
    assert "Romance 5 of 5 · Hearts everywhere" in html and "How romantic is it?" in html
    assert "Six kinds of Valentine&#x27;s Day" in html and "Sources we checked" in html
    assert 'id="new-for-valentines"' in html and 'href="#new-for-valentines"' in html
    assert html.index('id="long-distance"') < html.index('id="new-for-valentines"') < html.index('id="plan"')
    assert html.count('class="sn-calendar__row') == len(VALENTINES["calendar"]["items"])
    assert '<a href="/new-releases/winter-2027-movies#pick-remain">Remain</a>' in html
    assert '"FAQPage"' in html and "/static/ad-loader.js" in html and "/static/guest-list.js" in html
    assert "Fright" not in html and "Festive" not in html


def test_related_cards_wait_for_the_february_edition_and_challenge():
    from app.routers.seasonal import _related
    november = _related("valentines", VALENTINES, date(2026, 11, 21))
    assert 'href="/discover/one-evening-well-spent"' in november and 'href="/holidays"' in november
    assert "february-2027" not in november
    assert "february-2027" not in published_editions(date(2027, 1, 31))
    february = _related("valentines", VALENTINES, date(2027, 2, 1))
    assert 'href="/discover/monthly/february-2027"' in february and "February 2027 challenge" in february


def test_members_add_a_shelf_in_every_format_and_the_card_shows_it(authenticated_client, db_session, monkeypatch):
    monkeypatch.setattr(seasonal, "current", lambda today=None: "valentines")
    html = authenticated_client.get("/valentines-day").text
    assert html.count("data-season-add=") == 36 and html.count("data-season-add-shelf=") == 4
    assert 'data-season-progress="valentines"' in html and "/static/ad-loader.js" not in html
    ids = [seasonal.pool_entry(item)["id"] for item in VALENTINES["shelves"][3]["picks"]]
    body = authenticated_client.post("/api/seasonal/valentines/add", json={"ids": ids}).json()
    assert len(body["added"]) == 9 and body["progress"]["tracked"] == 9 and body["progress"]["total"] == 36
    user = db_session.query(models.User).filter_by(username="testuser").one()
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id, title="The Time Traveler's Wife").one()
    assert audiobook.author == "Audrey Niffenegger" and not audiobook.listened
    assert db_session.query(models.Manga).filter_by(user_id=user.id, title="A Sign of Affection").one()
    assert db_session.query(models.Podcast).filter_by(user_id=user.id, title="Alice Isn't Dead").one()
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Like Crazy").one().director == "Drake Doremus"
    card = authenticated_client.get("/api/seasonal/current").json()
    assert card["season"] == "valentines" and card["theme"] == "valentine" and card["cta"] == "Find your romance level"
    assert card["tracked"] == 9 and card["total"] == 36 and len(card["shelves"]) == 4
    assert [link["path"] for link in card["links"]] == ["/discover/one-evening-well-spent", "/discover/weather-and-windows"]


def test_a_guest_saved_manga_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "manga", "slug": "wotakoi-love-is-hard-for-otaku-2014"}, {"kind": "movie", "slug": "moonstruck-1987"}]})
    assert sorted(item["title"] for item in response.json()["added"]) == ["Moonstruck", "Wotakoi: Love Is Hard for Otaku"]


def test_hub_is_linked_from_the_sitemap_loader_and_other_hubs(client):
    assert "https://omnitrackr.xyz/valentines-day</loc>" in client.get("/sitemap.xml").text
    assert 'href="/valentines-day"' in client.get("/site-map").text
    assert "/valentines-day" in client.get("/llms.txt").text
    assert 'href="/valentines-day"' in client.get("/holidays").text
    loader = (Path(__file__).parents[1] / "app" / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert "/^\\/valentines-day$/" in loader
    css = (Path(__file__).parents[1] / "app" / "static" / "seasonal-card.css").read_text(encoding="utf-8")
    assert '.season-card[data-season-theme="valentine"]' in css
