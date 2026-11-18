"""Sweep of the Nov 18 2026 afternoon merges: the weekly email preview (#244), getting members talking
(#245: /discussions hub, openers, @mentions, shelf notes, Reply under reviews), the guide hub writing (#246)
and the bug walk fixes (#247), plus the morning sweep itself (#243)."""
from datetime import datetime, timedelta

import pytest

from app import models, title_discussions
from app.routers import for_you as for_you_router
from app.routers import title_discussions as discussions_router
from tests.test_security_sweep_nov06 import _limited
from tests.test_shared_lists import _as
from tests.test_title_pages import add_movie, member

API = "/api/titles/movie/interstellar-2014/discussions"
OPENER = "Did anyone else think the docking scene was the best part? The music there is something else."


@pytest.fixture(autouse=True)
def no_posting_gap(monkeypatch):
    monkeypatch.setattr(title_discussions, "POST_GAP_SECONDS", 0)


def _veteran(db, name):
    user = member(db, name)
    user.created_at = datetime.utcnow() - timedelta(days=30)
    db.flush()
    return user


def _start(client, subject="That docking scene", body=OPENER):
    response = client.post(API, json={"subject": subject, "body": body, "spoiler": False})
    assert response.status_code == 201, response.text
    return response.json()


def _notes(db, kind, link=None):
    query = db.query(models.Notification).filter(models.Notification.type == kind)
    if link:
        query = query.filter(models.Notification.link == link)
    return query.all()


# ---------------------------------------------------------------- rate limits

def test_every_discussion_api_route_is_rate_limited():
    """The friends feed rail's summary (new in #245) reads the member's recent library on each Friends tab
    open; the older list, delete and moderate routes had no limit either."""
    for route in discussions_router.router.routes:
        if not route.path.startswith("/api/"):
            continue
        for method in route.methods:
            assert _limited(discussions_router.router, route.path, method), (method, route.path)


def test_full_weekly_email_preview_page_is_rate_limited():
    """It builds the whole email on every load, with nothing cached (#244 added its sign-up button)."""
    assert _limited(for_you_router.router, "/email/weekly/preview", "GET")


# ---------------------------------------------------------------- shelf notes from brand-new accounts

def _trackers(db, count):
    found = []
    for number in range(count):
        tracker = member(db, f"tracker{number:02d}")
        add_movie(db, tracker, watched=True)
        found.append(tracker)
    return found


def test_a_brand_new_account_reaches_only_a_few_trackers(client, db_session):
    _trackers(db_session, title_discussions.NEW_ACCOUNT_SHELF_NOTES + 7)
    newcomer = member(db_session, "newcomer")  # signed up just now
    db_session.commit()
    _as(client, newcomer)
    _start(client)
    assert len(_notes(db_session, "discussion_started")) == title_discussions.NEW_ACCOUNT_SHELF_NOTES


def test_an_established_account_still_reaches_every_tracker(client, db_session):
    trackers = _trackers(db_session, title_discussions.NEW_ACCOUNT_SHELF_NOTES + 7)
    alice = _veteran(db_session, "alice")
    db_session.commit()
    _as(client, alice)
    _start(client)
    assert len(_notes(db_session, "discussion_started")) == len(trackers)


# ---------------------------------------------------------------- notes taken back when a thread is hidden

def _thread_with_notes(client, db_session):
    _trackers(db_session, 2)
    named = _veteran(db_session, "named")
    alice = _veteran(db_session, "alice")
    reporters = [_veteran(db_session, f"reporter{number}") for number in range(3)]
    db_session.commit()
    _as(client, alice)
    thread = _start(client, body="@named you added this last week, what did you make of the ending?")
    assert len(_notes(db_session, "discussion_started", thread["url"])) == 2
    assert len(_notes(db_session, "discussion_mention", thread["url"])) == 1
    return thread, alice, named, reporters


def test_hiding_a_thread_by_reports_takes_back_its_unread_notes(client, db_session):
    thread, alice, named, reporters = _thread_with_notes(client, db_session)
    # A tracker who already opened theirs keeps it: that's their own history.
    opened = _notes(db_session, "discussion_started", thread["url"])[0]
    opened.read_at = datetime.utcnow()
    db_session.commit()
    for reporter in reporters:
        _as(client, reporter)
        response = client.post(f"/api/discussions/{thread['id']}/report", json={"reason": "spam"})
        assert response.status_code == 200, response.text
    db_session.expire_all()
    assert [note.id for note in _notes(db_session, "discussion_started", thread["url"])] == [opened.id]
    assert not _notes(db_session, "discussion_mention", thread["url"])
    # Moderators still hear about the hide.
    assert db_session.get(models.TitleDiscussion, thread["id"]).hidden_at is not None


def test_a_moderator_hiding_a_thread_takes_back_its_unread_notes(client, db_session, monkeypatch):
    thread, alice, named, reporters = _thread_with_notes(client, db_session)
    moderator = _veteran(db_session, "modname")
    db_session.commit()
    monkeypatch.setenv("ADMIN_USERNAMES", "modname")
    _as(client, moderator)
    response = client.post(f"/api/discussions/{thread['id']}/moderate", json={"action": "hide"})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert not _notes(db_session, "discussion_started", thread["url"])
    assert not _notes(db_session, "discussion_mention", thread["url"])


def test_deleting_a_thread_with_no_replies_takes_back_its_unread_notes(client, db_session):
    thread, alice, named, reporters = _thread_with_notes(client, db_session)
    _as(client, alice)
    response = client.delete(f"/api/discussions/{thread['id']}")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert not _notes(db_session, "discussion_started", thread["url"])
    assert not _notes(db_session, "discussion_mention", thread["url"])


def test_hiding_one_reply_keeps_the_threads_notes(client, db_session):
    thread, alice, named, reporters = _thread_with_notes(client, db_session)
    bob = _veteran(db_session, "bob")
    db_session.commit()
    _as(client, bob)
    reply = client.post(f"/api/discussions/{thread['id']}/replies", json={"body": "Agreed, the docking scene is it."})
    assert reply.status_code == 201, reply.text
    reply_id = int(reply.json()["url"].rsplit("-", 1)[1])
    for reporter in reporters:
        _as(client, reporter)
        response = client.post(f"/api/discussions/{thread['id']}/report", json={"reason": "spam", "reply_id": reply_id})
        assert response.status_code == 200, response.text
    db_session.expire_all()
    assert len(_notes(db_session, "discussion_started", thread["url"])) == 2
    assert len(_notes(db_session, "discussion_mention", thread["url"])) == 1
