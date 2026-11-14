"""Sweep of the Nov 14 merges: the Nov 14 sweep itself (#208), public profile spotlight and
Right now (#209) and the advent calendar (#210). Also the badge key two tracks shared."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app import advent_calendar as advent, badges, migrations, models, public_profiles, title_search, web_push
from app.database import Base
from app.routers import advent_calendar as advent_router
from tests.conftest import engine
from tests.test_advent_calendar import DEC_5_NOON, NOVEMBER, at  # noqa: F401  (fixture)
from tests.test_public_profiles import enable, library, member


def _statements(fn):
    seen = []

    def hook(conn, cursor, statement, *args):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return result, seen


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _podcasts(db_session, user, count):
    db_session.add_all([models.Podcast(user_id=user.id, title=f"Show {index}", listened=True) for index in range(count)])
    db_session.commit()


# ---------------------------------------------------------------- the shared badge key

def test_every_badge_track_has_its_own_key():
    keys = [track["key"] for track in badges.TRACKS]
    assert len(keys) == len(set(keys))
    assert badges.BY_KEY["podcaster"]["name"] == "Podcast Regular"
    assert badges.BY_KEY["regular"]["metric"] == "visit_days"


def test_podcasts_and_visits_no_longer_share_a_tier(authenticated_client, db_session):
    user = _user(db_session)
    user.visit_days = 30
    db_session.commit()
    _podcasts(db_session, user, 5)
    data = authenticated_client.get("/api/badges").json()
    rows = {row["key"]: row for row in data["badges"]}
    # Before, both shared one saved row: the first save broke the unique key and nothing was kept.
    assert (rows["regular"]["tier"], rows["podcaster"]["tier"]) == (2, 1)
    stored = {row.badge: row.tier for row in db_session.query(models.UserBadge).filter_by(user_id=user.id)}
    assert stored["regular"] == 2 and stored["podcaster"] == 1


def _badge_db(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{(tmp_path / 'badges.db').as_posix()}")
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(migrations, "engine", test_engine)
    return test_engine


def _seed(test_engine, user_id, visit_days, podcasts, tier, seen=True):
    with Session(test_engine) as db:
        db.add(models.User(id=user_id, username=f"member{user_id}", email=f"m{user_id}@example.com",
                           hashed_password="x", visit_days=visit_days))
        db.add_all([models.Podcast(user_id=user_id, title=f"Show {index}", listened=True) for index in range(podcasts)])
        db.add(models.UserBadge(user_id=user_id, badge="regular", tier=tier, earned_at=datetime(2026, 10, 20),
                                seen_at=datetime(2026, 10, 21) if seen else None))
        db.commit()


def _stored(test_engine):
    with test_engine.connect() as conn:
        return {(user_id, badge): (tier, seen is not None) for user_id, badge, tier, seen in conn.execute(
            text("SELECT user_id, badge, tier, seen_at FROM user_badges")).fetchall()}


def test_old_shared_rows_are_split_without_losing_a_tier(tmp_path, monkeypatch):
    test_engine = _badge_db(tmp_path, monkeypatch)
    _seed(test_engine, 1, visit_days=40, podcasts=6, tier=2)    # silver from visits; podcasts reach bronze
    _seed(test_engine, 2, visit_days=40, podcasts=0, tier=2)    # visits only
    _seed(test_engine, 3, visit_days=10, podcasts=30, tier=2)   # silver can only be podcasts; visits reach bronze
    _seed(test_engine, 4, visit_days=2, podcasts=5, tier=1)     # bronze from podcasts; no visit tier
    _seed(test_engine, 5, visit_days=3, podcasts=2, tier=1, seen=False)  # podcasts since removed, celebration pending

    migrations.split_shared_regular_badge()

    assert _stored(test_engine) == {
        (1, "regular"): (2, True), (1, "podcaster"): (1, True),
        (2, "regular"): (2, True),
        (3, "podcaster"): (2, True), (3, "regular"): (1, True),
        (4, "podcaster"): (1, True),
        (5, "podcaster"): (1, False),
    }
    test_engine.dispose()


def test_the_split_runs_once(tmp_path, monkeypatch):
    test_engine = _badge_db(tmp_path, monkeypatch)
    _seed(test_engine, 1, visit_days=2, podcasts=5, tier=1)
    migrations.split_shared_regular_badge()
    first = _stored(test_engine)
    # After the fix a "regular" row is always the visits badge; a later start must leave it.
    _seed(test_engine, 2, visit_days=8, podcasts=30, tier=1)
    migrations.split_shared_regular_badge()
    assert _stored(test_engine) == {**first, (2, "regular"): (1, True)}
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM data_fixes")).fetchall() == [(migrations.REGULAR_BADGE_FIX,)]
    test_engine.dispose()


def test_the_split_runs_on_startup():
    import inspect as pyinspect
    assert "split_shared_regular_badge()" in pyinspect.getsource(migrations.run_migrations)


# ---------------------------------------------------------------- advent calendar

def test_preview_share_card_is_never_kept_by_a_shared_cache(authenticated_client, at, monkeypatch):
    at(NOVEMBER)
    monkeypatch.setattr(advent_router, "is_site_admin", lambda user: user is not None and user.username == "testuser")
    card = authenticated_client.get("/holidays/advent-calendar/2026/20/card.png")
    assert card.status_code == 200
    # A public cache would hand the pick to everyone before the door opens.
    assert card.headers["Cache-Control"] == "private, no-store"


def test_open_share_card_is_still_cached(client, at):
    at(DEC_5_NOON)
    card = client.get("/holidays/advent-calendar/2026/4/card.png")
    assert card.status_code == 200 and card.headers["Cache-Control"] == "public, max-age=3600"


def test_reminders_reach_members_past_the_first_page(db_session, at, monkeypatch):
    # Members waiting for their morning used to fill the one page read each hour, for good.
    monkeypatch.setattr(advent, "PER_RUN_LIMIT", 2)
    sent = []
    monkeypatch.setattr(web_push, "deliver",
                        lambda db, messages, http=None, now=None: sent.extend(messages) or {"sent": len(messages)})
    users = []
    for index, zone in enumerate(("Pacific/Honolulu", "Pacific/Honolulu", "Pacific/Honolulu", "Europe/London")):
        user = models.User(username=f"elf{index}", email=f"elf{index}@example.com", hashed_password="x", is_verified=True)
        db_session.add(user)
        db_session.commit()
        db_session.add(models.PushSubscription(user_id=user.id, endpoint=f"https://fcm.googleapis.com/fcm/send/elf{index}",
                                               p256dh="x", auth="y"))
        db_session.add(models.PushPreference(user_id=user.id, time_zone=zone, quiet_hours=False))
        db_session.add(models.AdventReminder(user_id=user.id, year=2026, last_day=5))
        db_session.commit()
        users.append(user.id)
    # 9am in London on December 6, still December 5 in Honolulu.
    at(datetime(2026, 12, 6, 9, 0))
    stats = advent.send_reminders(db_session)
    assert stats["members"] == 1 and [message[0] for message in sent] == [users[3]]


def test_reminders_skip_members_already_told_about_the_newest_door(db_session, at):
    for index in range(3):
        user = models.User(username=f"told{index}", email=f"told{index}@example.com", hashed_password="x", is_verified=True)
        db_session.add(user)
        db_session.commit()
        db_session.add(models.AdventReminder(user_id=user.id, year=2026, last_day=6))
    db_session.commit()
    at(datetime(2026, 12, 5, 12, 0))  # door 6 is the newest anywhere
    _, statements = _statements(lambda: advent.send_reminders(db_session))
    assert not any("push_preferences" in statement for statement in statements)


def test_door_details_are_worked_out_once_per_title_index(db_session, at, monkeypatch):
    calls = []
    real = advent_router._match_details
    monkeypatch.setattr(advent_router, "_match_details", lambda index, year: calls.append(year) or real(index, year))
    advent_router._DETAILS.clear()
    first = advent_router._details(db_session, 2026)
    assert advent_router._details(db_session, 2026) == first and calls == [2026]
    title_search.clear_cache()  # a rebuilt index is a new list
    advent_router._details(db_session, 2026)
    assert len(calls) == 2


# ---------------------------------------------------------------- public profile

def test_profile_reads_the_supporter_row_once_and_the_rating_spread_in_one_query(client, db_session):
    user = member(db_session, "spready")
    library(db_session, user)
    enable(db_session, user)
    client.get("/u/spready")
    response, statements = _statements(lambda: client.get("/u/spready"))
    assert response.status_code == 200 and "profile-spread" in response.text
    assert sum(1 for statement in statements if "FROM supporters" in statement) == 1
    spread = [statement for statement in statements if "UNION ALL" in statement and ".rating" in statement]
    assert len(spread) == 1


def test_rating_spread_matches_one_query_per_shelf(db_session):
    user = member(db_session, "spread2")
    library(db_session, user)
    db_session.add(models.Book(user_id=user.id, title="Half", author="A", year=2001, rating=7.5, read=True))
    db_session.commit()
    spread = public_profiles._rating_spread(db_session, user)
    assert len(spread) == 10 and spread[7] >= 1 and spread[9] >= 1  # 7.5 rounds up to 8; Interstellar is a 10
    user.movies_private = True
    user.books_private = True
    db_session.commit()
    hidden = public_profiles._rating_spread(db_session, user)
    assert not hidden or hidden[9] == 0

