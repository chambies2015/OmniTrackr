"""Yearly goals: private targets, progress from the recap's finishes, the weekly email and the recap."""
from datetime import date, datetime

import pytest

from app import digest, goals, models, year_in_review


def _user(db_session):
    return db_session.query(models.User).filter(models.User.username == "testuser").one()


def _finish(client, path, payload, done_field):
    item = client.post(path, json=dict(payload, **{done_field: True})).json()
    response = client.post("/completion-moments/", json={"category": path.strip("/"), "item_id": item["id"]})
    assert response.status_code == 200, response.text
    return item


def _seed(client):
    _finish(client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020}, "read")
    _finish(client, "/books/", {"title": "Dune", "author": "F. Herbert", "year": 1965}, "read")
    _finish(client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016}, "watched")


def test_goals_are_private_and_need_login(client):
    assert client.get("/api/goals").status_code == 401
    assert client.put("/api/goals/2026/books", json={"target": 5}).status_code == 401


def test_set_edit_and_remove_a_goal_with_progress(authenticated_client):
    _seed(authenticated_client)
    year = datetime.utcnow().year
    empty = authenticated_client.get("/api/goals")
    assert empty.status_code == 200 and empty.headers["Cache-Control"] == "private, no-store"
    assert empty.json()["goals"] == [] and empty.json()["years"] == [year, year + 1]

    saved = authenticated_client.put(f"/api/goals/{year}/books", json={"target": 4}).json()
    book = saved["goals"][0]
    assert (book["category"], book["done"], book["target"], book["percent"], book["noun"]) == ("books", 2, 4, 50, "books")

    authenticated_client.put(f"/api/goals/{year}/all", json={"target": 3})
    listed = authenticated_client.get(f"/api/goals?year={year}").json()["goals"]
    assert [goal["category"] for goal in listed] == ["all", "books"]
    assert listed[0]["done"] == 3 and listed[0]["pace"]["status"] == "done"
    assert listed[0]["summary"] == "3 of 3 titles, goal reached"

    edited = authenticated_client.put(f"/api/goals/{year}/books", json={"target": 2}).json()["goals"]
    assert [goal["target"] for goal in edited] == [3, 2]

    assert authenticated_client.delete(f"/api/goals/{year}/books").json()["goals"][0]["category"] == "all"
    assert authenticated_client.delete(f"/api/goals/{year}/books").status_code == 404


@pytest.mark.parametrize("path, body", [
    ("/api/goals/2025/books", {"target": 5}),
    ("/api/goals/{year}/podcasts", {"target": 5}),
    ("/api/goals/{year}/books", {"target": 0}),
    ("/api/goals/{year}/books", {"target": 1001}),
])
def test_goal_validation(authenticated_client, path, body):
    response = authenticated_client.put(path.format(year=datetime.utcnow().year), json=body)
    assert response.status_code == 422


def test_goals_belong_to_one_member(authenticated_client, db_session):
    year = datetime.utcnow().year
    other = models.User(username="goalother", email="goalother@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    db_session.add(models.YearlyGoal(user_id=other.id, year=year, category="books", target=9))
    db_session.commit()
    assert authenticated_client.get("/api/goals").json()["goals"] == []


def test_pace():
    assert goals._pace(10, 10, 2026, date(2026, 3, 1))["status"] == "done"
    assert goals._pace(0, 12, 2027, date(2026, 12, 1)) == {"status": "not_started", "difference": 0}
    assert goals._pace(6, 12, 2026, date(2026, 7, 2)) == {"status": "on_track", "difference": 0}
    assert goals._pace(9, 12, 2026, date(2026, 7, 2)) == {"status": "ahead", "difference": 3}
    assert goals._pace(2, 12, 2026, date(2026, 7, 2)) == {"status": "behind", "difference": 4}
    # A goal set late in the year paces from the day it was set, so it starts on pace.
    assert goals._pace(0, 30, 2026, date(2026, 10, 10), set_on=date(2026, 10, 10)) == {"status": "on_track", "difference": 0}
    assert goals._pace(0, 30, 2026, date(2026, 12, 1), set_on=date(2026, 10, 10))["status"] == "behind"
    # Set in December for next year: pace still starts on January 1.
    assert goals._pace(0, 12, 2027, date(2027, 2, 1), set_on=date(2026, 12, 20))["status"] == "behind"


def test_finished_counts_match_the_recap(authenticated_client, db_session):
    _seed(authenticated_client)
    year = datetime.utcnow().year
    counts = year_in_review.finished_counts(db_session, _user(db_session).id, year)
    recap = year_in_review.build(db_session, _user(db_session), year)
    assert counts["books"] == 2 and counts["movies"] == 1
    assert sum(counts.values()) == recap["finished_total"]


def test_recap_shows_goals_and_shared_recap_hides_private_ones(authenticated_client, db_session):
    _seed(authenticated_client)
    year = datetime.utcnow().year
    authenticated_client.put(f"/api/goals/{year}/books", json={"target": 2})
    authenticated_client.put(f"/api/goals/{year}/movies", json={"target": 5})
    authenticated_client.put(f"/api/goals/{year}/all", json={"target": 10})
    page = authenticated_client.get(f"/year-in-review/{year}").text
    assert "recap-goals" in page and "2 of 2 books" in page and "Goal reached" in page and "4 to go" in page

    user = _user(db_session)
    user.movies_private = True
    db_session.commit()
    shared = year_in_review.build(db_session, user, year, public=True)
    assert [goal["category"] for goal in shared["goals"]] == ["books"]


def test_weekly_email_lists_goals_without_forcing_a_send():
    goal = {"category": "books", "target": 24, "done": 12, "percent": 50, "noun": "books",
            "pace": {"status": "ahead", "difference": 2}}
    goal["summary"] = goals.describe(goal)
    report = {"matches": [{"url": "/release-radar", "title": "Dune: Part Three", "label": "Movie", "date": "2026-12-18", "reason": "You track Dune"}],
              "popular": []}
    subject, html, text = digest.build_digest("sam", report, "https://x/unsub", goals=[goal], goals_year=2026)
    assert "Your 2026 goals" in html and "12 of 24 books, 2 ahead of pace" in html
    assert "- 12 of 24 books, 2 ahead of pace" in text and "/#goals" in text
    assert digest.build_digest("sam", {"matches": [], "popular": []}, "https://x/unsub", goals=[goal], goals_year=2026) is None
    assert "goals" not in digest.build_digest("sam", report, "https://x/unsub")[1]


def test_yearly_goal_table_is_new_and_separate():
    assert models.YearlyGoal.__tablename__ == "yearly_goals"
    assert "goal" not in " ".join(models.User.__table__.columns.keys())
