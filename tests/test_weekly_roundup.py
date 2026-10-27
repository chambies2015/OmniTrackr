"""New this week: weekly release roundups built from Release Radar and anonymous member totals."""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest

from app import models
from app import release_radar as radar
from app import weekly_roundup as roundup
from app.routers import weekly_roundup as roundup_pages
from tests.release_radar_fixtures import install_fixture_providers

TODAY = date(2026, 10, 1)  # A Thursday: the current week starts Monday, September 28.
WEEK = date(2026, 9, 28)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def fixtures(monkeypatch):
    roundup_pages.clear_cache()
    yield install_fixture_providers(today=TODAY, monkeypatch=monkeypatch)
    roundup_pages.clear_cache()


def _user(db, name, **private):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, is_active=True, **private)
    db.add(user)
    db.flush()
    return user


def _finish(db, user, category, title, model, when, rating=None, year=2026, **extra):
    item = model(user_id=user.id, title=title, rating=rating, added_at=when, **extra)
    if hasattr(item, "year"):
        item.year = year
    db.add(item)
    db.flush()
    db.add(models.ActivityEntry(user_id=user.id, category=category, item_id=item.id, title=title, action="completed",
                                rating=rating, source="automatic", occurred_at=when))
    return item


# ---------------------------------------------------------------- weeks

def test_week_slugs_and_labels():
    assert roundup.parse_slug("2026-10-26") == date(2026, 10, 26)
    assert roundup.parse_slug("2026-10-27") is None  # Not a Monday.
    assert roundup.parse_slug("2026-1-26") is None
    assert roundup.parse_slug("../admin") is None
    assert roundup.monday_of(date(2026, 11, 1)) == date(2026, 10, 26)
    assert roundup.label(date(2026, 10, 26)) == "October 26 to November 1, 2026"
    assert roundup.label(date(2026, 10, 5)) == "October 5 to 11, 2026"
    assert roundup.label(date(2026, 12, 28)) == "December 28, 2026 to January 3, 2027"
    assert roundup.path(date(2026, 10, 26)) == "/new-this-week/2026-10-26"
    assert roundup.status(WEEK, TODAY) == "current"
    assert roundup.status(WEEK - timedelta(days=7), TODAY) == "past"
    assert roundup.status(WEEK + timedelta(days=7), TODAY) == "future"


def test_a_week_across_two_months_reads_both_radar_periods():
    windows = roundup.windows_for_week("movies", WEEK, TODAY)
    assert [w.slug for w in windows] == ["2026-09", "2026-10"]
    # Far outside Release Radar's range: nothing to build from.
    assert roundup.windows_for_week("movies", date(2026, 3, 2), TODAY) is None


# ---------------------------------------------------------------- building

def test_roundup_is_built_from_the_cache_and_saved(fixtures, db_session):
    payload = run(roundup.ensure(object(), db_session, WEEK, today=TODAY))
    assert payload["week_start"] == "2026-09-28"
    titles = {i["title"] for c in radar.CATEGORY_ORDER for i in roundup.releases(payload, c)}
    assert "Digger" in titles and "East of Eden" in titles
    for category in radar.CATEGORY_ORDER:
        for item in roundup.releases(payload, category):
            assert "2026-09-28" <= item["date"] < "2026-10-05"
    row = roundup.load(db_session, WEEK)
    assert row is not None and not row.final
    # Not due again yet: the saved copy comes back without a rebuild.
    built_at = row.built_at
    run(roundup.ensure(object(), db_session, WEEK, today=TODAY))
    assert roundup.load(db_session, WEEK).built_at == built_at


def test_a_finished_week_is_made_final_and_never_rebuilt(fixtures, db_session, monkeypatch):
    later = WEEK + timedelta(days=7 + roundup.FINAL_AFTER_DAYS)
    monkeypatch.setattr(radar, "today_utc", lambda: later)
    payload = run(roundup.ensure(object(), db_session, WEEK, today=later))
    assert payload is not None and roundup.load(db_session, WEEK).final
    frozen = roundup.load(db_session, WEEK).payload

    async def nothing(client, window):
        return []
    for category in radar.CATEGORY_ORDER:
        monkeypatch.setitem(radar.PROVIDERS, category, nothing)
    monkeypatch.setattr(radar, "CACHE", radar.RadarCache(None))
    run(roundup.ensure(object(), db_session, WEEK, today=later + timedelta(days=30)))
    roundup.save(db_session, WEEK, {"releases": {}}, final=False)
    assert roundup.load(db_session, WEEK).payload == frozen


