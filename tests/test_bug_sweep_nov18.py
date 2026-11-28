"""Bugs found walking the site end to end on Nov 18 2026 (guest and member, desktop and phone)."""
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from app import challenges, check_in, models, year_in_review
from app.home_summary import build as home_summary

ROOT = Path(__file__).resolve().parents[1]


def _user(db_session, name="testuser"):
    return db_session.query(models.User).filter(models.User.username == name).one()


def _add_watched(client, title, year):
    response = client.post("/movies/", json={"title": title, "director": "Someone", "year": year, "watched": True})
    assert response.status_code == 201
    return response.json()["id"]


# ---------------------------------------------------------------- removed duplicates

def test_a_deleted_duplicate_is_not_a_second_finish_this_month(authenticated_client, db_session):
    first = _add_watched(authenticated_client, "Arrival", 2016)
    copy = _add_watched(authenticated_client, "Arrival", 2016)
    assert authenticated_client.get("/statistics/home/").json()["finished_this_month"] == 2
    assert authenticated_client.delete(f"/movies/{copy}").status_code == 200
    # The journal keeps the removed copy's finish with its item_id cleared.
    entries = db_session.query(models.ActivityEntry).filter_by(action="completed").all()
    assert sorted((entry.item_id is None) for entry in entries) == [False, True]

    data = authenticated_client.get("/statistics/home/").json()
    assert (data["finished"], data["finished_this_month"]) == (1, 1)  # was (1, 2)
    assert first


def test_two_different_removed_titles_still_count_as_two(authenticated_client, db_session):
    for title, year in (("Heat", 1995), ("Collateral", 2004)):
        authenticated_client.delete(f"/movies/{_add_watched(authenticated_client, title, year)}")
    # Both entries have item_id cleared; a DISTINCT on (category, item_id) made them one.
    assert authenticated_client.get("/statistics/home/").json()["finished_this_month"] == 2


def test_the_recap_and_the_monthly_challenge_count_a_removed_duplicate_once(authenticated_client, db_session):
    user = _user(db_session)
    now = datetime.utcnow()
    _add_watched(authenticated_client, "Arrival", 2016)
    authenticated_client.delete(f"/movies/{_add_watched(authenticated_client, ' arrival ', 2016)}")
    _add_watched(authenticated_client, "Nope", 2022)
    assert year_in_review.finished_counts(db_session, user.id, now.year)["movies"] == 2  # was 3
    month = challenges.month_key(now.date())
    assert sorted(row["title"].strip().lower() for row in challenges._finishes(db_session, user.id, month)) == ["arrival", "nope"]
    assert home_summary(db_session, user, now=now)["finished_this_month"] == 2


def test_folding_keeps_the_live_row_and_carries_over_what_the_copy_had():
    finished = {
        ("movies", 3): {"category": "movies", "title": "Arrival", "rating": None, "favorite": False, "item_id": 3},
        ("movies", "arrival"): {"category": "movies", "title": "Arrival", "rating": 9.0, "favorite": True, "item_id": None},
        ("movies", "heat"): {"category": "movies", "title": "Heat", "rating": None, "favorite": False, "item_id": None},
        ("books", "arrival"): {"category": "books", "title": "Arrival", "rating": None, "favorite": False, "item_id": None},
    }
    folded = year_in_review.fold_deleted_copies(finished)
    assert set(folded) == {("movies", 3), ("movies", "heat"), ("books", "arrival")}
    assert folded[("movies", 3)]["rating"] == 9.0 and folded[("movies", 3)]["favorite"] is True
    assert folded[("movies", 3)]["item_id"] == 3


# ---------------------------------------------------------------- check-in page

def _member(db, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, is_active=True,
                       created_at=datetime.utcnow() - timedelta(days=60))
    db.add(user)
    db.flush()
    return user


def test_check_in_only_mentions_picks_below_when_there_are_some(client, db_session, monkeypatch):
    user = _member(db_session, "checker")
    show = models.TVShow(title="Severance", user_id=user.id, watched=True, rating=8.0)
    db_session.add(show)
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "tv-shows", "id": show.id}], "checkin")

    monkeypatch.setattr(check_in, "picks", lambda db, user_id, limit=3: [])
    page = client.get(f"/check-in/{token}?r=1")
    assert "All caught up" in page.text
    assert "picks below" not in page.text and "Picked for you" not in page.text
    assert "That’s everything. Your library is up to date." in page.text

    pick = {"title": "Andor", "url": "/titles/tv/andor-2022", "image": None, "label": "TV show", "reason": "Liked by members like you"}
    monkeypatch.setattr(check_in, "picks", lambda db, user_id, limit=3: [pick])
    page = client.get(f"/check-in/{token}?r=1")
    assert "shaping the picks below" in page.text and "Picked for you" in page.text


# ---------------------------------------------------------------- Continue labels

def test_unfinished_shows_are_not_called_in_progress_before_they_start():
    from app.routers.statistics import LIBRARY_CATEGORIES

    labels = {category["key"]: category["status_label"] for category in LIBRARY_CATEGORIES}
    # Continue showed "Anime · In progress" right above "Not started · 28 episodes".
    assert labels["tv-shows"] == labels["anime"] == "Not finished"
    core = (ROOT / "app/static/dashboard/core.js").read_text(encoding="utf-8")
    assert "'In progress'" not in core
