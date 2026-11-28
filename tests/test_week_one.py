"""The first-week home card: a new member's week, shows airing now, the one reminder email, counters."""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest

from app import auth, digest, episode_calendar, models, stay_posted, week_one
from app.routers import week_one as week_one_router
from app.site_traffic import RECORDER
from tests.test_merge_sweep_nov16b import _limited

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    week_one._POOL.clear()
    RECORDER._pending.clear()
    yield
    week_one._POOL.clear()
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "weekone" and name == key)


def today():
    return week_one._now().date()


def member(db, name="nova", days_old=0, verified=True, private_tv=False):
    # A few minutes in the past, but never so far that it lands on the day before (in the first
    # minutes after midnight UTC, "5 minutes ago" is yesterday and the card counts one day more).
    created = datetime.utcnow() - timedelta(days=days_old)
    created -= min(timedelta(minutes=5), created - created.replace(hour=0, minute=0, second=0, microsecond=0))
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=verified, is_active=True, created_at=created, tv_shows_private=private_tv)
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def schedule(db, category, title, year, days_ahead, number=3, season=2, show=None):
    key = episode_calendar.airing_key(category, title, year)
    data = {"source": "TVmaze", "source_id": abs(hash(key)) % 10000, "show": show or title, "network": "HBO", "ended": False,
            "episodes": [{"season": season if category == "tv-shows" else None, "number": number, "name": "",
                          "date": (today() + timedelta(days=d)).isoformat(), "start": None, "minutes": None}
                         for d in ([days_ahead] if isinstance(days_ahead, int) else days_ahead)]}
    db.add(models.TitleMetadata(key=key, data=json.dumps(data), status="ok", fetched_at=datetime.utcnow()))
    db.commit()
    return key


def card(client, user):
    response = client.get(f"/api/week-one?today={today().isoformat()}", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()["card"]


def test_only_new_members_with_a_title_see_it(client, db_session):
    empty = member(db_session, "empty")
    assert card(client, empty) is None  # the launchpad handles an empty library
    old = member(db_session, "old", days_old=9)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=old.id))
    fresh = member(db_session, "fresh", days_old=3)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=fresh.id))
    db_session.commit()
    assert card(client, old) is None
    found = card(client, fresh)
    assert found["day"] == 4 and len(found["days"]) == 7 and found["count"] == 0
    assert found["days"][0]["date"] == today().isoformat()


def test_week_lists_episodes_of_unfinished_shows(client, db_session):
    user = member(db_session)
    db_session.add_all([
        models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id),
        models.TVShow(title="Lost", year=2004, watched=True, user_id=user.id),
    ])
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, [2, 9])
    schedule(db_session, "tv-shows", "Lost", 2004, 1)
    found = card(client, user)
    assert found["count"] == 1
    day = found["days"][2]
    assert [item["title"] for item in day["items"]] == ["Severance"]
    assert day["items"][0]["what"] == "S2 E3" and day["items"][0]["url"].startswith("/titles/tv/")
    assert found["remind_day"] == day["date"]
    assert found["offer"] == {"email": True, "push": True}


def test_private_shelf_items_have_no_public_link(client, db_session):
    user = member(db_session, private_tv=True)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 1)
    item = card(client, user)["days"][1]["items"][0]
    assert item["url"] is None and item["item_id"]


