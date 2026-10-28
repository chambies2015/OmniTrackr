"""Weekly episodes in a member's private release calendar."""
import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app import episode_calendar, models, release_calendar
from app import release_radar as radar
from app.migrations import add_calendar_episodes_column

TODAY = date(2026, 10, 28)


@pytest.fixture
def pinned_today(monkeypatch):
    monkeypatch.setattr(radar, "today_utc", lambda: TODAY)
    return TODAY


def me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def unfold(body):
    return body.replace("\r\n ", "")


def feed_path(client):
    return client.post("/api/calendar").json()["links"]["url"].split("omnitrackr.xyz", 1)[1]


def tvmaze_show(show_id=7, name="Severance", status="Running"):
    return {"id": show_id, "name": name, "status": status, "premiered": "2022-02-18",
            "url": f"https://www.tvmaze.com/shows/{show_id}/severance", "webChannel": {"name": "Apple TV+"}}


def tvmaze_episode(season, number, day, airtime="21:00", name=None):
    stamp = f"{day.isoformat()}T01:00:00+00:00"
    return {"season": season, "number": number, "name": name or f"Episode {number}", "airdate": day.isoformat(),
            "airtime": airtime, "airstamp": stamp, "runtime": 50}


def store(db, category, title, year, data, status="ok"):
    db.add(models.TitleMetadata(key=episode_calendar.airing_key(category, title, year), status=status,
                                data=json.dumps(data) if data else None, fetched_at=datetime.utcnow()))
    db.commit()


def severance_schedule():
    return episode_calendar.tvmaze_episodes(tvmaze_show(), [
        tvmaze_episode(2, 4, TODAY - timedelta(days=30)),
        tvmaze_episode(2, 5, TODAY + timedelta(days=2), name="Trojan's Horse"),
        tvmaze_episode(2, 6, TODAY + timedelta(days=9), airtime=""),
        tvmaze_episode(0, 1, TODAY + timedelta(days=3)),
    ], TODAY)


# ---------------------------------------------------------------- parsing sources

def test_tvmaze_schedule_keeps_regular_episodes_in_range():
    data = severance_schedule()
    assert [(e["season"], e["number"]) for e in data["episodes"]] == [(2, 5), (2, 6)]
    first, second = data["episodes"]
    assert first["name"] == "Trojan's Horse" and first["start"] == f"{(TODAY + timedelta(days=2)).isoformat()}T01:00:00Z"
    assert second["name"] == "" and second["start"] is None  # no air time: an all-day entry
    assert data["network"] == "Apple TV+" and data["ended"] is False


def test_ended_show_with_nothing_upcoming_is_marked_ended():
    data = episode_calendar.tvmaze_episodes(tvmaze_show(status="Ended"), [tvmaze_episode(1, 1, date(2020, 1, 1))], TODAY)
    assert data["ended"] is True and data["episodes"] == []


def test_anilist_schedule_uses_exact_air_times():
    when = int(datetime(2026, 10, 31, 15, 30, tzinfo=timezone.utc).timestamp())
    data = episode_calendar.anilist_episodes({
        "id": 99, "siteUrl": "https://anilist.co/anime/99", "status": "RELEASING", "duration": 24,
        "title": {"english": "Frieren", "romaji": "Sousou no Frieren"},
        "airingSchedule": {"nodes": [{"episode": 12, "airingAt": when}, {"episode": "bad", "airingAt": when}]},
    }, TODAY)
    assert data["episodes"] == [{"season": None, "number": 12, "name": "", "date": "2026-10-31",
                                 "start": "2026-10-31T15:30:00Z", "minutes": 24}]


