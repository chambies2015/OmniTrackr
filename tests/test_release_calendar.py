"""Release calendars: public Release Radar feeds and a member's private library feed."""
import time
from datetime import date, datetime, timedelta

import pytest

from app import models, release_calendar
from app import release_radar as radar

TODAY = date(2026, 10, 13)


@pytest.fixture
def pinned_today(monkeypatch):
    monkeypatch.setattr(radar, "today_utc", lambda: TODAY)
    return TODAY


def radar_item(category, key, title, day, popularity=10.0, **extra):
    return radar.make_item(category=category, key=key, title=title, release_date=day.isoformat(),
                           source_url=None, popularity=popularity, save={"title": title}, **extra)


def seed(items):
    by_window = {}
    for item in items:
        window = radar.current_window(item["category"], TODAY)
        item["window"] = window.slug
        by_window.setdefault(window.cache_key, []).append(item)
    for key, rows in by_window.items():
        radar.CACHE.entries[key] = {"items": rows, "fetched_at": time.time(), "error": None}


def me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def unfold(body):
    return body.replace("\r\n ", "")


# ---------------------------------------------------------------- iCalendar format

def test_calendar_text_is_valid_icalendar():
    event = release_calendar.event_for(radar_item("tv", "show-1", "Hello, World; Again", TODAY,
                                                  details=["Netflix"]))
    body = release_calendar.build_ics("Name", "Desc", [event], now=datetime(2026, 10, 13, 12, 0))
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "\n" not in body.replace("\r\n", "")
    flat = unfold(body)
    assert "SUMMARY:Hello\\, World\\; Again premieres" in flat
    assert "DTSTART;VALUE=DATE:20261013" in flat and "DTEND;VALUE=DATE:20261014" in flat
    assert "UID:tv-show-1@omnitrackr.xyz" in flat
    assert "URL:https://omnitrackr.xyz/release-radar/tv#item-show-1" in flat
    assert all(len(line.encode("utf-8")) <= 75 for line in body.split("\r\n"))


def test_long_lines_fold_without_splitting_characters():
    title = "Ōshi no Ko " * 20
    body = release_calendar.build_ics(title, "", [])
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    assert f"X-WR-CALNAME:{title}" in unfold(body)


# ---------------------------------------------------------------- public feeds