def test_suggestions_come_from_shared_shelves_and_skip_owned(client, db_session):
    user = member(db_session)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=user.id))
    others = [member(db_session, f"m{i}", days_old=40) for i in range(3)]
    hidden = member(db_session, "hush", days_old=40, private_tv=True)
    for other in others:
        db_session.add(models.TVShow(title="Andor", year=2022, watched=False, poster_url="https://img.example/andor.jpg",
                                     user_id=other.id))
    db_session.add(models.TVShow(title="Secret Show", year=2020, watched=False, user_id=hidden.id))
    db_session.add(models.TVShow(title="Solo Show", year=2021, watched=False, user_id=others[0].id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Andor", 2022, 3)
    schedule(db_session, "tv-shows", "Secret Show", 2020, 1)
    schedule(db_session, "tv-shows", "Solo Show", 2021, 2)
    schedule(db_session, "tv-shows", "Far Away", 2021, 20)
    picks = card(client, user)["suggestions"]
    assert [pick["title"] for pick in picks] == ["Andor", "Solo Show"]
    assert picks[0]["members"] == 3 and picks[0]["image"] == "https://img.example/andor.jpg"
    assert picks[1]["members"] is None  # one member's shelf isn't counted out loud
    assert "hush" not in json.dumps(picks) and "Secret Show" not in json.dumps(picks)


def test_saving_a_suggestion_adds_an_unfinished_show_and_fills_the_week(client, db_session):
    user = member(db_session)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=user.id))
    other = member(db_session, "mara", days_old=40)
    db_session.add(models.TVShow(title="Andor", year=2022, watched=False, seasons=2, rating=9, review="mine",
                                 user_id=other.id))
    db_session.commit()
    key = schedule(db_session, "tv-shows", "Andor", 2022, 3)
    response = client.post("/api/week-one/save", headers=headers(user), json={"key": key, "today": today().isoformat()})
    assert response.status_code == 200 and response.json()["state"] == "created"
    saved = db_session.query(models.TVShow).filter_by(user_id=user.id).one()
    assert saved.title == "Andor" and saved.watched is False and saved.seasons == 2
    assert saved.rating is None and not saved.review  # another member's rating and notes never copy
    assert counted("saved") == 1
    again = client.post("/api/week-one/save", headers=headers(user), json={"key": key, "today": today().isoformat()})
    assert again.json()["state"] == "existing"
    found = card(client, user)
    assert found["count"] == 1 and found["suggestions"] == []
    missing = client.post("/api/week-one/save", headers=headers(user), json={"key": "airing:tv:nope:2020"})
    assert missing.status_code == 404


def test_saving_is_only_for_the_first_week(client, db_session):
    user = member(db_session, days_old=10)
    response = client.post("/api/week-one/save", headers=headers(user), json={"key": "airing:tv:andor:2022"})
    assert response.status_code == 403


def test_seen_then_a_later_day_counts_a_return(client, db_session, monkeypatch):
    user = member(db_session, days_old=1)
    assert client.post("/api/week-one/seen", headers=headers(user), json={"today": today().isoformat()}).json() == {"seen": True}
    client.post("/api/week-one/seen", headers=headers(user), json={"today": today().isoformat()})
    assert counted("seen") == 1 and counted("returned") == 0
    later = week_one._now() + timedelta(days=1)
    monkeypatch.setattr(week_one, "_now", lambda: later)
    client.post("/api/week-one/seen", headers=headers(user), json={"today": later.date().isoformat()})
    client.post("/api/week-one/seen", headers=headers(user), json={"today": later.date().isoformat()})
    assert counted("returned") == 1
    assert week_one.get_row(db_session, user.id).returned_at is not None


def test_browser_date_far_from_utc_is_ignored():
    now = datetime(2026, 11, 18, 12)
    assert week_one.local_today(now, "2026-11-19") == date(2026, 11, 19)
    assert week_one.local_today(now, "2026-12-25") == date(2026, 11, 18)
    assert week_one.local_today(now, "nonsense") == date(2026, 11, 18)


def test_reminder_rules(client, db_session):
    user = member(db_session)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, [0, 2])
    put = lambda day, tz=0: client.put("/api/week-one/reminder", headers=headers(user),  # noqa: E731
                                       json={"day": day.isoformat(), "today": today().isoformat(), "tz": tz})
    assert put(today()).status_code == 422  # today: they're already here
    assert put(today() + timedelta(days=1)).status_code == 422  # nothing of theirs that day
    assert put(today() + timedelta(days=9)).status_code == 422
    response = put(today() + timedelta(days=2), tz=-300)
    assert response.status_code == 200
    assert response.json()["reminder"] == {"date": (today() + timedelta(days=2)).isoformat(), "status": "set"}
    row = week_one.get_row(db_session, user.id)
    assert row.remind_at == datetime.combine(today() + timedelta(days=2), datetime.min.time()) + timedelta(hours=22)
    assert counted("email_set") == 1
    assert card(client, user)["reminder"]["status"] == "set"
    assert client.delete("/api/week-one/reminder", headers=headers(user)).json() == {"cancelled": True}
    assert card(client, user)["reminder"] is None and counted("email_cancel") == 1


