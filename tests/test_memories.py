"""On this day: memories from the same date in earlier years, six months and a month ago."""
import json
from datetime import date, datetime, timedelta

from app import memories, models, web_push
from tests.test_friend_recs import _as, _me
from tests.test_library_tags import add


def journal(db, user, category, title, action, when, item=None, rating=None, note=None):
    entry = models.ActivityEntry(user_id=user.id, category=category, item_id=item.id if item else None, title=title,
                                 action=action, rating=rating, note=note, occurred_at=when, source="manual")
    db.add(entry)
    db.commit()
    return entry


def collect(db, user, today, offset=0, **kwargs):
    return memories.collect(db, user, today, memories.offset_converter(offset), **kwargs)


def test_anchors_cover_earlier_years_and_skip_missing_month_days():
    today = date(2026, 3, 31)
    found = memories.anchors(today, date(2023, 1, 1))
    assert [(day.isoformat(), unit, count) for day, unit, count, _ in found] == [
        ("2025-03-31", "years", 1), ("2024-03-31", "years", 2), ("2023-03-31", "years", 3),
    ]  # no September 31 or February 31

    leap = memories.anchors(date(2027, 2, 28), date(2020, 1, 1), months=False)
    windows = {day.year: (day, last) for day, _, _, last in leap}
    assert windows[2024] == (date(2024, 2, 28), date(2024, 2, 29))  # the 29th shows on the 28th
    assert windows[2026] == (date(2026, 2, 28), date(2026, 2, 28))
    assert memories.anchors(date(2028, 2, 29), date(2027, 1, 1), months=False) == []
    assert [day for day, *_ in memories.anchors(date(2028, 2, 29), date(2024, 1, 1), months=False)] == [date(2024, 2, 29)]


def test_finish_from_two_years_ago_with_rating_art_and_reflection(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2023, 5, 1)
    dune = add(db_session, me, "books", "Dune", read=True, rating=9, cover_art_url="https://covers.openlibrary.org/b/id/1-L.jpg")
    journal(db_session, me, "books", "Dune", "completed", datetime(2024, 10, 29, 20, 0), dune, rating=9)
    db_session.add(models.CompletionMoment(user_id=me.id, category="books", item_id=dune.id, title="Dune", rating=9,
                                           takeaway="The spice must flow.", completed_at=datetime(2024, 10, 29, 20, 0)))
    journal(db_session, me, "books", "Dune", "completed", datetime(2024, 10, 28, 20, 0), dune)  # the day before
    db_session.commit()

    response = authenticated_client.get("/activity/on-this-day/", params={"tz_offset_minutes": 0})
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    body = memories.for_dashboard(db_session, me, 0, now=datetime(2026, 10, 29, 9, 0))
    [memory] = body["memories"]
    assert memory["label"] == "2 years ago today"
    assert memory["line"] == "You finished Dune and gave it 9/10."
    assert memory["note"] == "The spice must flow."
    assert memory["item_id"] == dune.id and memory["finished"] is True
    assert memory["image"].startswith("https://covers.openlibrary.org/")


def test_local_day_follows_the_browser_offset(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2024, 1, 1)
    db_session.commit()
    # 03:00 UTC on Oct 30 2025 is still Oct 29 in Chicago (UTC-5 in October, offset +300).
    journal(db_session, me, "movies", "Heat", "completed", datetime(2025, 10, 30, 3, 0))
    assert [m["title"] for m in collect(db_session, me, date(2026, 10, 29), offset=300)] == ["Heat"]
    assert collect(db_session, me, date(2026, 10, 29), offset=0) == []
    assert [m["title"] for m in collect(db_session, me, date(2026, 10, 30), offset=0)] == ["Heat"]


