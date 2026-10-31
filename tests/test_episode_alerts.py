"""New-episode alerts: a bell notification (pushed to devices) the moment an episode of a member's show is out."""
import json
from datetime import date, datetime, timedelta

import httpx

from app import episode_alerts, episode_calendar, models, web_push
from tests.test_push_settings import _device, _user, fresh_key  # noqa: F401  (fixture)

TODAY = date(2026, 10, 29)
NOW = datetime(2026, 10, 29, 12, 0)  # noon UTC


def store(db, category, title, year, data):
    db.add(models.TitleMetadata(key=episode_calendar.airing_key(category, title, year), status="ok",
                                data=json.dumps(data), fetched_at=datetime.utcnow()))
    db.commit()


def tv_schedule(episodes, show="Severance", show_id=7, network="Apple TV+"):
    return {"source": "TVmaze", "source_id": show_id, "source_url": None, "show": show, "network": network,
            "ended": False, "episodes": episodes}


def episode(season, number, start=None, day=None, name=""):
    """An episode out at ``start`` (UTC), or an all-day drop on ``day`` when there's no air time."""
    when = start or day
    return {"season": season, "number": number, "name": name, "date": when.date().isoformat() if start else day.isoformat(),
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ") if start else None, "minutes": 50}


def notes(db, user):
    return db.query(models.Notification).filter_by(user_id=user.id, type="episode_today").all()


def tracked(db, user, title="Severance", year=2022, model=models.TVShow):
    db.add(model(user_id=user.id, title=title, year=year, watched=False))
    db.commit()


def test_a_member_with_a_device_is_told_once_when_the_episode_is_out(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    tracked(db_session, sam)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([
        episode(2, 4, start=NOW - timedelta(days=7)),            # last week: too old to announce
        episode(2, 5, start=NOW - timedelta(hours=1), name="Trojan's Horse"),
        episode(2, 6, start=NOW + timedelta(days=7)),            # next week
    ]))
    assert episode_alerts.send_alerts(db_session, NOW) == {"members": 1, "episodes": 1}
    [note] = notes(db_session, sam)
    assert note.message == "Severance S2E5, Trojan's Horse is out now on Apple TV+."
    assert note.link == "/titles/tv/severance-2022"
    # Run again an hour later: nothing new to say.
    assert episode_alerts.send_alerts(db_session, NOW + timedelta(hours=1)) == {"members": 0, "episodes": 0}
    assert len(notes(db_session, sam)) == 1


def test_not_before_the_air_time_and_not_days_after(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    tracked(db_session, sam)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, start=NOW + timedelta(hours=2))]))
    assert episode_alerts.send_alerts(db_session, NOW)["members"] == 0
    assert episode_alerts.send_alerts(db_session, NOW + timedelta(hours=3))["members"] == 1
    # An episode first seen two days late is skipped rather than announced late.
    store(db_session, "anime", "One Piece", 1999, {"source": "AniList", "source_id": 21, "source_url": None,
                                                    "show": "One Piece", "network": "", "ended": False,
                                                    "episodes": [episode(None, 1120, start=NOW - timedelta(days=2))]})
    tracked(db_session, sam, "One Piece", 1999, models.Anime)
    assert episode_alerts.send_alerts(db_session, NOW + timedelta(hours=3))["members"] == 0


def test_streaming_drops_without_an_air_time_count_from_eight_utc(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    tracked(db_session, sam)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, day=TODAY)]))
    early = datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=7)
    assert episode_alerts.send_alerts(db_session, early)["members"] == 0
    assert episode_alerts.send_alerts(db_session, early + timedelta(hours=1))["members"] == 1


def test_several_new_episodes_make_one_message_that_opens_the_library(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    tracked(db_session, sam)
    tracked(db_session, sam, "One Piece", 1999, models.Anime)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, start=NOW - timedelta(hours=1))]))
    store(db_session, "anime", "One Piece", 1999, {"source": "AniList", "source_id": 21, "source_url": None,
                                                    "show": "One Piece", "network": "", "ended": False,
                                                    "episodes": [episode(None, 1120, start=NOW - timedelta(hours=3))]})
    assert episode_alerts.send_alerts(db_session, NOW) == {"members": 1, "episodes": 2}
    [note] = notes(db_session, sam)
    assert note.message == "New episodes out now: One Piece episode 1120 and Severance S2E5."
    assert note.link == "/"


def test_private_libraries_open_the_dashboard_not_the_title_page(db_session):
    sam = _user(db_session, "sam")
    sam.tv_shows_private = True
    _device(db_session, sam)
    tracked(db_session, sam)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, start=NOW - timedelta(hours=1))]))
    episode_alerts.send_alerts(db_session, NOW)
    assert notes(db_session, sam)[0].link == "/"


def test_only_members_who_asked_are_checked(db_session):
    quiet = _user(db_session, "quiet")                       # tracks the show, no device, no calendar
    switched_off = _user(db_session, "off")                  # device, but New episodes switched off
    _device(db_session, switched_off, endpoint="https://fcm.googleapis.com/fcm/send/off-device")
    web_push.save_settings(db_session, switched_off.id, topics={"episodes": False})
    calendar = _user(db_session, "calendar")                 # private calendar with episodes, no device
    db_session.add(models.CalendarFeed(user_id=calendar.id, token="cal-token", include_episodes=True))
    finished = _user(db_session, "finished")
    _device(db_session, finished, endpoint="https://fcm.googleapis.com/fcm/send/finished-device")
    db_session.commit()
    for user in (quiet, switched_off, calendar):
        tracked(db_session, user)
    db_session.add(models.TVShow(user_id=finished.id, title="Severance", year=2022, watched=True))
    db_session.commit()
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, start=NOW - timedelta(hours=1))]))

    # Checked: the calendar member and the device owner (whose only show is finished, so nothing is sent).
    assert episode_alerts.members(db_session) == [calendar.id, finished.id]
    assert episode_alerts.send_alerts(db_session, NOW) == {"members": 1, "episodes": 1}
    assert notes(db_session, quiet) == [] and notes(db_session, switched_off) == [] and notes(db_session, finished) == []
    assert len(notes(db_session, calendar)) == 1


def test_members_with_the_switch_on_get_their_schedules_fetched(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    nobody = _user(db_session, "nobody")
    assert episode_calendar._subscribers(db_session) == [sam.id]
    assert nobody.id not in episode_calendar._subscribers(db_session)


def test_the_notification_is_pushed_to_the_device(db_session):
    sam = _user(db_session, "sam")
    _device(db_session, sam)
    tracked(db_session, sam)
    store(db_session, "tv-shows", "Severance", 2022, tv_schedule([episode(2, 5, start=NOW - timedelta(hours=1))]))
    episode_alerts.send_alerts(db_session, NOW)
    [note] = notes(db_session, sam)
    seen = []
    http = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(201))[1]))
    with http:
        stats = web_push.deliver(db_session, [(sam.id, note.type, note.message, note.link)], http=http, now=NOW)
    assert stats["sent"] == 1 and len(seen) == 1
    assert web_push.payload_for(note.type, note.message, note.link).startswith(b'{"title":"New episode out"')
