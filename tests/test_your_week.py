"""Your week: day tiles from what members already log, a weekly pace, kept weeks in a row, the Sunday nudge."""
import asyncio
from datetime import date, datetime, timedelta

import pytest

from app import auth, badges, check_in, digest, models, your_week
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
# A Wednesday, 15:00 UTC. In New York (UTC-5) it's 10 am on Wednesday Nov 18.
WEDNESDAY = datetime(2026, 11, 18, 15, 0)
THIS_MONDAY = date(2026, 11, 16)
NY = -300


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "yourweek" and name == key)


def member(db, name="iris", days_old=40, verified=True, titles=3):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=verified, is_active=True, created_at=WEDNESDAY - timedelta(days=days_old))
    db.add(user)
    db.commit()
    for index in range(titles):
        db.add(models.Movie(title=f"Film {index}", year=2020, watched=False, user_id=user.id,
                            added_at=WEDNESDAY - timedelta(days=60)))
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def log(db, user, at, action="progressed", title="Film 0"):
    movie = db.query(models.Movie).filter(models.Movie.user_id == user.id, models.Movie.title == title).first()
    db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=movie.id if movie else None,
                                title=title, action=action, occurred_at=at, source="manual"))
    db.commit()


def local(day: date, hour: int, tz: int = NY) -> datetime:
    """A member-local time on ``day`` as naive UTC."""
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour) - timedelta(minutes=tz)


def pick(db, user, goal="once", now=WEDNESDAY, tz=NY, started=None):
    your_week.set_goal(db, user, goal, tz, now=now)
    if started is not None:
        plan = your_week.get_plan(db, user.id)
        plan.started_week = started
        db.commit()


def test_card_waits_for_three_titles_and_the_end_of_week_one(db_session):
    fresh = member(db_session, "fresh", days_old=2)
    assert your_week.build(db_session, fresh, NY, now=WEDNESDAY) is None  # the first-week card has the screen
    small = member(db_session, "small", titles=2)
    assert your_week.build(db_session, small, NY, now=WEDNESDAY) is None  # the launchpad comes first
    ready = member(db_session, "ready")
    card = your_week.build(db_session, ready, NY, now=WEDNESDAY)
    assert card["status"] == "setup" and card["goal"] is None
    assert [goal["key"] for goal in card["goals"]] == ["once", "three", "most", "finish"]
    assert card["week_start"] == THIS_MONDAY.isoformat() and len(card["days"]) == 7
    assert [day["today"] for day in card["days"]].index(True) == 2
    assert card["label"] == "Nov 16 to 22"


def test_days_light_up_from_what_the_member_already_logs(db_session):
    user = member(db_session)
    log(db_session, user, local(THIS_MONDAY, 20))                                  # Monday evening, journal
    movie = db_session.query(models.Movie).filter(models.Movie.user_id == user.id).first()
    db_session.add(models.FriendFeedEvent(user_id=user.id, category="movies", item_id=movie.id, kind="rated",
                                          created_at=local(THIS_MONDAY + timedelta(days=1), 9)))  # Tuesday, a rating
    db_session.add(models.Book(title="Dune", user_id=user.id, read=False, added_at=local(THIS_MONDAY + timedelta(days=2), 8)))
    db_session.commit()
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert [day["logged"] for day in card["days"]] == [True, True, True, False, False, False, False]
    assert card["logged_days"] == 3
    assert {item["title"] for item in card["touched"]} >= {"Dune", "Film 0"}


def test_the_week_follows_the_members_own_clock(db_session):
    user = member(db_session)
    # Sunday 11:30 pm in New York is already Monday in UTC: it belongs to last week, on Sunday.
    log(db_session, user, local(THIS_MONDAY - timedelta(days=1), 23) + timedelta(minutes=30))
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["logged_days"] == 0
    assert card["history"][-1]["state"] == "active" and card["history"][-1]["days"] == 1
    # The same moment for a member in UTC lands on this Monday.
    assert your_week.build(db_session, user, 0, now=WEDNESDAY)["days"][0]["logged"] is True


def test_episode_progress_leaves_a_mark_at_most_every_half_hour(client, db_session):
    user = member(db_session, titles=0)
    show = models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id)
    db_session.add(show)
    db_session.commit()
    for revision, episode in ((0, 3), (1, 4)):
        response = client.put(f"/progress/tv-shows/{show.id}/episode", headers=headers(user),
                              json={"expected_revision": revision, "season": 1, "episode": episode})
        assert response.status_code == 200, response.text
    assert db_session.query(models.ProgressMark).filter(models.ProgressMark.user_id == user.id).count() == 1
    # Clearing a place is not progress.
    client.put(f"/progress/tv-shows/{show.id}", headers=headers(user),
               json={"expected_revision": 2, "unit": None, "position": None, "season": None, "note": None})
    assert db_session.query(models.ProgressMark).count() == 1