def test_a_cold_cache_saves_nothing(db_session):
    assert run(roundup.ensure(None, db_session, roundup.current_monday(), wait=0)) is None
    assert roundup.load(db_session, roundup.current_monday()) is None


# ---------------------------------------------------------------- members

def test_member_totals_are_anonymous_and_respect_private_categories(db_session):
    when = datetime(2026, 9, 30, 20, 0)
    a, b, c = _user(db_session, "ann"), _user(db_session, "bob"), _user(db_session, "cat")
    hidden = _user(db_session, "dee", movies_private=True)
    from app.editorial_collections import EDITOR_USERNAME
    editor = _user(db_session, EDITOR_USERNAME)
    for user, rating in ((a, 9), (b, 8), (c, 7)):
        _finish(db_session, user, "movies", "Arrival", models.Movie, when, rating=rating)
    _finish(db_session, hidden, "movies", "Secret Film", models.Movie, when)
    _finish(db_session, a, "movies", "Secret Film", models.Movie, when)
    _finish(db_session, editor, "movies", "Secret Film", models.Movie, when)
    _finish(db_session, b, "movies", "Only Me", models.Movie, when)
    _finish(db_session, c, "movies", "Last Week", models.Movie, when - timedelta(days=7))
    db_session.commit()

    members = roundup.member_activity(db_session, WEEK)
    names = [row["title"] for row in members["finished"]]
    assert names == ["Arrival"]
    assert members["finished"][0]["members"] == 3 and members["finished"][0]["average"] == 8.0
    assert members["finishers"] == 3
    assert [row["title"] for row in members["added"]] == ["Arrival"]
    text = " ".join(roundup.member_paragraphs(members, "current"))
    assert "Arrival" in text and "ann" not in text and "Secret Film" not in text and "Only Me" not in text


# ---------------------------------------------------------------- write-up

def _payload(n_per_category=5):
    releases = {}
    for category in radar.CATEGORY_ORDER:
        items = []
        for n in range(n_per_category):
            day = (WEEK + timedelta(days=n % 7)).isoformat()
            details = {"movies": [f"Directed by Director {n}"], "tv": [f"Streaming on Service {n % 2}"],
                       "anime": [f"Made by Studio {n % 2}", "Adapted from manga"], "games": []}[category]
            items.append(roundup._slim(radar.make_item(
                category=category, key=f"{category}-{n}", title=f"{category.title()} Title {n}", release_date=day,
                source_url=None, genres=["Drama", "Horror"] if n % 2 else ["Horror"], details=details,
                badges=["New series"] if category == "tv" and n % 2 else (["Sequel"] if category == "anime" and n == 0 else []),
                platforms=["PC", "PlayStation 5", "Nintendo Switch 2"] if category == "games" else [],
                popularity=100 - n, save={"title": f"{category.title()} Title {n}", "year": 2026})))
        releases[category] = items
    return {"version": 1, "week_start": WEEK.isoformat(), "built_at": "2026-10-01T10:00:00Z", "complete": True,
            "releases": releases, "counts": {"movies": {"movies-0": 4}}, "members": {"finishers": 0, "finished": [], "added": []}}


def test_write_up_names_specifics_and_compares_weeks():
    payload = _payload()
    previous = dict(_payload(3), week_start=(WEEK - timedelta(days=7)).isoformat())
    lead = " ".join(roundup.lead_paragraphs(payload, previous, "current"))
    assert "September 28 to October 4, 2026" in lead
    assert "20 releases" in lead and "8 more than the week of September 21" in lead
    assert "horror is the most common genre" in lead
    movies = " ".join(roundup.category_paragraphs("movies", roundup.releases(payload, "movies"), payload["counts"]["movies"], "current"))
    assert "Movies Title 0" in movies and "Director 0" in movies and "4 libraries" in movies
    past = " ".join(roundup.category_paragraphs("games", roundup.releases(payload, "games"), {}, "past"))
    assert "was Games Title 0" in past and "PlayStation 5" in past
    assert roundup.writeup_words(payload, previous, "current") >= roundup.MIN_INDEX_WORDS
    assert roundup.is_indexable(payload, WEEK, TODAY)


def test_thin_weeks_stay_out_of_the_index():
    thin = _payload(2)
    assert not roundup.is_indexable(thin, WEEK, TODAY)  # 8 releases
    one_format = _payload(6)
    one_format["releases"] = {"movies": one_format["releases"]["movies"] * 3}
    assert not roundup.is_indexable(one_format, WEEK, TODAY)


# ---------------------------------------------------------------- pages

