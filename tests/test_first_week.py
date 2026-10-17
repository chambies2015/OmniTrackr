"""First-week social steps on the library launchpad: friends, a public review, the weekly email."""
from datetime import datetime, timedelta

from app import digest, for_you, models
from tests.test_title_pages import LONG_REVIEW, add_movie, member

API = "/api/for-you/first-week"


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def test_new_member_sees_open_steps_and_a_title_to_review(authenticated_client, db_session, monkeypatch):
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    me = _me(db_session)
    me.created_at = datetime.utcnow() - timedelta(days=3)
    add_movie(db_session, member(db_session, "a"))
    add_movie(db_session, me, watched=True)
    add_movie(db_session, me, title="Nobody Else Has This", year=2001)
    db_session.commit()
    response = authenticated_client.get(API)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {
        "show": True, "friend": False, "public_review": False, "weekly_email": False,
        "email_available": True, "verified": True,
        "review_target": {"title": "Interstellar", "path": "/titles/movie/interstellar-2014"},
    }


def test_steps_tick_off_from_existing_data(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime.utcnow() - timedelta(days=10)
    friend = member(db_session, "pal")
    db_session.add(models.FriendRequest(sender_id=me.id, receiver_id=friend.id, status="pending"))
    add_movie(db_session, me, review=LONG_REVIEW, review_public=True)
    db_session.commit()
    digest.subscribe(db_session, me.id)
    data = authenticated_client.get(API).json()
    assert (data["friend"], data["public_review"], data["weekly_email"], data["review_target"]) == (True, True, True, None)

    db_session.query(models.FriendRequest).delete()
    db_session.add(models.Friendship(user1_id=friend.id, user2_id=me.id))
    db_session.commit()
    assert authenticated_client.get(API).json()["friend"] is True


def test_private_or_blank_reviews_do_not_count(db_session):
    me = member(db_session, "fresh")
    add_movie(db_session, me, review=LONG_REVIEW, review_public=False)
    add_movie(db_session, me, title="Heat", year=1995, review="   ", review_public=True)
    db_session.commit()
    assert for_you.first_week(db_session, me)["public_review"] is False


def test_longtime_members_are_left_alone(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime.utcnow() - timedelta(days=31)
    db_session.commit()
    assert authenticated_client.get(API).json() == {"show": False}


def test_requires_login(client):
    assert client.get(API).status_code == 401
