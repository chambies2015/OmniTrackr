"""What's new on the home screen: episodes, releases and friends since the last visit (Nov 2026)."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from app import dashboard_assets, episode_calendar, home_today, models, title_metadata
from tests.test_title_pages import add_movie, member

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
NOW = datetime(2026, 11, 15, 18, 0)
TODAY = NOW.date()


def _show(db, user, title="Severance", year=2022, watched=False, model=models.TVShow):
    show = model(user_id=user.id, title=title, year=year, watched=watched)
    db.add(show)
    db.flush()
    return show


def _schedule(db, category, title, year, episodes, **extra):
    title_metadata.store(db, episode_calendar.airing_key(category, title, year),
                         {"show": title, "source_id": 1, "episodes": episodes, **extra}, "ok")


def _friends(db, a, b):
    low, high = sorted([a.id, b.id])
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.flush()


def _day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


def test_new_episode_waits_when_saved_progress_is_behind(db_session):
    me = member(db_session, "maya")
    show = _show(db_session, me)
    db_session.add(models.ProgressCheckpoint(user_id=me.id, category="tv-shows", item_id=show.id,
                                             unit="episode", season=2, position=6))
    _schedule(db_session, "tv-shows", "Severance", 2022, [
        {"season": 2, "number": 6, "date": _day(-9)},
        {"season": 2, "number": 7, "name": "Chikhai Bardo", "date": _day(-2)},
        {"season": 2, "number": 8, "date": _day(5)},
        {"season": 2, "number": 9, "date": _day(12)},
    ], network="Apple TV+")
    db_session.commit()

    data = home_today.build(db_session, me, since=NOW - timedelta(days=3), now=NOW)
    [entry] = data["shows"]
    assert entry["out"] == {"code": "S2 E7", "date": _day(-2), "name": "Chikhai Bardo", "new": True, "waiting": True}
    assert entry["next"]["code"] == "S2 E8"  # the closest one, never past next week
    assert entry["progress"] == "S2 E6" and entry["network"] == "Apple TV+"
    assert data["counts"]["episodes"] == 1 and data["counts"]["waiting"] == 1 and data["counts"]["soon"] == 1


def test_episode_seen_before_last_visit_is_not_new_and_caught_up_is_not_waiting(db_session):
    me = member(db_session, "maya")
    show = _show(db_session, me, title="Frieren", year=2023, model=models.Anime)
    db_session.add(models.ProgressCheckpoint(user_id=me.id, category="anime", item_id=show.id,
                                             unit="episode", position=15))
    _schedule(db_session, "anime", "Frieren", 2023, [{"number": 15, "date": _day(-4)}])
    db_session.commit()

    [entry] = home_today.build(db_session, me, since=NOW - timedelta(days=1), now=NOW)["shows"]
    assert entry["out"]["code"] == "Episode 15"
    assert entry["out"]["new"] is False and entry["out"]["waiting"] is False


def test_finished_hidden_and_other_peoples_shows_stay_out(db_session):
    me = member(db_session, "maya")
    other = member(db_session, "sam")
    _show(db_session, me, title="Shogun", year=2024, watched=True)
    _show(db_session, me, title="Frieren", year=2023, model=models.Anime)
    _show(db_session, other, title="The Bear", year=2022)
    for category, title, year in (("tv-shows", "Shogun", 2024), ("anime", "Frieren", 2023), ("tv-shows", "The Bear", 2022)):
        _schedule(db_session, category, title, year, [{"season": 1, "number": 3, "date": _day(0)}])
    me.anime_visible = False
    db_session.commit()

    assert home_today.build(db_session, me, now=NOW)["shows"] == []


def test_releases_come_from_alerts_already_sent(db_session):
    me = member(db_session, "maya")
    db_session.add_all([
        models.ReleaseAlert(user_id=me.id, category="movies", item_key="a", title="Wicked: For Good", release_date=TODAY - timedelta(days=1)),
        models.ReleaseAlert(user_id=me.id, category="video-games", item_key="b", title="Old Game", release_date=TODAY - timedelta(days=30)),
        models.ReleaseAlert(user_id=member(db_session, "sam").id, category="movies", item_key="a", title="Someone else's", release_date=TODAY),
    ])
    db_session.commit()

    data = home_today.build(db_session, me, since=NOW - timedelta(days=3), now=NOW)
    assert [(r["title"], r["new"]) for r in data["releases"]] == [("Wicked: For Good", True)]
    assert data["counts"]["releases"] == 1


def test_friends_part_reuses_the_friends_feed_and_counts_since_last_visit(db_session):
    me = member(db_session, "maya")
    friend = member(db_session, "jordan")
    stranger = member(db_session, "sam")
    _friends(db_session, me, friend)
    add_movie(db_session, friend, title="The Substance", year=2024, added_at=NOW - timedelta(hours=3))
    add_movie(db_session, friend, title="Heat", year=1995, added_at=NOW - timedelta(days=5))
    add_movie(db_session, stranger, title="Alien", year=1979, added_at=NOW - timedelta(hours=1))
    db_session.commit()

    part = home_today.build(db_session, me, since=NOW - timedelta(days=1), now=NOW)["friends"]
    assert [item["title"] for item in part["items"]] == ["The Substance", "Heat"]
    assert part["new"] == 1 and part["friends"] == 1


def test_since_is_clamped_to_the_last_thirty_days_and_never_the_future(db_session):
    assert home_today.clamp_since(None, NOW) == NOW - timedelta(days=7)
    assert home_today.clamp_since(NOW - timedelta(days=90), NOW) == NOW - timedelta(days=30)
    assert home_today.clamp_since(NOW + timedelta(days=2), NOW) == NOW
    from datetime import timezone
    aware = datetime(2026, 11, 15, 12, 0, tzinfo=timezone(timedelta(hours=-6)))
    assert home_today.clamp_since(aware, NOW) == datetime(2026, 11, 15, 18, 0)


def test_endpoint_needs_sign_in_and_is_private(client, authenticated_client):
    response = authenticated_client.get("/api/home/today?since=2026-11-10T08:00:00.000Z")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    data = response.json()
    assert set(data) == {"since", "shows", "releases", "friends", "counts"}
    assert authenticated_client.get("/api/home/today?since=not-a-date").status_code == 200

    authenticated_client.cookies.clear()
    authenticated_client.headers.pop("Authorization", None)
    assert authenticated_client.get("/api/home/today").status_code == 401


def test_endpoint_asks_for_missing_schedules_in_the_background(authenticated_client, db_session, monkeypatch):
    me = db_session.query(models.User).filter_by(username="testuser").one()
    _show(db_session, me)
    db_session.commit()
    asked = []
    monkeypatch.setattr(episode_calendar, "queue_member", lambda app, user_id: asked.append(user_id))
    assert authenticated_client.get("/api/home/today").status_code == 200
    assert asked == [me.id]


def test_card_sits_after_continue_and_year_so_far_moves_to_the_rail():
    main = INDEX[INDEX.index('<div class="home-board__main">'):INDEX.index('<aside class="home-board__rail"')]
    order = [main.index(f'id="{card}"') for card in ("libraryPulse", "homeNews", "nextUpQueue", "onThisDay")]
    assert order == sorted(order)
    assert '<section id="homeNews" class="home-news" aria-labelledby="homeNewsTitle" hidden>' in main
    rail = INDEX[INDEX.index('<aside class="home-board__rail"'):INDEX.index("</aside>", INDEX.index('<aside class="home-board__rail"'))]
    assert rail.index('id="yearSoFar"') < rail.index('id="seasonCard"')
    assert 'id="homeHeroNews"' in INDEX


def test_script_loads_and_the_dashboard_refreshes_and_resets_it():
    assert re.search(r'<script src="/static/home-today\.js\?v=[\w-]+"></script>', INDEX)
    source = dashboard_assets.full_source()
    assert "window.OmniHomeToday?.refresh()" in source
    assert "window.OmniHomeToday?.reset()" in source
