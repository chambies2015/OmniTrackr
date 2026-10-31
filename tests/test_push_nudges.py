"""Away reminders: one push, with something concrete from the member's library, after a week without a visit."""
import json
from datetime import date, datetime, timedelta

import httpx

from app import models, push_nudges, web_push
from app import release_radar as radar
from tests.test_episode_alerts import episode, store, tv_schedule
from tests.test_push_settings import _device, _user, fresh_key  # noqa: F401  (fixture)
from tests.test_web_push import decrypt

NOW = datetime(2026, 10, 29, 15, 0)  # 10 am in Chicago, 3 pm UTC


def member(db, name, away_days=10, device=True, endpoint=None):
    user = _user(db, name)
    user.is_verified = True
    user.created_at = NOW - timedelta(days=60)
    user.last_login_at = NOW - timedelta(days=away_days)
    user.last_seen_on = (NOW - timedelta(days=away_days)).date()
    db.commit()
    keys = _device(db, user, endpoint=endpoint or f"https://fcm.googleapis.com/fcm/send/{name}") if device else None
    return user, keys


def recording():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(201)

    return seen, httpx.Client(transport=httpx.MockTransport(handler))


def test_due_after_a_week_away_with_a_device_and_the_switch_on(db_session):
    away, _ = member(db_session, "away")
    fresh, _ = member(db_session, "fresh", away_days=3)
    no_device, _ = member(db_session, "nodevice", device=False)
    switched_off, _ = member(db_session, "off")
    web_push.save_settings(db_session, switched_off.id, topics={"reminders": False})
    unverified, _ = member(db_session, "unverified")
    unverified.is_verified = False
    db_session.commit()
    assert [user.id for user in push_nudges.due_members(db_session, NOW)] == [away.id]


def test_a_visit_in_between_counts_even_without_a_log_in(db_session):
    user, _ = member(db_session, "visitor", away_days=20)
    user.last_seen_on = (NOW - timedelta(days=2)).date()  # opened the app, session still valid
    db_session.commit()
    assert push_nudges.due_members(db_session, NOW) == []


def test_at_most_one_every_two_weeks_and_two_unanswered(db_session):
    user, _ = member(db_session, "away", away_days=40)
    db_session.add(models.PushNudge(user_id=user.id, kind="away_nudge", sent_at=NOW - timedelta(days=5)))
    db_session.commit()
    assert push_nudges.due_members(db_session, NOW) == []
    db_session.query(models.PushNudge).delete()
    db_session.add_all([models.PushNudge(user_id=user.id, kind="away_nudge", sent_at=NOW - timedelta(days=30)),
                        models.PushNudge(user_id=user.id, kind="away_nudge", sent_at=NOW - timedelta(days=16))])
    db_session.commit()
    assert push_nudges.due_members(db_session, NOW) == []
    # Those two were before the member's last visit, so they were answered: a new quiet spell starts the count over.
    user.last_seen_on = (NOW - timedelta(days=10)).date()
    db_session.commit()
    assert [user.id for user in push_nudges.due_members(db_session, NOW)] == [user.id]


def test_the_message_names_an_episode_then_a_release_then_a_waiting_title(db_session):
    user, _ = member(db_session, "away")
    assert push_nudges.message_for(db_session, user, NOW.date()) is None  # empty library: nothing to say
    db_session.add(models.Movie(user_id=user.id, title="Dune", director="X", watched=False))
    db_session.add(models.Book(user_id=user.id, title="Dune (novel)", author="Herbert", read=False))
    db_session.commit()
    assert push_nudges.message_for(db_session, user, NOW.date()) == \
        "Dune and 1 more are still waiting in your library. One for tonight?"
    pool = [radar.make_item(category="movies", key="wd-Q1", title="Dune: Part Three",
                            release_date=(NOW + timedelta(days=4)).date().isoformat(), source_url=None,
                            save={"title": "Dune: Part Three"})]
    assert push_nudges.message_for(db_session, user, NOW.date(), pool) == \
        "Dune: Part Three (Movie) is out on Monday, and it's connected to your library."
    db_session.add(models.TVShow(user_id=user.id, title="Severance", year=2022, watched=False))
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([
        episode(2, 5, start=NOW + timedelta(days=1), name="Trojan's Horse")]))
    assert push_nudges.message_for(db_session, user, NOW.date(), pool) == \
        "Severance S2E5, Trojan's Horse is out tomorrow."


def test_sends_once_records_it_and_skips_quiet_hours(db_session):
    user, (private, auth) = member(db_session, "away")
    db_session.add(models.Movie(user_id=user.id, title="Dune", director="X", watched=False))
    db_session.commit()
    web_push.save_settings(db_session, user.id, time_zone="America/Chicago")  # quiet 22:00-08:00 by default
    seen, http = recording()
    with http:
        night = datetime(2026, 10, 29, 4, 0)  # 11 pm in Chicago
        assert push_nudges.send_nudges(db_session, http=http, now=night) == \
            {"sent": 0, "members": 0, "quiet": 1, "nothing_to_say": 0}
        assert push_nudges.send_nudges(db_session, http=http, now=NOW) == \
            {"sent": 1, "members": 1, "quiet": 0, "nothing_to_say": 0}
        assert push_nudges.send_nudges(db_session, http=http, now=NOW + timedelta(hours=1))["members"] == 0
    [request] = seen
    data = json.loads(decrypt(request.content, private, auth))
    assert data == {"title": "Still on your list", "body": "Dune is still waiting in your library. One for tonight?",
                    "url": "/?utm_source=push&utm_campaign=away-reminder", "tag": "away_nudge"}
    [row] = db_session.query(models.PushNudge).all()
    assert row.user_id == user.id and row.sent_at == NOW
    # Nothing in the bell about having been away.
    assert db_session.query(models.Notification).filter_by(user_id=user.id).count() == 0


def test_nothing_to_say_sends_nothing_and_records_nothing(db_session):
    member(db_session, "empty")
    seen, http = recording()
    with http:
        assert push_nudges.send_nudges(db_session, http=http, now=NOW)["nothing_to_say"] == 1
    assert seen == [] and db_session.query(models.PushNudge).count() == 0


def test_the_hourly_push_jobs_include_away_reminders(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(push_nudges, "send_nudges", lambda db: calls.append(db) or {"sent": 2})
    monkeypatch.setattr(web_push, "send_held", lambda db: {"members": 0})
    monkeypatch.setattr("app.clubs.send_due_reminders", lambda db: 0)
    monkeypatch.setattr("app.memories.send_due_pushes", lambda db: 0)
    stats = web_push._hourly_jobs(lambda: db_session)
    assert stats["away"] == 2 and len(calls) == 1