def test_this_week_redirects_to_the_dated_page(client, fixtures):
    response = client.get("/new-this-week", follow_redirects=False)
    assert response.status_code == 302 and response.headers["location"] == "/new-this-week/2026-09-28"


def test_week_page_renders_releases_write_up_and_links(client, fixtures):
    response = client.get("/new-this-week/2026-09-28")
    assert response.status_code == 200
    html = response.text
    assert "New this week: movies, TV, anime and games for September 28 to October 4, 2026" in html
    assert "Digger" in html and "East of Eden" in html
    assert "The week of September 28 to October 4, 2026 brings" in html
    assert 'href="/new-this-week/archive"' in html and 'href="/release-radar/movies' in html
    assert "How this roundup is made" in html and "TVmaze" in html
    assert 'data-radar-add=' in html  # Still on the radar, so members can track from here.
    assert '"@type": "Article"' in html
    # The fixtures hold fewer than 12 releases that week: a thin page stays out of search.
    assert 'content="noindex, follow"' in html
    assert "ad-loader.js" not in html


def test_week_page_is_indexed_and_in_the_sitemap_once_it_has_enough(client, fixtures, monkeypatch):
    monkeypatch.setattr(roundup, "MIN_INDEX_RELEASES", 3)
    monkeypatch.setattr(roundup, "MIN_INDEX_WORDS", 40)
    html = client.get("/new-this-week/2026-09-28").text
    assert 'content="index, follow, max-image-preview:large"' in html
    sitemap = client.get("/sitemap.xml").text
    assert "/new-this-week/2026-09-28</loc>" in sitemap and "/new-this-week/archive</loc>" in sitemap


def test_unknown_future_and_malformed_weeks_are_not_found(client, fixtures):
    assert client.get("/new-this-week/2026-10-05").status_code == 404  # Next week.
    assert client.get("/new-this-week/2026-09-29").status_code == 404  # Not a Monday.
    assert client.get("/new-this-week/2025-01-06").status_code == 404  # Never saved, off the radar.
    assert client.get("/new-this-week/latest").status_code == 404


def test_archive_lists_saved_weeks(client, fixtures, db_session):
    payload = _payload(4)
    payload["week_start"] = "2026-09-21"
    roundup.save(db_session, date(2026, 9, 21), payload, final=True)
    html = client.get("/new-this-week/archive").text
    assert "Week of September 21 to 27, 2026" in html
    assert "Week of September 28 to October 4, 2026" in html  # This week is saved on the way.
    assert 'href="/new-this-week/2026-09-21"' in html
    # A saved past week renders from its snapshot, without Release Radar.
    week = client.get("/new-this-week/2026-09-21")
    assert week.status_code == 200 and "Movies Title 0" in week.text
    assert "New releases for the week of September 21 to 27, 2026" in week.text


def test_a_past_week_off_the_radar_hides_tracking_but_keeps_the_cards(client, fixtures, db_session):
    payload = _payload(4)
    for category in radar.CATEGORY_ORDER:
        for item in payload["releases"][category]:
            item["window"] = "2025-01"
    payload["week_start"] = "2026-09-21"
    roundup.save(db_session, date(2026, 9, 21), payload, final=True)
    html = client.get("/new-this-week/2026-09-21").text
    assert "Movies Title 0" in html and "data-radar-add=" not in html


def test_roundup_links_from_radar_footer_and_site_map(client, fixtures):
    assert 'href="/new-this-week"' in client.get("/release-radar").text
    assert 'href="/new-this-week"' in client.get("/site-map").text
    llms = client.get("/llms.txt").text
    assert "/new-this-week" in llms


def test_saved_payload_holds_no_member_names(client, fixtures, db_session):
    when = datetime(2026, 9, 30, 20, 0)
    names = ("zqmemberone", "zqmembertwo", "zqmemberthree")
    for name in names:
        _finish(db_session, _user(db_session, name), "movies", "Arrival", models.Movie, when, rating=8)
    db_session.commit()
    client.get("/new-this-week/2026-09-28")
    stored = roundup.load(db_session, WEEK).payload
    data = json.loads(stored)
    assert data["members"]["finished"][0]["title"] == "Arrival"
    for name in (*names, "@example.com", "user_id"):
        assert name not in stored


def test_background_save_builds_every_week_the_radar_still_covers(fixtures, db_session):
    from tests.conftest import TestingSessionLocal
    saved = run(roundup_pages.save_recent_weeks(object(), TestingSessionLocal, today=TODAY))
    assert saved >= 2
    assert roundup.load(db_session, WEEK) is not None
