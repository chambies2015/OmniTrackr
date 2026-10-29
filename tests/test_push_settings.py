"""What gets pushed to a member's devices: per-kind switches, quiet hours and club finish-by nudges."""
import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import clubs, models, web_push
from app.web_push import b64url_encode
from tests.test_web_push import FCM, auth_headers, create_user_and_login, decrypt


@pytest.fixture(autouse=True)
def fresh_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    web_push._reset_key_cache()
    yield
    web_push._reset_key_cache()


@pytest.fixture
def client(client, db_session):
    client.app_state_db = db_session
    return client


def _user(db, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    return user


def _device(db, user, endpoint=FCM):
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    web_push.save_subscription(db, user.id, endpoint, b64url_encode(public), b64url_encode(auth))
    return private, auth


def _recording():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(201)

    return seen, httpx.Client(transport=httpx.MockTransport(handler))


# Tue Oct 27 2026: 05:00 UTC is midnight in Chicago (CDT), 14:00 UTC is 9 am.
CHICAGO_MIDNIGHT = datetime(2026, 10, 27, 5, 0)
CHICAGO_MORNING = datetime(2026, 10, 27, 14, 0)


def test_quiet_defaults_push_only_what_is_worth_a_buzz():
    chosen = {topic["key"]: topic["on"] for topic in web_push.settings_for(None)["topics"]}
    assert chosen == {"releases": True, "clubs": True, "recommendations": True, "friends": True,
                      "discussions": True, "club_talk": False, "milestones": False, "memories": False}
    assert web_push.wants(None, "release_day") and web_push.wants(None, "club_pick")
    assert web_push.wants(None, "friend_recommendation") and web_push.wants(None, "club_due_soon")
    assert not web_push.wants(None, "club_post") and not web_push.wants(None, "friend_feed_cheer")
    # Something new nobody has filed yet stays quiet; the push confirmation always goes.
    assert not web_push.wants(None, "something_new")
    assert web_push.wants(None, "push_enabled")


def test_every_notification_type_has_a_push_title_and_a_home():
    types = {"release_day", "club_pick", "club_post", "club_due_soon", "friend_recommendation",
             "friend_recommendation_added", "recommendation_received", "take_received", "friend_request_received",
             "shared_list_item", "friend_feed_cheer", "badge_earned", "push_enabled", "discussion_reply",
             "discussion_report"}
    for kind in types:
        assert kind in web_push.TITLES
        assert kind in web_push.TOPIC_FOR_TYPE or kind in web_push.ALWAYS_PUSHED


def test_settings_round_trip_and_store_only_changes(client, db_session):
    token = create_user_and_login(client, "settings", "settings@example.com")
    defaults = client.get("/notifications/push/settings", headers=auth_headers(token)).json()
    assert defaults["quiet_hours"] == {"on": True, "start": 22, "end": 8}
    assert db_session.query(models.PushPreference).count() == 0  # Reading makes no row.

    saved = client.put("/notifications/push/settings", headers=auth_headers(token), json={
        "topics": {"club_talk": True, "releases": True}, "quiet_hours": True, "quiet_start": 23, "quiet_end": 7,
        "time_zone": "Europe/Berlin"})
    assert saved.status_code == 200
    chosen = {topic["key"]: topic["on"] for topic in saved.json()["topics"]}
    assert chosen["club_talk"] is True and chosen["milestones"] is False
    pref = db_session.query(models.PushPreference).one()
    assert json.loads(pref.topics) == {"club_talk": True}
    assert (pref.quiet_start, pref.quiet_end, pref.time_zone) == (23, 7, "Europe/Berlin")

    back = client.put("/notifications/push/settings", headers=auth_headers(token), json={"topics": {"club_talk": False}})
    assert back.status_code == 200
    db_session.refresh(pref)
    assert pref.topics is None and pref.quiet_start == 23


@pytest.mark.parametrize("body", [
    {"topics": {"everything": True}},
    {"quiet_start": 24},
    {"time_zone": "Not/A_Zone"},
    {"time_zone": "../../etc/passwd"},
])
def test_settings_reject_unknown_values(client, body):
    token = create_user_and_login(client, "strict", "strict@example.com")
    assert client.put("/notifications/push/settings", headers=auth_headers(token), json=body).status_code == 422


def test_turning_on_a_device_remembers_its_time_zone(client, db_session, monkeypatch):
    monkeypatch.setattr(web_push, "submit", lambda bind, messages: None)
    token = create_user_and_login(client, "zone", "zone@example.com")
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
    body = {"endpoint": FCM, "keys": {"p256dh": b64url_encode(public), "auth": b64url_encode(b"0123456789abcdef")},
            "time_zone": "America/Chicago"}
    assert client.post("/notifications/push/subscription", headers=auth_headers(token), json=body).status_code == 200
    assert db_session.query(models.PushPreference).one().time_zone == "America/Chicago"
    # A made-up zone is ignored rather than refusing the device.
    body["time_zone"] = "Mars/Olympus"
    assert client.post("/notifications/push/subscription", headers=auth_headers(token), json=body).status_code == 200
    assert db_session.query(models.PushPreference).one().time_zone == "America/Chicago"


def test_switched_off_kinds_are_not_pushed(db_session):
    user = _user(db_session, "picky")
    _device(db_session, user)
    web_push.save_settings(db_session, user.id, topics={"releases": False, "milestones": True})
    seen, http = _recording()
    with http:
        stats = web_push.deliver(db_session, [
            (user.id, "release_day", "Out today: Dune", "/release-radar"),
            (user.id, "club_post", "sam posted", "/lists/1"),
            (user.id, "badge_earned", "New badge", "/#badges"),
        ], http=http, now=CHICAGO_MORNING)
    assert stats["sent"] == 1 and stats["muted"] == 2
    assert len(seen) == 1


def test_quiet_hours_hold_pushes_then_send_one_catch_up(db_session):
    user = _user(db_session, "sleepy")
    private, auth = _device(db_session, user)
    web_push.save_settings(db_session, user.id, time_zone="America/Chicago")
    for minutes, kind, message in [(1, "club_pick", 'sam picked Heat for "Film club".'),
                                   (2, "friend_recommendation", "sam thinks you'd love Arrival."),
                                   (3, "club_post", "sam posted about Heat."),
                                   (4, "release_day", "Out today: Dune (Movie), from your library.")]:
        db_session.add(models.Notification(user_id=user.id, type=kind, message=message, link="/",
                                           created_at=CHICAGO_MIDNIGHT + timedelta(minutes=minutes)))
    # Pushed before quiet hours began, so it's not repeated.
    db_session.add(models.Notification(user_id=user.id, type="release_day", message="Earlier",
                                       created_at=datetime(2026, 10, 27, 1, 0)))
    db_session.commit()

    seen, http = _recording()
    with http:
        stats = web_push.deliver(db_session, [(user.id, "club_pick", "sam picked Heat", "/lists/1")],
                                 http=http, now=CHICAGO_MIDNIGHT)
        assert stats["held"] == 1 and seen == []
        pref = db_session.get(models.PushPreference, user.id)
        assert pref.held_since == datetime(2026, 10, 27, 3, 0)  # 10 pm in Chicago.

        # Still quiet: nothing goes out.
        assert web_push.send_held(db_session, http=http, now=CHICAGO_MIDNIGHT + timedelta(hours=2))["members"] == 0
        # The newest one has been read in the app meanwhile.
        newest = db_session.query(models.Notification).filter_by(type="release_day", message=
                                                                 "Out today: Dune (Movie), from your library.").one()
        newest.read_at = CHICAGO_MIDNIGHT + timedelta(hours=3)
        db_session.commit()

        stats = web_push.send_held(db_session, http=http, now=CHICAGO_MORNING)
    assert stats["members"] == 1 and len(seen) == 1
    message = json.loads(decrypt(seen[0].content, private, auth))
    assert message["title"] == "While you were away"
    # Unread and wanted only: not the club talk (off by default), the read one or the earlier one.
    assert message["body"] == "sam thinks you'd love Arrival. · sam picked Heat for \"Film club\"."
    assert message["url"] == "/"
    db_session.refresh(pref)
    assert pref.held_since is None

    # Running again sends nothing more.
    seen2, http2 = _recording()
    with http2:
        assert web_push.send_held(db_session, http=http2, now=CHICAGO_MORNING)["members"] == 0
    assert seen2 == []


def test_quiet_hours_need_a_known_time_zone_and_can_be_turned_off(db_session):
    user = _user(db_session, "nozone")
    _device(db_session, user)
    pref = web_push.save_settings(db_session, user.id)
    assert pref.quiet_hours is True and pref.time_zone is None
    assert web_push.in_quiet_hours(pref, CHICAGO_MIDNIGHT) is False
    web_push.save_settings(db_session, user.id, time_zone="America/Chicago")
    assert web_push.in_quiet_hours(pref, CHICAGO_MIDNIGHT) is True
    assert web_push.in_quiet_hours(pref, CHICAGO_MORNING) is False
    web_push.save_settings(db_session, user.id, quiet_hours=False)
    assert web_push.in_quiet_hours(pref, CHICAGO_MIDNIGHT) is False
    # A daytime window (e.g. work hours) works too.
    web_push.save_settings(db_session, user.id, quiet_hours=True, quiet_start=9, quiet_end=17)
    assert web_push.in_quiet_hours(pref, CHICAGO_MORNING) is True
    assert web_push.in_quiet_hours(pref, CHICAGO_MIDNIGHT) is False


def test_the_push_confirmation_ignores_quiet_hours(db_session):
    user = _user(db_session, "eager")
    _device(db_session, user)
    web_push.save_settings(db_session, user.id, time_zone="America/Chicago")
    seen, http = _recording()
    with http:
        stats = web_push.deliver(db_session, [(user.id, "push_enabled", "Notifications are on", "/")],
                                 http=http, now=CHICAGO_MIDNIGHT)
    assert stats["sent"] == 1 and len(seen) == 1


# ---------------------------------------------------------------- club finish-by nudges

def _round(db, owner, others, ends_in, started_days_ago):
    shared = models.SharedList(owner_id=owner.id, name="Film club", token=f"tok{owner.id}{ends_in}{started_days_ago}")
    db.add(shared)
    db.flush()
    for user in [owner, *others]:
        db.add(models.SharedListMember(list_id=shared.id, user_id=user.id))
    today = datetime.utcnow().date()
    picked = models.ClubRound(list_id=shared.id, started_by_id=owner.id, kind="movie", title="Heat",
                              ends_on=today + timedelta(days=ends_in),
                              started_at=datetime.utcnow() - timedelta(days=started_days_ago))
    db.add(picked)
    db.commit()
    return shared, picked


def test_club_members_who_havent_finished_get_one_nudge(db_session):
    owner, sam, ana = _user(db_session, "owner"), _user(db_session, "sam"), _user(db_session, "ana")
    shared, picked = _round(db_session, owner, [sam, ana], ends_in=2, started_days_ago=5)
    db_session.add(models.ClubProgress(round_id=picked.id, user_id=ana.id, status="finished"))
    db_session.add(models.ClubProgress(round_id=picked.id, user_id=owner.id, status="started"))
    db_session.commit()

    assert clubs.send_due_reminders(db_session) == 2
    notes = db_session.query(models.Notification).filter_by(type="club_due_soon").all()
    assert sorted(note.user_id for note in notes) == sorted([owner.id, sam.id])
    assert notes[0].link == f"/lists/{shared.id}"
    assert "Heat, the club pick in \"Film club\"" in notes[0].message and "Mark it watched" in notes[0].message
    assert clubs.send_due_reminders(db_session) == 0  # Once per member per pick.


def test_no_nudge_for_new_far_off_or_wrapped_up_picks(db_session):
    owner, sam = _user(db_session, "owner2"), _user(db_session, "sam2")
    _round(db_session, owner, [sam], ends_in=2, started_days_ago=1)   # Everyone just heard about it.
    _round(db_session, owner, [sam], ends_in=6, started_days_ago=5)   # Not due yet.
    _, done = _round(db_session, owner, [sam], ends_in=1, started_days_ago=5)
    done.ended_at = datetime.utcnow()
    db_session.commit()
    assert clubs.send_due_reminders(db_session) == 0
    assert db_session.query(models.Notification).filter_by(type="club_due_soon").count() == 0