def test_unverified_member_gets_no_email_offer(client, db_session):
    user = member(db_session, verified=False)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 2)
    assert card(client, user)["offer"]["email"] is False
    response = client.put("/api/week-one/reminder", headers=headers(user),
                          json={"day": (today() + timedelta(days=2)).isoformat(), "today": today().isoformat()})
    assert response.status_code == 422


def _session_factory(db_session):
    class Wrapper:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass
    return lambda: Wrapper()


def test_reminder_email_goes_out_once_on_the_day(client, db_session, monkeypatch):
    user = member(db_session)
    db_session.add(models.TVShow(title="Severance <b>", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance <b>", 2022, 2)
    day = today() + timedelta(days=2)
    week_one.set_reminder(db_session, user, day, today(), 0)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html, unsubscribe_url))

    factory = _session_factory(db_session)
    early = asyncio.run(week_one.send_due(factory, now=datetime.combine(day, datetime.min.time()) + timedelta(hours=16), sender=sender))
    assert early["sent"] == 0 and sent == []
    on_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=17, minutes=5)
    # On the day itself, "today" in the email is that day.
    result = asyncio.run(week_one.send_due(factory, now=on_time, sender=sender))
    assert result["sent"] == 1 and len(sent) == 1
    to, subject, html, unsubscribe = sent[0]
    assert to == "nova@example.com" and subject == "Severance <b> S2 E3 is out today"
    assert "Severance &lt;b&gt;" in html and "Severance <b>" not in html
    assert "/email/updates/unsubscribe?token=" in unsubscribe
    assert counted("sent") == 1
    assert asyncio.run(week_one.send_due(factory, now=on_time + timedelta(minutes=20), sender=sender))["sent"] == 0
    assert db_session.query(models.EmailCampaignSend).filter_by(user_id=user.id).count() == 1
    # The next look at the home screen counts the return.
    monkeypatch.setattr(week_one, "_now", lambda: on_time + timedelta(hours=1))
    response = client.get(f"/api/week-one?today={day.isoformat()}", headers=headers(user))
    assert response.json()["card"]["reminder"]["status"] == "sent"
    assert counted("back_after_email") == 1


def test_late_or_empty_reminders_are_dropped(db_session):
    user = member(db_session)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 2)
    day = today() + timedelta(days=2)
    week_one.set_reminder(db_session, user, day, today(), 0)
    sent = []

    async def sender(*args):
        sent.append(args)

    late = datetime.combine(day, datetime.min.time()) + timedelta(hours=17) + week_one.LATE + timedelta(minutes=1)
    result = asyncio.run(week_one.send_due(_session_factory(db_session), now=late, sender=sender))
    assert result == {"sent": 0, "failed": 0, "dropped": 1, "limited": False} and sent == []
    assert week_one.get_row(db_session, user.id).reminder_status == "dropped"


def test_hide_and_stay_posted_waits_for_the_card(client, db_session):
    user = member(db_session, days_old=3)
    user.visit_days = 3
    for i in range(12):
        db_session.add(models.Movie(title=f"Film {i}", year=2001, watched=True, user_id=user.id))
    db_session.commit()
    assert week_one.active(db_session, user)
    assert stay_posted.current(db_session, user) is None  # the first-week card asks instead
    assert client.post("/api/week-one/hide", headers=headers(user)).json() == {"hidden": True}
    assert counted("hidden") == 1 and card(client, user) is None
    assert not week_one.active(db_session, user)
    assert stay_posted.current(db_session, user) is not None


def test_push_counted_only_with_a_device(client, db_session):
    user = member(db_session)
    assert client.post("/api/week-one/push", headers=headers(user)).json() == {"counted": False}
    db_session.add(models.PushSubscription(user_id=user.id, endpoint="https://fcm.googleapis.com/fcm/send/x", p256dh="p", auth="a"))
    db_session.commit()
    assert client.post("/api/week-one/push", headers=headers(user)).json() == {"counted": True}
    client.post("/api/week-one/push", headers=headers(user))
    assert counted("push_on") == 1