def test_section_feed_lists_dated_releases_in_range(client, pinned_today):
    seed([
        radar_item("tv", "a", "Soon Show", TODAY + timedelta(days=3)),
        radar_item("tv", "b", "Long Gone", TODAY - timedelta(days=40)),
        radar_item("movies", "c", "A Movie", TODAY + timedelta(days=2)),
    ])
    response = client.get("/calendar/release-radar/tv.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.headers["x-robots-tag"] == "noindex"
    body = unfold(response.text)
    assert "Soon Show premieres" in body
    assert "Long Gone" not in body
    assert "A Movie" not in body
    assert "X-WR-CALNAME:OmniTrackr TV premieres" in body


def test_highlights_feed_keeps_the_most_followed_per_section(client, pinned_today):
    items = [radar_item("tv", f"t{i}", f"Show {i:02d}", TODAY + timedelta(days=1), popularity=i) for i in range(30)]
    items.append(radar_item("games", "g", "Big Game", TODAY + timedelta(days=5)))
    seed(items)
    body = unfold(client.get("/calendar/release-radar.ics").text)
    assert body.count("BEGIN:VEVENT") == release_calendar.HIGHLIGHTS_PER_SECTION + 1
    assert "Show 29 premieres" in body and "Show 00 premieres" not in body
    assert "Big Game out" in body


def test_unknown_section_is_404(client):
    assert client.get("/calendar/release-radar/podcasts.ics").status_code == 404


def test_cold_cache_gives_a_valid_empty_calendar(client, pinned_today):
    response = client.get("/calendar/release-radar/anime.ics")
    assert response.status_code == 200
    assert "BEGIN:VEVENT" not in response.text
    assert response.headers["cache-control"] == "public, max-age=300"


# ---------------------------------------------------------------- member feed

def test_member_turns_on_a_private_feed_of_their_library(authenticated_client, db_session, pinned_today):
    assert authenticated_client.get("/api/calendar").json() == {"enabled": False}
    db_session.add_all([
        models.TVShow(user_id=me(db_session).id, title="Stranger Things"),
        models.Anime(user_id=me(db_session).id, title="Jujutsu Kaisen"),
    ])
    db_session.commit()
    seed([
        radar_item("tv", "st", "Stranger Things", TODAY + timedelta(days=10)),
        radar_item("anime", "jjk", "Jujutsu Kaisen Season 3", TODAY + timedelta(days=20)),
        radar_item("tv", "other", "Someone Else's Show", TODAY + timedelta(days=4)),
    ])
    state = authenticated_client.post("/api/calendar").json()
    assert state["enabled"] is True
    links = state["links"]
    assert links["webcal"].startswith("webcal://") and links["url"].startswith("https://")
    assert links["google"].startswith("https://calendar.google.com/calendar/r?cid=webcal%3A%2F%2F")
    path = links["url"].split("omnitrackr.xyz", 1)[1]

    feed = authenticated_client.get(path)
    assert feed.status_code == 200
    assert feed.headers["cache-control"] == "private, max-age=1800"
    body = unfold(feed.text)
    assert "Stranger Things premieres" in body and "In your library" in body
    assert "Jujutsu Kaisen Season 3 premieres" in body and "Because you track Jujutsu Kaisen" in body
    assert "Someone Else" not in body
    assert db_session.query(models.CalendarFeed).one().last_fetched_at is not None

    # Turning it on again keeps the same address.
    assert authenticated_client.post("/api/calendar").json()["links"]["url"] == links["url"]


def test_reset_and_turn_off_retire_the_old_address(authenticated_client, pinned_today):
    first = authenticated_client.post("/api/calendar").json()["links"]["url"].split("omnitrackr.xyz", 1)[1]
    second = authenticated_client.post("/api/calendar/reset").json()["links"]["url"].split("omnitrackr.xyz", 1)[1]
    assert first != second
    assert authenticated_client.get(first).status_code == 404
    assert authenticated_client.get(second).status_code == 200
    assert authenticated_client.delete("/api/calendar").json() == {"enabled": False}
    assert authenticated_client.get(second).status_code == 404


def test_feed_of_a_deactivated_member_stops(authenticated_client, db_session, pinned_today):
    path = authenticated_client.post("/api/calendar").json()["links"]["url"].split("omnitrackr.xyz", 1)[1]
    me(db_session).is_active = False
    db_session.commit()
    assert authenticated_client.get(path).status_code == 404


def test_feed_addresses_reject_junk_tokens(client):
    assert client.get("/calendar/u/feed-not-a-real-token.ics").status_code == 404
    assert client.get("/calendar/u/feed-" + "a" * 80 + ".ics").status_code == 404
    assert client.get("/calendar/u/feed-bad%20token.ics").status_code == 404


def test_tokens_that_look_like_scanner_paths_still_work(authenticated_client, db_session, pinned_today):
    authenticated_client.post("/api/calendar")
    feed = db_session.query(models.CalendarFeed).one()
    feed.token = "AdminPhpmyadmin_wp-admin"
    db_session.commit()
    assert authenticated_client.get("/calendar/u/feed-AdminPhpmyadmin_wp-admin.ics").status_code == 200


def test_calendar_setting_needs_an_account(client):
    assert client.get("/api/calendar").status_code == 401
    assert client.post("/api/calendar").status_code in (401, 403)


def test_feed_never_contains_private_library_fields(authenticated_client, db_session, pinned_today):
    db_session.add(models.TVShow(user_id=me(db_session).id, title="Severance", review="secret note", rating=9))
    db_session.commit()
    seed([radar_item("tv", "sev", "Severance", TODAY + timedelta(days=1))])
    path = authenticated_client.post("/api/calendar").json()["links"]["url"].split("omnitrackr.xyz", 1)[1]
    body = authenticated_client.get(path).text
    assert "secret note" not in body and "testuser" not in body and "test@example.com" not in body


# ---------------------------------------------------------------- Release Radar pages

def test_radar_pages_offer_calendar_subscriptions(client, pinned_today):
    hub = client.get("/release-radar").text
    assert 'href="webcal://omnitrackr.xyz/calendar/release-radar.ics"' in hub
    assert "https://calendar.google.com/calendar/r?cid=webcal%3A%2F%2Fomnitrackr.xyz%2Fcalendar%2Frelease-radar.ics" in hub
    assert "Members get a private calendar" in hub
    anime = client.get("/release-radar/anime").text
    assert 'href="webcal://omnitrackr.xyz/calendar/release-radar/anime.ics"' in anime
    assert "every show in this anime season and the next" in anime


def test_calendar_clicks_are_counted_anonymously(client):
    from app import funnel
    assert "calendar_subscribe_clicked" in funnel.CLIENT_EVENTS
    assert client.post("/api/funnel", json={"event": "calendar_subscribe_clicked"}).status_code == 204


def test_site_stats_count_private_calendars(authenticated_client, db_session, monkeypatch):
    for name in ("COLLECTION_MODERATOR_USERNAMES", "admin_usernames", "collection_moderator_usernames"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    user = me(db_session)
    other = models.User(username="calother", email="calother@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    now = datetime.utcnow()
    db_session.add_all([
        models.CalendarFeed(user_id=user.id, token="calfeed1", last_fetched_at=now - timedelta(days=1)),
        models.CalendarFeed(user_id=other.id, token="calfeed2", created_at=now - timedelta(days=60),
                            last_fetched_at=now - timedelta(days=20)),
    ])
    db_session.commit()
    response = authenticated_client.get("/api/site-stats/overview?days=30")
    assert response.status_code == 200
    assert response.json()["growth"]["calendar"] == {"feeds": 2, "new": 1, "refreshed_7d": 1}
    assert "calfeed1" not in response.text


def test_calendar_apps_can_check_feeds_with_head(client, pinned_today):
    response = client.head("/calendar/release-radar/games.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
