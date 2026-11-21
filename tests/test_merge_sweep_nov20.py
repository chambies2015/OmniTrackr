"""Nov 20 2026 sweep of the title page redesign (#253), Your week (#254) and the speed pass (#255)."""
import asyncio
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from sqlalchemy import event

from app import auth, check_in, digest, models, your_week
from app.site_traffic import RECORDER
from tests.conftest import engine

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
WEDNESDAY = datetime(2026, 11, 18, 15, 0)  # 10 am in New York
THIS_MONDAY = date(2026, 11, 16)
SUNDAY_EVENING = datetime(2026, 11, 22, 23, 5)  # just after 6 pm in New York
NY = -300


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(kind, key):
    return sum(amount for (_, found_kind, name), amount in RECORDER._pending.items() if found_kind == kind and name == key)


def member(db, name="iris", titles=3):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=WEDNESDAY - timedelta(days=60))
    db.add(user)
    db.commit()
    for index in range(titles):
        db.add(models.Movie(title=f"Film {index}", year=2020, watched=False, user_id=user.id,
                            added_at=WEDNESDAY - timedelta(days=60)))
    db.commit()
    return user


def local(day: date, hour: int) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour) - timedelta(minutes=NY)


def log(db, user, at, action="progressed", title="Film 0"):
    movie = db.query(models.Movie).filter(models.Movie.user_id == user.id, models.Movie.title == title).first()
    db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=movie.id if movie else None,
                                title=title, action=action, occurred_at=at, source="manual"))
    db.commit()


class Statements:
    def __init__(self):
        self.seen = []

    def __enter__(self):
        event.listen(engine, "before_cursor_execute", self.record)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "before_cursor_execute", self.record)

    def record(self, conn, cursor, statement, params, context, executemany):
        self.seen.append(statement)

    def writes(self):
        return [s for s in self.seen if s.lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE")]


def path_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


def _session(db):
    class Shared:
        def __call__(self):
            return self

        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            pass
    return Shared()


def _remind(db, user, goal="once", email=True, push=False, now=WEDNESDAY):
    your_week.set_goal(db, user, goal, NY, now=now)
    plan = your_week.get_plan(db, user.id)
    plan.remind_email, plan.remind_push, plan.remind_set_at = email, push, now
    plan.next_remind_at = your_week.next_remind_at(now, NY)
    db.commit()
    return plan


# ---------------------------------------------------------------- Your week: work per home screen load

def test_looking_at_the_card_again_writes_nothing(db_session):
    user = member(db_session)
    your_week.set_goal(db_session, user, "three", NY, now=WEDNESDAY - timedelta(days=21))
    plan = your_week.get_plan(db_session, user.id)
    plan.started_week = THIS_MONDAY - timedelta(days=21)
    db_session.commit()
    log(db_session, user, local(THIS_MONDAY, 12))
    first = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert first["logged_days"] == 1
    before = {row.week_start: row.updated_at for row in db_session.query(models.YourWeekWeek)}
    with Statements() as sql:
        again = your_week.build(db_session, user, NY, now=WEDNESDAY + timedelta(minutes=5))
    assert again["logged_days"] == 1 and again["history"] == first["history"]
    assert sql.writes() == []  # it used to rewrite this week's row (and commit) on every home load
    assert {row.week_start: row.updated_at for row in db_session.query(models.YourWeekWeek)} == before
    # Something new still grows the week, and only then is it written.
    log(db_session, user, local(THIS_MONDAY + timedelta(days=1), 12))
    with Statements() as sql:
        grown = your_week.build(db_session, user, NY, now=WEDNESDAY + timedelta(minutes=10))
    assert grown["logged_days"] == 2 and len(sql.writes()) == 1


def test_the_card_reads_its_days_and_titles_in_a_few_queries(client, db_session):
    user = member(db_session, titles=0)
    for index in range(6):
        db_session.add(models.Movie(title=f"Film {index}", year=2020, watched=False, user_id=user.id,
                                    added_at=local(THIS_MONDAY, 8 + index)))
        db_session.add(models.Book(title=f"Book {index}", read=False, user_id=user.id, added_at=local(THIS_MONDAY, 9 + index)))
        db_session.add(models.Anime(title=f"Show {index}", watched=False, user_id=user.id, added_at=WEDNESDAY - timedelta(days=30)))
    db_session.commit()
    for index in range(4):
        log(db_session, user, local(THIS_MONDAY + timedelta(days=1), 10 + index), title=f"Film {index}")
    your_week.set_goal(db_session, user, "most", NY, now=WEDNESDAY)
    your_week.build(db_session, user, NY, now=WEDNESDAY)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}
    with Statements() as sql:
        response = client.get(f"/api/your-week?tz={NY}", headers=headers)
    card = response.json()["card"]
    assert len(card["touched"]) == your_week.TOUCHED_LIMIT
    library = [s for s in sql.seen if any(f"FROM {table}" in " ".join(s.split()) for table in ("movies", "books", "anime"))]
    # Was 9 queries for the days, 9 for this week's adds and one per title shown (41 in all).
    assert len(sql.seen) <= 15, sql.seen
    assert len(library) <= 4, library