def test_every_route_needs_sign_in_and_is_rate_limited(client):
    for route in week_one_router.router.routes:
        for method in route.methods:
            assert _limited(week_one_router.router, route.path, method), (method, route.path)
            response = client.request(method, route.path, json={})
            assert response.status_code in (401, 403), route.path


def test_site_stats_block(db_session):
    db_session.add(models.SiteTrafficDaily(day=datetime.utcnow().date(), kind="weekone", key="returned", count=4))
    db_session.commit()
    stats = week_one.stats(db_session, 30, datetime.utcnow())
    assert stats["counts"]["returned"] == 4 and stats["counts"]["seen"] == 0
    assert set(stats["labels"]) == set(week_one.COUNTERS) and stats["pending_reminders"] == 0


RADAR_CARD = {"category": "movies", "library_category": "movies", "label": "Movie", "title": "Big New Film",
              "date": None, "image": "https://img.example/film.jpg", "window": "2026-11", "key": "big-new-film",
              "url": "/release-radar/movies#item-big-new-film", "reason": "", "source": "radar", "details": []}


def test_releases_out_this_week_for_a_thin_week(client, db_session, monkeypatch):
    from app import for_you
    user = member(db_session)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=user.id))
    db_session.commit()
    soon = {**RADAR_CARD, "date": (today() + timedelta(days=3)).isoformat()}
    later = {**RADAR_CARD, "key": "later", "title": "Later Film", "date": (today() + timedelta(days=20)).isoformat()}
    monkeypatch.setattr(for_you, "radar_pool", lambda today=None, client=None: [])
    monkeypatch.setattr(for_you, "upcoming_popular", lambda pool, today, owned, days=30, limit=8, exclude_keys=None: [soon, later])
    found = card(client, user)
    assert [release["title"] for release in found["releases"]] == ["Big New Film"]
    assert found["releases"][0]["window"] == "2026-11" and "reason" not in found["releases"][0]


def test_save_release_goes_through_the_radar_save_and_counts(client, db_session, monkeypatch):
    from app.routers import release_radar
    user = member(db_session)
    item = {"key": "big-new-film", "title": "Big New Film", "save": {"title": "Big New Film", "year": 2026, "director": "A"}}
    monkeypatch.setattr(release_radar, "_window_items", lambda category, window: (None, [item]))
    body = {"category": "movies", "window": "2026-11", "key": "big-new-film", "today": today().isoformat()}
    response = client.post("/api/week-one/save-release", headers=headers(user), json=body)
    assert response.status_code == 200 and response.json()["state"] == "created"
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Big New Film").one().watched is False
    assert counted("saved_release") == 1
    assert client.post("/api/week-one/save-release", headers=headers(user), json=body).json()["state"] == "existing"
    assert counted("saved_release") == 1
    old = member(db_session, "old", days_old=10)
    assert client.post("/api/week-one/save-release", headers=headers(old), json=body).status_code == 403


def test_start_page_counts_its_own_look_and_reminder(client, db_session):
    user = member(db_session)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 2)
    for _ in range(2):
        assert client.post("/api/week-one/start-seen", headers=headers(user), json={"today": today().isoformat()}).json() == {"seen": True}
    assert counted("start_seen") == 1
    response = client.put("/api/week-one/reminder", headers=headers(user), json={
        "day": (today() + timedelta(days=2)).isoformat(), "today": today().isoformat(), "place": "start"})
    assert response.status_code == 200
    assert counted("start_email_set") == 1 and counted("email_set") == 0
    assert client.put("/api/week-one/reminder", headers=headers(user), json={
        "day": (today() + timedelta(days=2)).isoformat(), "place": "elsewhere"}).status_code == 422


def test_start_page_script_asks_for_the_week():
    from pathlib import Path
    script = Path("app/static/start.js").read_text()
    assert "/api/week-one?today=" in script and "/api/week-one/start-seen" in script and "place: 'start'" in script
