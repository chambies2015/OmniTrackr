"""October 11 sweep: month-boundary challenge sharing, race-safe completions, reactivation lockout."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from app import auth, challenges, goals, models
from app.crud.friends import create_notification


TEST_CHALLENGE = {
    "name": "Test the strange",
    "tagline": "A test challenge.",
    "published": "2026-10-10",
    "edition": "october-2026",
    "intro": ["Intro paragraph."],
    "steps": [{"kind": "reflect", "count": 1, "label": "Rate one", "detail": "d"}],
    "reflection": "Think.",
}


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _previous_month(month: str) -> str:
    year, number = (int(part) for part in month.split("-"))
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"


def _completed_entry(db_session, user, month):
    entry = models.MonthlyChallengeEntry(user_id=user.id, month=month, completed_at=datetime.utcnow())
    db_session.add(entry)
    db_session.commit()
    return entry


def test_last_months_completion_can_still_be_shared_and_unshared(authenticated_client, db_session, monkeypatch):
    month = _previous_month(challenges.month_key())
    monkeypatch.setitem(challenges.CHALLENGES, month, TEST_CHALLENGE)
    _completed_entry(db_session, _user(db_session), month)

    assert authenticated_client.put("/api/challenge/share").status_code == 404  # this month: not done
    shared = authenticated_client.put(f"/api/challenge/share?month={month}")
    assert shared.status_code == 200 and shared.json()["shared"] is True
    assert authenticated_client.post(f"/api/challenge/seen?month={month}").status_code == 200
    stopped = authenticated_client.delete(f"/api/challenge/share?month={month}")
    assert stopped.status_code == 200 and stopped.json()["shared"] is False


@pytest.mark.parametrize("month", ["2026-13", "26-10", "next", "2999-01"])
def test_share_rejects_bad_or_future_months(authenticated_client, db_session, month):
    _completed_entry(db_session, _user(db_session), "2999-01")
    assert authenticated_client.put(f"/api/challenge/share?month={month}").status_code in (404, 422)


def test_challenge_completion_is_claimed_once(authenticated_client, db_session, monkeypatch):
    month = challenges.month_key()
    monkeypatch.setitem(challenges.CHALLENGES, month, TEST_CHALLENGE)
    user = _user(db_session)
    entry = models.MonthlyChallengeEntry(user_id=user.id, month=month)
    db_session.add(entry)
    db_session.commit()
    steps = [{"done": True}]
    # Another request completes the entry after this one loaded it.
    db_session.query(models.MonthlyChallengeEntry).filter_by(id=entry.id).update(
        {"completed_at": datetime.utcnow()}, synchronize_session=False)
    db_session.commit()
    entry.completed_at = None  # this request's stale view

    assert challenges.record_completed(db_session, user, month, entry, steps) is False
    assert db_session.query(models.Notification).filter_by(type="challenge_complete").count() == 0


def test_joining_twice_returns_the_existing_entry(authenticated_client, db_session):
    user = _user(db_session)
    first = challenges.join(db_session, user.id, "2026-10")
    db_session.add(models.MonthlyChallengeEntry(user_id=user.id, month="2026-11"))
    db_session.commit()
    assert challenges.join(db_session, user.id, "2026-10").id == first.id
    assert challenges.join(db_session, user.id, "2026-11").month == "2026-11"


def test_notification_link_is_present_when_first_flushed(authenticated_client, db_session):
    seen = []

    def capture(session, _context, _instances):
        seen.extend(obj.link for obj in session.new if isinstance(obj, models.Notification))

    event.listen(db_session, "before_flush", capture)
    try:
        create_notification(db_session, _user(db_session).id, "goal_reached", "Goal reached", link="/#goals")
    finally:
        event.remove(db_session, "before_flush", capture)
    assert seen == ["/#goals"]


def test_raised_goal_keeps_its_live_share_link_reachable(authenticated_client, db_session):
    year = datetime.utcnow().year
    for title in ("Piranesi", "Dune"):
        item = authenticated_client.post("/books/", json={"title": title, "author": "A", "year": 2000, "read": True}).json()
        authenticated_client.post("/completion-moments/", json={"category": "books", "item_id": item["id"]})
    authenticated_client.put(f"/api/goals/{year}/books", json={"target": 2})
    url = authenticated_client.put(f"/api/goals/{year}/books/share").json()["url"]

    raised = authenticated_client.put(f"/api/goals/{year}/books", json={"target": 5}).json()["goals"][0]
    assert raised["achievement"]["shared"] is True and raised["achievement"]["url"] == url
    assert raised["achievement"]["celebrate"] is False
    assert authenticated_client.delete(f"/api/goals/{year}/books/share").json()["shared"] is False
    assert authenticated_client.get("/api/goals").json()["goals"][0]["achievement"] is None


def test_reactivate_shares_the_login_lockout(client, db_session, test_user_data):
    client.post("/auth/register", json=test_user_data)
    user = _user(db_session)
    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    db_session.commit()
    body = {"username": test_user_data["username"], "password": "wrong-password-1"}
    for _ in range(5):
        assert client.post("/auth/reactivate", json=body).status_code == 401
    db_session.refresh(user)
    assert user.locked_until is not None

    right = dict(body, password=test_user_data["password"])
    assert client.post("/auth/reactivate", json=right).status_code == 401  # locked, even with the right password

    user.locked_until = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert client.post("/auth/reactivate", json=right).status_code == 200
    db_session.refresh(user)
    assert user.is_active and not user.failed_login_attempts and user.locked_until is None


def test_changing_password_retires_an_emailed_reset_link(authenticated_client, db_session, test_user_data):
    user = _user(db_session)
    user.reset_token = "pending"
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db_session.commit()
    response = authenticated_client.put("/account/password", json={
        "current_password": test_user_data["password"], "new_password": "AnotherPassword456!"})
    assert response.status_code == 200, response.text
    db_session.refresh(user)
    assert user.reset_token is None and user.reset_token_expires is None