def test_one_memory_per_day_ranked_and_bulk_adds_collapse(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2026, 4, 29, 12, 0)
    db_session.commit()
    for index in range(6):
        add(db_session, me, "movies", f"Imported {index}", added_at=datetime(2026, 4, 29, 12, 5))
    journal(db_session, me, "tv-shows", "Severance", "started", datetime(2026, 9, 29, 21, 0))
    journal(db_session, me, "tv-shows", "Andor", "noted", datetime(2026, 9, 29, 22, 0), note="")  # empty note: skipped
    journal(db_session, me, "anime", "Frieren", "completed", datetime(2026, 9, 29, 23, 0))

    found = collect(db_session, me, date(2026, 10, 29))
    assert [(m["label"], m["kind"]) for m in found] == [("6 months ago today", "joined"), ("A month ago today", "finished")]
    assert found[0]["more"] == 1  # the import is behind the join
    assert found[1]["title"] == "Frieren" and found[1]["more"] == 1

    me.created_at = datetime(2026, 1, 1)
    db_session.commit()
    [bulk] = [m for m in collect(db_session, me, date(2026, 10, 29)) if m["unit"] == "months" and m["ago"] == 6]
    assert bulk["kind"] == "added_many" and bulk["line"] == "You added 6 titles to your library."


def test_nothing_from_other_members_or_today(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    other = models.User(username="someoneelse", email="else@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.commit()
    journal(db_session, other, "movies", "Not mine", "completed", datetime(2025, 10, 29, 12, 0))
    journal(db_session, me, "movies", "Today", "completed", datetime(2026, 10, 29, 8, 0))
    assert collect(db_session, me, date(2026, 10, 29)) == []


def test_week_in_past_years_for_the_email(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    db_session.commit()
    journal(db_session, me, "movies", "Alien", "completed", datetime(2023, 10, 25, 12, 0), rating=8)
    journal(db_session, me, "movies", "Started only", "started", datetime(2024, 10, 26, 12, 0))
    journal(db_session, me, "games", "Wrong category", "completed", datetime(2024, 10, 26, 12, 0))
    found = memories.week_in_past_years(db_session, me, date(2026, 10, 29))
    assert [(m["title"], m["ago"]) for m in found] == [("Alien", 3)]


def _push_member(db, user, topics, zone="America/Chicago"):
    db.add(models.PushPreference(user_id=user.id, topics=json.dumps(topics), quiet_hours=True, quiet_start=22,
                                 quiet_end=8, time_zone=zone))
    db.add(models.PushSubscription(user_id=user.id, endpoint="https://fcm.googleapis.com/fcm/send/abc",
                                   p256dh="x", auth="y"))
    db.commit()


def test_push_once_a_day_in_the_afternoon_when_switched_on(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    db_session.commit()
    journal(db_session, me, "movies", "Heat", "completed", datetime(2025, 10, 29, 18, 0), rating=10)
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 19, 0)) == 0  # topic off by default

    _push_member(db_session, me, {"memories": True})
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 4, 0)) == 0  # 11 pm in Chicago: quiet
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 19, 0)) == 1  # 2 pm in Chicago
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 20, 0)) == 0  # once a day
    [note] = db_session.query(models.Notification).filter_by(user_id=me.id, type="memory").all()
    assert note.message == "A year ago today: you watched Heat and gave it 10/10."
    assert note.link == "/#on-this-day"
    assert web_push.topic_of("memory") == "memories"
    assert not web_push.wants(None, "memory")


def test_weekly_email_section_never_forces_a_send():
    from app import digest
    report = {"matches": [], "popular": []}
    past = [{"ago": 3, "line": "You watched Alien and gave it 8/10."}]
    assert digest.build_digest("sam", report, "https://x/unsub", past=past) is None
    friends = [{"username": "pat", "count": 1, "titles": [{"title": "Heat", "label": "Movie", "done": None, "rating": None, "path": "/titles/movie/heat"}]}]
    built = digest.build_digest("sam", report, "https://x/unsub", friends=friends, past=past)
    assert built is not None
    _subject, html, text = built
    assert "This week in past years" in html and "3 years ago: you watched Alien and gave it 8/10." in text
    _, html, _ = digest.build_digest("sam", report, "https://x/unsub", friends=friends, past=[])
    assert "This week in past years" not in html
