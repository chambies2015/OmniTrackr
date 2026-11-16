"""The "stay posted" card, the note after saving a show, push opt-in places and their Site stats counters."""
from datetime import datetime, timedelta

import pytest

from app import auth, digest, models, stay_posted, support_asks, web_push
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
FCM = "https://fcm.googleapis.com/fcm/send/abc123:APA91bExampleEndpointToken"
REAL_UPCOMING = stay_posted.upcoming
SOON = [{"kind": "episode", "title": "Frieren", "label": "Anime", "what": "Episode 10", "date": "2026-11-20"}]


@pytest.fixture(autouse=True)
def counters(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    # Nothing coming up unless a test says so; the real lookup reads schedule caches.
    monkeypatch.setattr(stay_posted, "upcoming", lambda db, user, today=None: [])
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key, kind="stay"):
    return sum(amount for (_, k, name), amount in RECORDER._pending.items() if k == kind and name == key)


def member(db, name="riley", days_old=20, visit_days=6, titles=12, verified=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=verified, is_active=True, created_at=datetime.utcnow() - timedelta(days=days_old),
                       visit_days=visit_days)
    db.add(user)
    db.flush()
    for i in range(titles):
        db.add(models.Movie(title=f"Film {i}", director="X", year=2001, watched=True, user_id=user.id))
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def card(client, user):
    response = client.get("/api/stay-posted", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()["ask"]


def seen(client, user, moment):
    return client.post("/api/stay-posted/seen", headers=headers(user), json={"moment": moment}).json()["shown"]


def reply(client, user, answer, place="card"):
    return client.post("/api/stay-posted/answer", headers=headers(user), json={"answer": answer, "place": place})


# ---------------------------------------------------------------- who sees the card

def test_a_settled_library_gets_the_card_and_looking_stores_nothing(client, db_session):
    user = member(db_session)
    ask = card(client, user)
    assert ask["moment"] == "library"
    assert ask["title"] == "Want a heads-up when something you track comes out?"
    assert "12 titles" in ask["body"]
    assert ask["offer"] == {"email": True, "calendar": True}
    assert ask["items"] == [] and ask["sample_url"] == "/email/weekly/preview"
    assert stay_posted.get_row(db_session, user.id) is None
    assert counted("card_shown_library") == 0
    # Looking never turns anything on.
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    assert db_session.query(models.CalendarFeed).count() == 0


@pytest.mark.parametrize("kwargs", [{"days_old": 1}, {"visit_days": 1}, {"titles": 2}, {"titles": 6}])
def test_new_quiet_or_small_libraries_are_not_asked(client, db_session, kwargs):
    user = member(db_session, **kwargs)
    assert card(client, user) is None


def test_something_coming_up_names_it_even_in_a_small_library(client, db_session, monkeypatch):
    monkeypatch.setattr(stay_posted, "upcoming", lambda db, user, today=None: list(SOON))
    user = member(db_session, titles=4)
    ask = card(client, user)
    assert ask["moment"] == "soon" and ask["eyebrow"] == "Coming up"
    assert ask["title"] == "Frieren has a new episode coming"
    assert ask["items"][0]["what"] == "Episode 10"
    more = SOON + [{"kind": "release", "title": "Big Game", "label": "Game", "what": "Out", "date": "2026-12-01"}]
    monkeypatch.setattr(stay_posted, "upcoming", lambda db, user, today=None: list(more))
    assert card(client, user)["title"] == "2 things you track have something coming up"


@pytest.mark.parametrize("channel", ["email", "push", "calendar"])
def test_members_who_already_use_a_channel_are_never_asked(client, db_session, channel):
    user = member(db_session)
    if channel == "email":
        digest.subscribe(db_session, user.id)
    elif channel == "push":
        web_push.save_subscription(db_session, user.id, FCM, "p" * 20, "a" * 16)
    else:
        db_session.add(models.CalendarFeed(user_id=user.id, token="tok-" + "x" * 20))
        db_session.commit()
    assert card(client, user) is None
    offer = client.post("/api/stay-posted/after-save", headers=headers(user),
                        json={"category": "anime", "title": "Frieren", "push": True}).json()["offer"]
    assert offer is None


def test_unverified_members_are_not_offered_the_email(client, db_session):
    user = member(db_session, verified=False)
    assert card(client, user)["offer"]["email"] is False


def test_an_open_support_note_wins(client, db_session, monkeypatch):
    user = member(db_session)
    monkeypatch.setattr(support_asks, "current", lambda db, user, now=None: {"moment": "titles"})
    assert card(client, user) is None


# ---------------------------------------------------------------- how often

def test_seen_opens_the_card_for_a_week_then_it_rests_for_a_month(client, db_session):
    user = member(db_session)
    assert seen(client, user, "library") is True
    assert seen(client, user, "library") is True
    assert counted("card_shown_library") == 1
    assert card(client, user)["moment"] == "library"
    row = stay_posted.get_row(db_session, user.id)
    row.shown_at = datetime.utcnow() - timedelta(days=8)
    db_session.commit()
    assert card(client, user) is None
    row.shown_at = datetime.utcnow() - timedelta(days=38)
    db_session.commit()
    assert card(client, user)["moment"] == "library"


def test_three_showings_and_it_stops_for_good(client, db_session):
    user = member(db_session)
    for _ in range(3):
        assert seen(client, user, "library") is True
        row = stay_posted.get_row(db_session, user.id)
        row.shown_at = datetime.utcnow() - timedelta(days=60)
        db_session.commit()
    assert row.shown_count == 3
    assert card(client, user) is None


def test_seen_for_a_moment_that_is_not_due_is_ignored(client, db_session):
    user = member(db_session)
    assert seen(client, user, "soon") is False
    assert seen(client, user, "weird") is False
    assert stay_posted.get_row(db_session, user.id) is None


def test_not_now_waits_six_weeks(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    assert reply(client, user, "later").json() == {"saved": True}
    assert card(client, user) is None
    row = stay_posted.get_row(db_session, user.id)
    assert row.snoozed_until > datetime.utcnow() + timedelta(days=40)
    assert counted("card_later_library") == 1


def test_dont_ask_again_stops_the_card_and_the_note(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    reply(client, user, "stop")
    row = stay_posted.get_row(db_session, user.id)
    row.shown_at = datetime.utcnow() - timedelta(days=400)
    db_session.commit()
    assert card(client, user) is None
    offer = client.post("/api/stay-posted/after-save", headers=headers(user),
                        json={"category": "tv-shows", "title": "Severance", "push": True}).json()["offer"]
    assert offer is None


def test_unknown_answers_are_refused(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    assert reply(client, user, "everything").status_code == 422
    assert reply(client, user, "email", place="elsewhere").status_code == 422


def test_sample_email_leaves_the_card_up(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    reply(client, user, "sample")
    assert card(client, user)["moment"] == "library"
    assert counted("card_sample_library") == 1


# ---------------------------------------------------------------- turning a channel on from the card

def test_weekly_email_from_the_card_is_counted_by_place_and_ends_the_asking(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    response = client.put("/api/for-you/email", headers=headers(user), json={"enabled": True, "source": "home_card"})
    assert response.status_code == 200 and response.json()["enabled"] is True
    reply(client, user, "email")
    assert counted("weekly_on_home_card", kind="email") == 1
    assert counted("card_email_library") == 1
    assert card(client, user) is None


def test_push_devices_are_counted_by_the_place_they_were_turned_on(client, db_session, monkeypatch):
    from tests.test_web_push import browser_keys
    monkeypatch.setattr(web_push, "deliver", lambda *args, **kwargs: None, raising=False)
    user = member(db_session)
    _, p256dh, key = browser_keys()
    body = {"endpoint": FCM, "keys": {"p256dh": p256dh, "auth": key}, "source": "home_card"}
    assert client.post("/notifications/push/subscription", headers=headers(user), json=body).status_code == 200
    assert counted("on_home_card", kind="push") == 1
    # Sending the same device again isn't a new one.
    client.post("/notifications/push/subscription", headers=headers(user), json=body)
    assert counted("on_home_card", kind="push") == 1
    other = member(db_session, name="sam")
    _, p256dh, key = browser_keys()
    body = {"endpoint": FCM + "x", "keys": {"p256dh": p256dh, "auth": key}, "source": "somewhere"}
    assert client.post("/notifications/push/subscription", headers=headers(other), json=body).status_code == 200
    assert not any(k == "push" and name.startswith("on_") and name != "on_home_card"
                   for (_, k, name) in RECORDER._pending)


# ---------------------------------------------------------------- the note after saving a show

def after(client, user, category="anime", push=True, title="Frieren"):
    return client.post("/api/stay-posted/after-save", headers=headers(user),
                       json={"category": category, "title": title, "push": push}).json()["offer"]


def test_saving_a_show_offers_notifications_then_waits_three_weeks(client, db_session):
    user = member(db_session, days_old=1, visit_days=1, titles=0)
    offer = after(client, user)
    assert offer["channel"] == "push" and offer["action"] == "Notify me on this device"
    assert offer["text"] == "Want a heads-up when new episodes of Frieren come out?"
    assert counted("after_shown") == 1
    assert after(client, user) is None
    row = stay_posted.get_row(db_session, user.id)
    row.after_save_at = datetime.utcnow() - timedelta(days=22)
    db_session.commit()
    assert after(client, user)["channel"] == "push"
    row.after_save_at = datetime.utcnow() - timedelta(days=22)
    db_session.commit()
    assert after(client, user) is None  # twice at most


def test_the_note_falls_back_to_email_and_skips_other_kinds(client, db_session, monkeypatch):
    user = member(db_session)
    assert after(client, user, category="movies") is None
    offer = after(client, user, push=False, title="Severance")
    assert offer["channel"] == "email" and "Severance" in offer["text"]
    assert reply(client, user, "email", place="after").json() == {"saved": True}
    assert counted("after_email") == 1
    other = member(db_session, name="kai")
    monkeypatch.setattr(digest, "mail_configured", lambda: False)
    assert after(client, other, push=False) is None


def test_the_note_waits_while_the_card_is_up_and_skips_brand_new_accounts(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    assert after(client, user) is None
    fresh = models.User(username="newbie", email="newbie@example.com", hashed_password="x", is_verified=True,
                        is_active=True, created_at=datetime.utcnow() - timedelta(minutes=5), visit_days=1)
    db_session.add(fresh)
    db_session.commit()
    assert after(client, fresh) is None


def test_endpoints_need_a_member(client):
    assert client.get("/api/stay-posted").status_code == 401
    assert client.post("/api/stay-posted/after-save", json={"category": "anime"}).status_code == 401


# ---------------------------------------------------------------- Site stats

def test_site_stats_summary_groups_the_counters(client, db_session):
    user = member(db_session)
    seen(client, user, "library")
    reply(client, user, "calendar")
    other = member(db_session, name="ash")
    after(client, other)
    reply(client, other, "later", place="after")
    for (day, kind, key), amount in RECORDER._pending.items():
        if kind == "stay":
            db_session.add(models.SiteTrafficDaily(day=day, kind=kind, key=key, count=amount))
    db_session.commit()
    summary = stay_posted.stats(db_session, 30, datetime.utcnow())
    assert summary["shown"] == 1
    assert summary["turned_on"] == {"push": 0, "email": 0, "calendar": 1}
    assert summary["after"]["shown"] == 1 and summary["later"] == 1
    library = next(row for row in summary["cards"] if row["moment"] == stay_posted.MOMENTS["library"])
    assert library["calendar"] == 1


# ---------------------------------------------------------------- what counts as coming up

def test_upcoming_lists_next_episodes_and_saved_releases_soonest_first(db_session, monkeypatch):
    from datetime import date
    from app import for_you, home_today
    user = member(db_session)
    today = date(2026, 11, 16)
    assert REAL_UPCOMING(db_session, user, today) == []
    monkeypatch.setattr(home_today, "show_updates", lambda db, user, today, since: [
        {"title": "Frieren", "category_label": "Anime", "next": {"code": "Episode 10", "date": "2026-11-20"}},
        {"title": "Finished Show", "category_label": "TV", "next": None},
    ])
    monkeypatch.setattr(for_you, "coming_up", lambda db, user_id, today: {"matches": [
        {"title": "Big Game", "label": "Game", "date": "2026-11-18", "reason": "In your library: Big Game"},
        {"title": "A Sequel", "label": "Movie", "date": "2026-11-19", "reason": "Because you track A Film"},
        {"title": "Old News", "label": "Movie", "date": "2026-11-10", "reason": "In your library: Old News"},
        {"title": "Far Off", "label": "Movie", "date": "2027-06-01", "reason": "In your library: Far Off"},
    ]})
    items = REAL_UPCOMING(db_session, user, today)
    assert [item["title"] for item in items] == ["Big Game", "Frieren"]
    assert items[1] == {"kind": "episode", "title": "Frieren", "label": "Anime", "what": "Episode 10", "date": "2026-11-20"}