def test_a_pace_keeps_the_week_and_builds_a_run(db_session):
    user = member(db_session)
    for back in (3, 2, 1):
        log(db_session, user, local(THIS_MONDAY - timedelta(days=7 * back), 12))
    pick(db_session, user, "once", started=THIS_MONDAY - timedelta(days=21))
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["status"] == "open" and card["needed"] == 1 and card["run_before"] == 3 and card["run"] == 3
    assert [week["state"] for week in card["history"][-3:]] == ["kept", "kept", "kept"]
    log(db_session, user, local(THIS_MONDAY + timedelta(days=2), 9))
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["status"] == "kept" and card["run"] == 4 and card["best"] == 4 and card["kept_total"] == 4
    assert counted("kept") == 4 and counted("first_kept") == 1


def test_three_days_and_finish_paces(db_session):
    user = member(db_session)
    pick(db_session, user, "three")
    log(db_session, user, local(THIS_MONDAY, 12))
    log(db_session, user, local(THIS_MONDAY + timedelta(days=1), 12))
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["status"] == "open" and card["needed"] == 1 and card["days_left"] == 5
    assert card["can_rest"] is False  # no run yet, so nothing to take a week off from
    your_week.set_goal(db_session, user, "finish", NY, now=WEDNESDAY)
    assert your_week.build(db_session, user, NY, now=WEDNESDAY)["needed"] == 1
    log(db_session, user, local(THIS_MONDAY + timedelta(days=2), 9), action="completed", title="Film 1")
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["status"] == "kept" and card["finishes"] == 1
    assert counted("set_goal") == 1 and counted("changed_goal") == 1


def test_a_kept_week_stays_kept_when_its_title_is_deleted(db_session):
    user = member(db_session)
    pick(db_session, user, "once")
    db_session.add(models.Book(title="Gone", user_id=user.id, read=False, added_at=local(THIS_MONDAY, 10)))
    db_session.commit()
    assert your_week.build(db_session, user, NY, now=WEDNESDAY)["status"] == "kept"
    db_session.query(models.Book).filter(models.Book.title == "Gone").delete()
    db_session.commit()
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert card["status"] == "kept" and card["days"][0]["logged"] is True


def test_a_week_off_keeps_the_run_and_a_missed_week_ends_it(db_session):
    user = member(db_session)
    pick(db_session, user, "once", now=WEDNESDAY - timedelta(days=28))
    for back in (4, 2):
        log(db_session, user, local(THIS_MONDAY - timedelta(days=7 * back), 12))
    # Three weeks ago: a week off, taken that Thursday.
    your_week.take_rest(db_session, user, NY, now=WEDNESDAY - timedelta(days=20))
    card = your_week.build(db_session, user, NY, now=WEDNESDAY)
    # 4 back kept, 3 back rest, 2 back kept, last week missed: the run ended last week.
    assert [week["state"] for week in card["history"][-4:]] == ["kept", "rest", "kept", "missed"]
    assert card["run_before"] == 0 and card["best"] == 2
    assert card["can_rest"] is False  # one week off in any four
    with pytest.raises(ValueError):
        your_week.take_rest(db_session, user, NY, now=WEDNESDAY)
    later = WEDNESDAY + timedelta(days=7)
    log(db_session, user, local(THIS_MONDAY, 12))  # this week gets logged, so next week has a run to protect
    assert your_week.build(db_session, user, NY, now=later)["can_rest"] is True
    your_week.take_rest(db_session, user, NY, now=later)
    card = your_week.build(db_session, user, NY, now=later)
    assert card["status"] == "rest" and counted("rest") == 2
    your_week.take_rest(db_session, user, NY, undo=True, now=later)
    assert your_week.build(db_session, user, NY, now=later)["status"] == "open"


def test_monday_opens_on_last_weeks_recap(db_session):
    user = member(db_session)
    pick(db_session, user, "once", now=WEDNESDAY - timedelta(days=7))
    log(db_session, user, local(THIS_MONDAY - timedelta(days=5), 20), action="completed", title="Film 2")
    monday = local(THIS_MONDAY, 9)
    recap = your_week.build(db_session, user, NY, now=monday)["recap"]
    assert recap["kept"] is True and recap["days"] == 1 and recap["finishes"] == 1 and recap["run"] == 1
    assert [title["title"] for title in recap["finished"]] == ["Film 2"] and recap["label"] == "Nov 9 to 15"
    assert your_week.build(db_session, user, NY, now=local(THIS_MONDAY + timedelta(days=3), 9))["recap"] is None
    your_week.recap_seen(db_session, user, NY, now=monday)
    assert your_week.build(db_session, user, NY, now=monday)["recap"] is None
    assert counted("recap_seen") == 1