def test_card_days_match_one_by_one_counting(db_session):
    user = member(db_session)
    show = models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id, added_at=local(THIS_MONDAY, 7))
    db_session.add(show)
    db_session.commit()
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=show.id, unit="episode",
                                             position=3, season=1, revision=1, updated_at=local(THIS_MONDAY + timedelta(days=2), 8)))
    db_session.add(models.ProgressMark(user_id=user.id, at=local(THIS_MONDAY + timedelta(days=1), 22)))
    db_session.add(models.ProgressMark(user_id=user.id, at=local(THIS_MONDAY - timedelta(days=1), 22)))  # last Sunday
    db_session.commit()
    stamps = your_week._stamps(db_session, user.id, *your_week.week_bounds(THIS_MONDAY, NY))
    assert sorted(stamps) == sorted([local(THIS_MONDAY, 7), local(THIS_MONDAY + timedelta(days=2), 8),
                                     local(THIS_MONDAY + timedelta(days=1), 22)])
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert [day["logged"] for day in card["days"]][:3] == [True, True, True]
    assert [title["title"] for title in card["touched"]][:1] == ["Severance"]


# ---------------------------------------------------------------- Your week: the Sunday email can always be stopped

def test_sunday_email_is_not_offered_to_members_who_turned_product_emails_off(client, db_session):
    user = member(db_session)
    db_session.add(models.EmailOptOut(user_id=user.id, created_at=WEDNESDAY - timedelta(days=10)))
    db_session.commit()
    your_week.set_goal(db_session, user, "once", NY, now=WEDNESDAY)
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["remind"]["offer_email"] is False
    with pytest.raises(ValueError, match="turned off OmniTrackr emails"):
        your_week.set_reminder(db_session, user, True, None, NY, now=WEDNESDAY)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}
    response = client.post("/api/your-week/remind", json={"email": True, "tz": NY}, headers=headers)
    assert response.status_code == 422 and "Settings" in response.json()["detail"]
    assert your_week.get_plan(db_session, user.id).remind_email is False


def test_an_earlier_unsubscribe_stops_the_sunday_email(db_session):
    """An opt-out older than the switch used to let the email through, and its footer link could not stop it."""
    user = member(db_session)
    _remind(db_session, user)
    db_session.add(models.EmailOptOut(user_id=user.id, created_at=WEDNESDAY - timedelta(days=30)))
    db_session.commit()
    sent = []

    async def sender(*args):
        sent.append(args)

    result = asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender))
    assert sent == [] and result["dropped"] == 1
    assert your_week.get_plan(db_session, user.id).remind_email is False


def test_the_footer_link_in_the_sunday_email_stops_the_next_one(client, db_session):
    user = member(db_session)
    _remind(db_session, user)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append(unsubscribe_url)

    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender))
    assert len(sent) == 1
    assert client.post(path_of(sent[0]), headers=CHROME).status_code == 200
    card = your_week.build(db_session, user, NY, now=SUNDAY_EVENING + timedelta(days=3))
    assert card["remind"]["email"] is False  # reads off straight away
    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING + timedelta(days=7), sender=sender))
    assert len(sent) == 1
    assert your_week.get_plan(db_session, user.id).remind_email is False


def test_per_run_limit_holds_within_one_check(db_session, monkeypatch):
    monkeypatch.setattr(your_week, "PER_RUN_LIMIT", 2)
    plans = [_remind(db_session, member(db_session, f"m{index}")) for index in range(4)]
    sent = []

    async def sender(to, *args):
        sent.append(to)

    result = asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender))
    assert len(sent) == 2 and result["limited"] is True
    waiting = [plan for plan in plans if plan.next_remind_at <= SUNDAY_EVENING]
    assert len(waiting) == 2  # still due: the next check sends them
    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING + timedelta(minutes=15), sender=sender))
    assert len(sent) == 4 and len(set(sent)) == 4


# ---------------------------------------------------------------- the email's Log it buttons

def test_opening_a_log_it_link_counts_nothing_and_saves_nothing(client, db_session):
    user = member(db_session)
    your_week.set_goal(db_session, user, "once", NY)
    movie = db_session.query(models.Movie).filter(models.Movie.user_id == user.id).first()
    token = check_in.make_token(user.id, [{"category": "movies", "id": movie.id}], "week")
    for link in (check_in.link_for(token, 0), check_in.link_for(token, 0, "still"), check_in.link_for(token, 0, "finished")):
        page = client.get(path_of(link), headers=CHROME)
        assert page.status_code == 200
    assert counted("checkin", "still_week") == 0
    assert db_session.query(models.ProgressMark).count() == 0
    db_session.refresh(movie)
    assert movie.watched is False
    # A tampered link is refused; a press on a real one counts once.
    assert client.post(f"/check-in/{token[:-2]}xx", data={"item": "0", "choice": "still"}, headers=CHROME,
                       follow_redirects=False).status_code == 404
    client.post(f"/check-in/{token}", data={"item": "0", "choice": "still", "ok": ""}, headers=CHROME, follow_redirects=False)
    assert counted("checkin", "still_week") == 1
    assert db_session.query(models.ProgressMark).count() == 1
