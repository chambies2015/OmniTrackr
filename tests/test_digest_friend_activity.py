"""Weekly email: what friends added to their libraries this week (Oct 22)."""
import asyncio
from datetime import datetime, timedelta

from app import digest, for_you, models
from tests.conftest import TestingSessionLocal
from tests.test_for_you import TODAY, member, pinned_today  # noqa: F401  (fixture)

NOW = datetime(2026, 9, 29, 12)


def befriend(db, a, b):
    db.add(models.Friendship(user1_id=min(a.id, b.id), user2_id=max(a.id, b.id)))
    db.flush()


def add_book(db, user, title, days_ago=1, rating=None, read=False):
    db.add(models.Book(user_id=user.id, title=title, author="A", year=2020, rating=rating, read=read,
                       added_at=NOW - timedelta(days=days_ago)))
    db.flush()


def test_lists_recent_additions_with_rating_and_status(db_session):
    me, sam = member(db_session, "me"), member(db_session, "sam")
    befriend(db_session, me, sam)
    add_book(db_session, sam, "Dune", rating=9, read=True)
    add_book(db_session, sam, "Unrated", days_ago=2)
    add_book(db_session, sam, "Old news", days_ago=10, rating=10, read=True)
    db_session.add(models.TVShow(user_id=sam.id, title="Severance", year=2022, watched=True, rating=8.5,
                                 added_at=NOW - timedelta(days=3)))
    db_session.commit()
    activity = digest.friend_activity(db_session, me.id, NOW)
    assert len(activity) == 1 and activity[0]["username"] == "sam" and activity[0]["count"] == 3
    assert [t["title"] for t in activity[0]["titles"]] == ["Dune", "Severance"]
    assert activity[0]["titles"][0]["done"] == "read" and activity[0]["titles"][0]["rating"] == 9

    _html, text = digest._friends_section(activity, "https://x")
    assert "- sam added Dune (Book, read, 9/10), Severance (TV show, watched, 8.5/10) and 1 more title" in text


def test_private_categories_inactive_friends_and_strangers_stay_out(db_session):
    me = member(db_session, "me")
    private, gone, stranger = member(db_session, "private"), member(db_session, "gone"), member(db_session, "stranger")
    private.books_private = True
    gone.is_active = False
    befriend(db_session, me, private)
    befriend(db_session, me, gone)
    for user in (private, gone, stranger):
        add_book(db_session, user, f"{user.username} book")
    db_session.commit()
    assert digest.friend_activity(db_session, me.id, NOW) == []


def test_a_big_import_does_not_hide_other_friends(db_session):
    me, bulk, quiet = member(db_session, "me"), member(db_session, "bulk"), member(db_session, "quiet")
    befriend(db_session, me, bulk)
    befriend(db_session, me, quiet)
    for index in range(30):
        add_book(db_session, bulk, f"Import {index}", rating=10)
    add_book(db_session, quiet, "Piranesi")
    db_session.commit()
    activity = digest.friend_activity(db_session, me.id, NOW)
    assert [(f["username"], f["count"]) for f in activity] == [("bulk", 30), ("quiet", 1)]
    assert [t["title"] for t in activity[1]["titles"]] == ["Piranesi"]


def test_section_is_escaped_and_friends_alone_make_an_email():
    activity = [{"username": "sam<b>", "count": 1,
                 "titles": [{"title": "Dune <i>", "label": "Book", "done": None, "rating": None, "path": None}]}]
    subject, html, text = digest.build_digest("me", {"matches": [], "popular": []}, "https://x/unsub", friends=activity)
    assert subject == "New on your friends' shelves: sam<b> added Dune <i>"
    assert "sam&lt;b&gt;" in html and "Dune &lt;i&gt;" in html and "<b>" not in html.split("sam")[1][:10]
    assert "here is what your friends added this week" in html
    assert "https://x/unsub" in text


def run(**kwargs):
    sent = []

    async def sender(to, subject, html, url):
        sent.append((to, subject, html))

    asyncio.run(digest.send_due_digests(TestingSessionLocal, sender=sender, today=TODAY, **kwargs))
    return sent


def test_friend_activity_sends_in_a_quiet_week(db_session, pinned_today, monkeypatch):  # noqa: F811
    monkeypatch.setattr(for_you, "upcoming_popular", lambda *a, **k: [])
    me, sam, lonely = member(db_session, "me"), member(db_session, "sam"), member(db_session, "lonely")
    befriend(db_session, me, sam)
    add_book(db_session, sam, "Dune", rating=9, read=True)
    db_session.commit()
    digest.subscribe(db_session, me.id)
    digest.subscribe(db_session, lonely.id)
    sent = run(now=NOW)
    assert [to for to, _s, _h in sent] == ["me@example.com"]
    assert "New on your friends' shelves" in sent[0][2] and "Dune" in sent[0][2]