def test_endpoints_and_their_rules(client, db_session):
    user = member(db_session, verified=False)
    response = client.get(f"/api/your-week?tz={NY}", headers=headers(user))
    assert response.status_code == 200 and response.headers["Cache-Control"] == "private, no-store"
    assert response.json()["card"]["status"] == "setup"
    assert client.post("/api/your-week/goal", json={"goal": "weekly", "tz": NY}, headers=headers(user)).status_code == 422
    assert client.post("/api/your-week/remind", json={"email": True, "tz": NY}, headers=headers(user)).status_code == 422
    card = client.post("/api/your-week/goal", json={"goal": "three", "tz": NY}, headers=headers(user)).json()["card"]
    assert card["goal"]["key"] == "three" and card["goal"]["target"] == 3
    response = client.post("/api/your-week/remind", json={"email": True, "tz": NY}, headers=headers(user))
    assert response.status_code == 422 and "Confirm your email" in response.json()["detail"]
    response = client.post("/api/your-week/remind", json={"push": True, "tz": NY}, headers=headers(user))
    assert response.status_code == 422  # no device yet
    assert client.post("/api/your-week/seen", json={"tz": NY}, headers=headers(user)).status_code == 200
    assert counted("seen") == 1
    assert client.post("/api/your-week/hide", headers=headers(user)).json() == {"hidden": True}
    assert client.get(f"/api/your-week?tz={NY}", headers=headers(user)).json()["card"] is None
    card = client.post("/api/your-week/show", json={"tz": NY}, headers=headers(user)).json()["card"]
    assert card is not None and card["hidden"] is False
    card = client.post("/api/your-week/goal", json={"goal": None, "tz": NY}, headers=headers(user)).json()["card"]
    assert card["status"] == "setup" and counted("stopped") == 1
    assert client.get("/api/your-week").status_code == 401


def test_next_reminder_is_sunday_evening_local():
    assert your_week.next_remind_at(WEDNESDAY, NY) == datetime(2026, 11, 22, 23, 0)  # 6 pm New York
    sunday_late = datetime(2026, 11, 22, 23, 30)
    assert your_week.next_remind_at(sunday_late, NY) == datetime(2026, 11, 29, 23, 0)
    assert your_week.next_remind_at(WEDNESDAY, 9 * 60) == datetime(2026, 11, 22, 9, 0)  # Tokyo


def _remind(db, user, goal="three", email=True, push=False, now=WEDNESDAY):
    pick(db, user, goal, now=now)
    plan = your_week.get_plan(db, user.id)
    plan.remind_email, plan.remind_push, plan.remind_set_at = email, push, now
    plan.next_remind_at = your_week.next_remind_at(now, NY)
    db.commit()
    return plan


def _session(db):
    class Shared:
        def __call__(self):
            return self

        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            pass
    return Shared()


SUNDAY_EVENING = datetime(2026, 11, 22, 23, 5)


def test_sunday_email_goes_once_when_one_more_day_keeps_the_week(db_session):
    user = member(db_session)
    show = models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id, poster_url="https://img.example/s.jpg")
    db_session.add(show)
    db_session.commit()
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=show.id, unit="episode",
                                             position=4, season=1, revision=1, updated_at=local(THIS_MONDAY, 21)))
    db_session.commit()
    log(db_session, user, local(THIS_MONDAY + timedelta(days=3), 12))
    _remind(db_session, user)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html))

    result = asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender, pusher=lambda *a: 0))
    assert result["sent"] == 1 and len(sent) == 1
    to, subject, html = sent[0]
    assert to == "iris@example.com" and subject == "One more day keeps your week (2 of 3)"
    assert "Severance" in html and "/check-in/" in html and "Log it" in html and "#your-week" in html
    row = db_session.query(models.YourWeekWeek).filter(models.YourWeekWeek.week_start == THIS_MONDAY).one()
    assert row.nudged_at is not None
    plan = your_week.get_plan(db_session, user.id)
    assert plan.next_remind_at == datetime(2026, 11, 29, 23, 0)
    # Nothing twice: even if the plan were due again this week, the week is already nudged.
    plan.next_remind_at = SUNDAY_EVENING
    db_session.commit()
    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING + timedelta(minutes=15), sender=sender))
    assert len(sent) == 1
    assert counted("sent") == 1
    # The email's button logs progress without signing in, and that keeps the week.
    token = html.split("/check-in/")[1].split("?")[0]
    assert check_in.read_token(token)["source"] == "week"