def test_anime_search_prefers_the_season_airing_now():
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": {"Page": {"media": [
                {"id": 1, "status": "FINISHED", "startDate": {"year": 2020}, "title": {"romaji": "Jujutsu Kaisen"},
                 "airingSchedule": {"nodes": []}},
                {"id": 2, "status": "RELEASING", "startDate": {"year": 2026}, "title": {"romaji": "Jujutsu Kaisen Season 3"},
                 "airingSchedule": {"nodes": [{"episode": 4, "airingAt": int(datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp())}]}},
            ]}}}

    class FakeClient:
        async def post(self, *args, **kwargs):
            return FakeResponse()

    data = asyncio.run(episode_calendar.fetch_anime(FakeClient(), "Jujutsu Kaisen", 2020, TODAY))
    assert data["source_id"] == 2 and data["show"] == "Jujutsu Kaisen Season 3"


# ---------------------------------------------------------------- the feed

def test_episodes_appear_in_a_new_members_feed(authenticated_client, db_session, pinned_today):
    user = me(db_session)
    db_session.add_all([
        models.TVShow(user_id=user.id, title="Severance", year=2022),
        models.TVShow(user_id=user.id, title="Finished Show", year=2020, watched=True),
    ])
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, severance_schedule())
    store(db_session, "tv-shows", "Finished Show", 2020, episode_calendar.tvmaze_episodes(
        tvmaze_show(8, "Finished Show"), [tvmaze_episode(1, 2, TODAY + timedelta(days=1))], TODAY))

    state = authenticated_client.post("/api/calendar").json()
    assert state["include_episodes"] is True and state["episodes_soon"] == 2
    body = unfold(authenticated_client.get(state["links"]["url"].split("omnitrackr.xyz", 1)[1]).text)
    assert "SUMMARY:Severance S2E5: Trojan's Horse" in body
    assert "SUMMARY:Severance S2E6" in body
    assert "UID:ep-tvm-7-s2e5@omnitrackr.xyz" in body
    start = TODAY + timedelta(days=2)
    assert f"DTSTART:{start.strftime('%Y%m%d')}T010000Z" in body and f"DTEND:{start.strftime('%Y%m%d')}T015000Z" in body
    assert f"DTSTART;VALUE=DATE:{(TODAY + timedelta(days=9)).strftime('%Y%m%d')}" in body
    assert "S2E4" not in body and "S0E1" not in body
    assert "Finished Show" not in body
    assert "URL:https://omnitrackr.xyz/titles/tv/severance-2022" in body
    assert "Air dates come from TVmaze" in body


def test_turning_episodes_off_and_on(authenticated_client, db_session, pinned_today):
    db_session.add(models.TVShow(user_id=me(db_session).id, title="Severance", year=2022))
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, severance_schedule())
    path = feed_path(authenticated_client)
    off = authenticated_client.put("/api/calendar/episodes", json={"enabled": False}).json()
    assert off["include_episodes"] is False and "episodes_soon" not in off
    assert "Severance S2E5" not in authenticated_client.get(path).text
    on = authenticated_client.put("/api/calendar/episodes", json={"enabled": True}).json()
    assert on["include_episodes"] is True and on["links"]["url"].endswith(path)
    assert "Severance S2E5" in unfold(authenticated_client.get(path).text)
    # A reset keeps the choice.
    assert authenticated_client.post("/api/calendar/reset").json()["include_episodes"] is True


def test_episodes_setting_needs_an_account(client):
    assert client.put("/api/calendar/episodes", json={"enabled": True}).status_code in (401, 403)


def test_a_premiere_already_on_the_radar_is_not_listed_twice(authenticated_client, db_session, pinned_today):
    db_session.add(models.TVShow(user_id=me(db_session).id, title="Severance", year=2022))
    db_session.commit()
    premiere = TODAY + timedelta(days=2)
    store(db_session, "tv-shows", "Severance", 2022, episode_calendar.tvmaze_episodes(tvmaze_show(), [
        tvmaze_episode(3, 1, premiere), tvmaze_episode(3, 2, premiere + timedelta(days=7))], TODAY))
    item = radar.make_item(category="tv", key="sev3", title="Severance", release_date=premiere.isoformat(),
                           source_url=None, popularity=1.0, save={"title": "Severance"})
    window = radar.current_window("tv", TODAY)
    item["window"] = window.slug
    radar.CACHE.entries[window.cache_key] = {"items": [item], "fetched_at": __import__("time").time(), "error": None}
    body = unfold(authenticated_client.get(feed_path(authenticated_client)).text)
    assert "Severance premieres" in body
    assert "S3E1" not in body and "S3E2" in body


