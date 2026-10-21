"""Regressions from the October 21 bug sweep."""
import json

from app import web_push


def test_shared_list_and_invite_pushes_have_their_own_titles():
    for kind in ("shared_list_added", "shared_list_joined", "shared_list_item", "friend_invite_accepted"):
        data = json.loads(web_push.payload_for(kind, "alice added you to a list", "/lists/3"))
        assert data["title"] != "OmniTrackr", kind
        assert data["url"] == "/lists/3"


def test_adding_a_title_as_finished_counts_toward_goals_and_the_recap(authenticated_client, db_session):
    from datetime import datetime
    from app import models, year_in_review

    year = datetime.utcnow().year
    authenticated_client.post("/movies/", json={"title": "Arrival", "director": "Denis Villeneuve", "year": 2016, "watched": True})
    authenticated_client.post("/movies/", json={"title": "Paddington 2", "director": "Paul King", "year": 2017, "watched": False})
    authenticated_client.post("/books/", json={"title": "Dune", "author": "Frank Herbert", "year": 1965, "read": True})
    authenticated_client.post("/video-games/", json={"title": "Hades", "played": True})
    user = db_session.query(models.User).filter_by(username="testuser").one()

    counts = year_in_review.finished_counts(db_session, user.id, year)
    assert (counts["movies"], counts["books"], counts["video-games"]) == (1, 1, 1)
    entries = db_session.query(models.ActivityEntry).filter_by(user_id=user.id).all()
    assert sorted(e.title for e in entries) == ["Arrival", "Dune", "Hades"]
    assert {e.action for e in entries} == {"completed"} and {e.source for e in entries} == {"automatic"}

    goal = authenticated_client.put(f"/api/goals/{year}/movies", json={"target": 5}).json()["goals"][0]
    assert goal["done"] == 1


def test_finishing_a_title_added_as_finished_is_still_counted_once(authenticated_client, db_session):
    from datetime import datetime
    from app import models, year_in_review

    movie = authenticated_client.post("/movies/", json={"title": "Arrival", "director": "Denis Villeneuve", "year": 2016, "watched": True}).json()
    assert authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": movie["id"]}).status_code == 200
    user = db_session.query(models.User).filter_by(username="testuser").one()
    assert year_in_review.finished_counts(db_session, user.id, datetime.utcnow().year)["movies"] == 1
    # One "Finished" line in the journal, not one for the add and another for the reflection.
    assert [e["action"] for e in authenticated_client.get("/activity/").json()] == ["completed"]