def test_check_in_from_the_nudge_counts_the_day(client, db_session):
    user = member(db_session)
    pick(db_session, user, "once")
    movie = db_session.query(models.Movie).filter(models.Movie.user_id == user.id).first()
    token = check_in.make_token(user.id, [{"category": "movies", "id": movie.id}], "week")
    page = client.get(f"/check-in/{token}?pick=0&a=still", headers=CHROME)
    assert page.status_code == 200 and "Made some progress" in page.text and "YOUR WEEK" in page.text
    assert "Counted for this week" not in page.text  # a link alone never counts
    assert db_session.query(models.ProgressMark).count() == 0
    response = client.post(f"/check-in/{token}", data={"item": "0", "choice": "still", "ok": ""}, headers=CHROME,
                           follow_redirects=False)
    assert response.status_code == 303
    assert db_session.query(models.ProgressMark).filter(models.ProgressMark.user_id == user.id).count() == 1
    assert counted("logged_from_email") == 1
    assert your_week.build(db_session, user, 0)["logged_days"] >= 1


def test_sunday_nudge_is_skipped_when_not_needed(db_session):
    kept = member(db_session, "kept")
    log(db_session, kept, local(THIS_MONDAY, 12))
    _remind(db_session, kept, goal="once")
    far = member(db_session, "far")
    _remind(db_session, far, goal="most")  # five days needed, one day left
    sent = []

    async def sender(*args):
        sent.append(args)

    result = asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender, pusher=lambda *a: 0))
    assert sent == [] and result["skipped"] == 2 and counted("skipped") == 2
    assert all(plan.next_remind_at == datetime(2026, 11, 29, 23, 0) for plan in db_session.query(models.YourWeekPlan))


def test_late_or_unsubscribed_nudges_are_dropped(db_session):
    late = member(db_session, "late")
    _remind(db_session, late, goal="once")
    out = member(db_session, "out")
    _remind(db_session, out, goal="once")
    db_session.add(models.EmailOptOut(user_id=out.id, created_at=WEDNESDAY + timedelta(hours=1)))
    db_session.commit()
    sent = []

    async def sender(*args):
        sent.append(args)

    plan = your_week.get_plan(db_session, late.id)
    plan.next_remind_at = SUNDAY_EVENING - timedelta(hours=4)  # the app was asleep through Sunday evening
    db_session.commit()
    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender))
    assert sent == [] and plan.next_remind_at == datetime(2026, 11, 29, 23, 0)
    assert your_week.get_plan(db_session, out.id).remind_email is False
    assert counted("dropped") == 2


def test_push_only_nudge(db_session):
    user = member(db_session)
    _remind(db_session, user, goal="once", email=False, push=True)
    pushed = []

    def pusher(db, user_id, message, now):
        pushed.append((user_id, message))
        return 1

    async def sender(*args):
        raise AssertionError("no email was asked for")

    result = asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, sender=sender, pusher=pusher))
    assert result["pushed"] == 1 and pushed == [(user.id, "Nothing logged yet this week. One episode or chapter tonight keeps your week.")]
    assert counted("push_sent") == 1


def test_coming_back_after_a_nudge_and_keeping_the_week_are_counted(db_session):
    user = member(db_session)
    _remind(db_session, user, goal="once", email=False, push=True)
    asyncio.run(your_week.send_due(_session(db_session), now=SUNDAY_EVENING, pusher=lambda *a: 1))
    log(db_session, user, SUNDAY_EVENING + timedelta(minutes=20))
    card = your_week.build(db_session, user, NY, now=SUNDAY_EVENING + timedelta(minutes=30))
    assert card["status"] == "kept"
    assert counted("back_after_nudge") == 1 and counted("kept_after_nudge") == 1


def test_steady_badge_counts_kept_weeks(db_session):
    user = member(db_session)
    pick(db_session, user, "once", started=THIS_MONDAY - timedelta(days=28))
    for back in range(4):
        log(db_session, user, local(THIS_MONDAY - timedelta(days=7 * back), 12))
    your_week.build(db_session, user, NY, now=WEDNESDAY)
    assert badges.counts(db_session, user)["weeks_kept"] == 4
    track = badges.BY_KEY["steady"]
    assert badges.tier_for(track, 4) == 1 and badges.LINKS["steady"] == "/#your-week"


def test_site_stats_numbers(db_session):
    user = member(db_session)
    _remind(db_session, user, goal="three")
    other = member(db_session, "other")
    pick(db_session, other, "once")
    log(db_session, other, local(THIS_MONDAY, 12))
    your_week.build(db_session, other, NY, now=WEDNESDAY)
    found = your_week.stats(db_session, 30, WEDNESDAY)
    assert found["with_pace"] == 2 and found["email_on"] == 1 and found["kept_all_time"] == 1
    assert {row["pace"]: row["count"] for row in found["by_pace"]}["Three days a week"] == 1
    assert set(found["labels"]) == set(your_week.COUNTERS)