def test_private_shelf_links_to_the_source_not_a_title_page(authenticated_client, db_session, pinned_today):
    user = me(db_session)
    user.tv_shows_private = True
    db_session.add(models.TVShow(user_id=user.id, title="Severance", year=2022, review="secret"))
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, severance_schedule())
    body = unfold(authenticated_client.get(feed_path(authenticated_client)).text)
    assert "URL:https://www.tvmaze.com/shows/7/severance" in body
    assert "/titles/tv/" not in body and "secret" not in body


def test_feeds_from_before_the_update_keep_their_contents(authenticated_client, db_session, pinned_today):
    db_session.add(models.TVShow(user_id=me(db_session).id, title="Severance", year=2022))
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, severance_schedule())
    path = feed_path(authenticated_client)
    # What the migration gives a feed made before this change.
    db_session.query(models.CalendarFeed).update({"include_episodes": False})
    db_session.commit()
    assert "Severance S2E5" not in authenticated_client.get(path).text
    assert authenticated_client.get("/api/calendar").json()["include_episodes"] is False


def test_migration_is_safe_to_run_twice():
    add_calendar_episodes_column()
    add_calendar_episodes_column()


# ---------------------------------------------------------------- refreshing

def test_refresh_fetches_only_stale_shows_of_subscribers(authenticated_client, db_session, monkeypatch, pinned_today):
    user = me(db_session)
    other = models.User(username="nocal", email="nocal@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    db_session.add_all([
        models.TVShow(user_id=user.id, title="Severance", year=2022),
        models.TVShow(user_id=user.id, title="Fresh Show", year=2021),
        models.TVShow(user_id=other.id, title="Not Subscribed", year=2021),
        models.CalendarFeed(user_id=user.id, token="tok-episodes", include_episodes=True),
    ])
    db_session.commit()
    store(db_session, "tv-shows", "Fresh Show", 2021, {"source_id": 3, "episodes": []})
    asked = []

    async def fake_fetch(client, title, year, today):
        asked.append(title)
        return episode_calendar.tvmaze_episodes(tvmaze_show(), [tvmaze_episode(2, 5, today + timedelta(days=1))], today)

    async def no_sleep(_):
        return None

    monkeypatch.setitem(episode_calendar.FETCHERS, "tv-shows", fake_fetch)
    monkeypatch.setattr(episode_calendar.asyncio, "sleep", no_sleep)
    bind = db_session.get_bind()
    from sqlalchemy.orm import sessionmaker
    count = asyncio.run(episode_calendar.refresh_members(sessionmaker(bind=bind), object(), today=TODAY))
    assert count == 1 and asked == ["Severance"]
    db_session.expire_all()
    row = db_session.query(models.TitleMetadata).filter_by(
        key=episode_calendar.airing_key("tv-shows", "Severance", 2022)).one()
    assert row.status == "ok" and json.loads(row.data)["episodes"][0]["number"] == 5


def test_a_failed_lookup_is_cached_as_an_error(db_session, monkeypatch, pinned_today):
    async def broken(client, title, year, today):
        raise RuntimeError("down")

    monkeypatch.setitem(episode_calendar.FETCHERS, "anime", broken)
    asyncio.run(episode_calendar.refresh_show(db_session, object(), "anime", "Frieren", 2023, TODAY))
    row = db_session.query(models.TitleMetadata).filter_by(key=episode_calendar.airing_key("anime", "Frieren", 2023)).one()
    assert row.status == "error"
    assert episode_calendar.stale(db_session, row.key) is False
