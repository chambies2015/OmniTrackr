"""Watch clubs: a shared list picks one title, members check in, score it and talk it over."""
from datetime import date, timedelta

import pytest

from app import models, title_search
from tests.test_shared_lists import _as, _me, _new_list, _token
from tests.test_title_pages import member


@pytest.fixture(autouse=True)
def fresh_search_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def _day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def _club(client, db):
    """A list with two titles, sam in it, and testuser back in charge."""
    owner = _me(db)
    list_id = _new_list(client, name="Film club")
    first = client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Arrival", "year": 2016}).json()["id"]
    second = client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Heat", "year": 1995}).json()["id"]
    token = _token(client, list_id)
    sam = member(db, "sam")
    db.commit()
    _as(client, sam)
    assert client.post(f"/api/lists/join/{token}").json()["joined"] is True
    client.get(f"/api/lists/{list_id}")
    _as(client, owner)
    return owner, sam, list_id, first, second, token


def _start(client, list_id, item_id, days=7):
    response = client.post(f"/api/lists/{list_id}/club", json={"item_id": item_id, "ends_on": _day(days)})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()["id"]


def test_start_a_pick_tells_the_club(authenticated_client, db_session):
    owner, sam, list_id, first, _, token = _club(authenticated_client, db_session)
    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    assert data["club"] == {"current": None, "past": [], "max_days": 90}

    round_id = _start(authenticated_client, list_id, first)
    note = db_session.query(models.Notification).filter_by(user_id=sam.id, type="club_pick").one()
    assert note.message.startswith('testuser picked Arrival for "Film club". Finish by ') and note.link == f"/lists/{list_id}"
    assert db_session.query(models.Notification).filter_by(user_id=owner.id, type="club_pick").count() == 0

    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert current["id"] == round_id and current["title"] == "Arrival" and current["days_left"] == 7
    assert current["started_by"]["username"] == "testuser" and current["can_run"] is True
    # Whoever picks is on it.
    assert current["me"] == {"status": "started", "score": None}
    assert [(p["username"], p["status"]) for p in current["members"]] == [("testuser", "started"), ("sam", None)]

    # Only one at a time.
    again = authenticated_client.post(f"/api/lists/{list_id}/club", json={"item_id": first, "ends_on": _day(3)})
    assert again.status_code == 409

    # The list card and the join link say what the club is on.
    [card] = authenticated_client.get("/api/lists").json()["lists"]
    assert card["club"]["title"] == "Arrival" and card["club"]["days_left"] == 7
    link = authenticated_client.post(f"/api/lists/{list_id}/link").json()
    assert link["text"].startswith('Join our watch club "Film club"') and "Arrival" in link["text"]
    _as(authenticated_client, None)
    page = authenticated_client.get(f"/lists/join/{token}")
    assert "Club pick right now" in page.text and "runs this as a watch club" in page.text


def test_dates_must_be_ahead_and_within_range(authenticated_client, db_session):
    _, _, list_id, first, _, _ = _club(authenticated_client, db_session)
    for offset in (0, -1, 91):
        response = authenticated_client.post(f"/api/lists/{list_id}/club", json={"item_id": first, "ends_on": _day(offset)})
        assert response.status_code == 400
    assert authenticated_client.post(f"/api/lists/{list_id}/club", json={"item_id": 999999, "ends_on": _day(3)}).status_code == 404
    round_id = _start(authenticated_client, list_id, first, days=90)
    assert authenticated_client.patch(f"/api/lists/{list_id}/club/{round_id}", json={"ends_on": _day(0)}).status_code == 400
    moved = authenticated_client.patch(f"/api/lists/{list_id}/club/{round_id}", json={"ends_on": _day(10)})
    assert moved.status_code == 200 and moved.json()["ends_on"] == _day(10)


def test_progress_scores_and_spoilers(authenticated_client, db_session):
    owner, sam, list_id, first, _, _ = _club(authenticated_client, db_session)
    round_id = _start(authenticated_client, list_id, first)
    base = f"/api/lists/{list_id}/club/{round_id}"

    # A score needs finishing first, and stays in range.
    assert authenticated_client.put(f"{base}/progress", json={"status": "started", "score": 8}).status_code == 400
    assert authenticated_client.put(f"{base}/progress", json={"status": "finished", "score": 11}).status_code == 422
    assert authenticated_client.put(f"{base}/progress", json={"status": "finished", "score": 9}).status_code == 200
    spoiler = authenticated_client.post(f"{base}/posts", json={"body": "The ending is all about the daughter.", "spoiler": True})
    assert spoiler.status_code == 201
    authenticated_client.post(f"{base}/posts", json={"body": "Loved the score.", "spoiler": False})
    assert authenticated_client.post(f"{base}/posts", json={"body": "   ", "spoiler": False}).status_code == 400

    # Sam hasn't finished: the spoiler comes folded and sam was told once about the talk.
    notes = db_session.query(models.Notification).filter_by(user_id=sam.id, type="club_post").all()
    assert len(notes) == 1 and notes[0].message == 'testuser posted about Arrival in "Film club".'
    _as(authenticated_client, sam)
    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert [(p["spoiler"], p["folded"], p["new"]) for p in current["posts"]] == [(True, True, True), (False, False, True)]
    assert current["finished_count"] == 1 and current["average"] == 9.0
    assert current["can_run"] is False
    # Opening the list clears the notes, and the posts aren't new anymore.
    db_session.expire_all()
    assert all(n.read_at for n in db_session.query(models.Notification).filter_by(user_id=sam.id))

    authenticated_client.put(f"{base}/progress", json={"status": "finished", "score": 6})
    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert [(p["folded"], p["new"]) for p in current["posts"]] == [(False, False), (False, False)]
    assert current["average"] == 7.5 and current["finished_count"] == 2

    # Members can't wrap up, move or drop someone else's pick, or delete others' posts.
    assert authenticated_client.post(f"{base}/finish").status_code == 403
    assert authenticated_client.patch(base, json={"ends_on": _day(3)}).status_code == 403
    assert authenticated_client.delete(f"{base}/posts/{spoiler.json()['id']}").status_code == 403
    # Clearing your progress works.
    assert authenticated_client.put(f"{base}/progress", json={"status": None}).status_code == 200
    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert current["me"] == {"status": None, "score": None} and current["average"] == 9.0


def test_wrap_up_marks_done_and_keeps_history(authenticated_client, db_session):
    owner, sam, list_id, first, second, _ = _club(authenticated_client, db_session)
    round_id = _start(authenticated_client, list_id, first)
    base = f"/api/lists/{list_id}/club/{round_id}"
    authenticated_client.put(f"{base}/progress", json={"status": "finished", "score": 8})
    authenticated_client.post(f"{base}/posts", json={"body": "Great pick.", "spoiler": True})
    # A pick people talked about can't be quietly dropped.
    assert authenticated_client.delete(base).status_code == 400
    assert authenticated_client.post(f"{base}/finish").status_code == 200

    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    assert data["club"]["current"] is None
    [past] = data["club"]["past"]
    assert past["title"] == "Arrival" and past["average"] == 8.0 and past["my_score"] == 8 and past["post_count"] == 1
    assert [i["title"] for i in data["done"]] == ["Arrival"]
    posts = authenticated_client.get(f"{base}/posts").json()["posts"]
    assert [(p["body"], p["folded"]) for p in posts] == [("Great pick.", False)]
    # A wrapped-up pick takes no more progress.
    assert authenticated_client.put(f"{base}/progress", json={"status": "started"}).status_code == 400

    # Sam can start the next one and drop it again while nobody has posted.
    _as(authenticated_client, sam)
    next_id = _start(authenticated_client, list_id, second)
    assert authenticated_client.delete(f"/api/lists/{list_id}/club/{next_id}").status_code == 204
    assert authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"] is None


def test_removing_the_title_keeps_the_pick(authenticated_client, db_session):
    _, _, list_id, first, _, _ = _club(authenticated_client, db_session)
    round_id = _start(authenticated_client, list_id, first)
    assert authenticated_client.delete(f"/api/lists/{list_id}/items/{first}").status_code == 204
    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert current["id"] == round_id and current["title"] == "Arrival"
    assert authenticated_client.post(f"/api/lists/{list_id}/club/{round_id}/finish").status_code == 200
    assert authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["past"][0]["title"] == "Arrival"


def test_leaving_drops_progress_but_keeps_posts(authenticated_client, db_session):
    owner, sam, list_id, first, _, _ = _club(authenticated_client, db_session)
    round_id = _start(authenticated_client, list_id, first)
    base = f"/api/lists/{list_id}/club/{round_id}"
    _as(authenticated_client, sam)
    authenticated_client.put(f"{base}/progress", json={"status": "finished", "score": 2})
    authenticated_client.post(f"{base}/posts", json={"body": "Not for me.", "spoiler": False})
    assert authenticated_client.delete(f"/api/lists/{list_id}/members/{sam.id}").status_code == 204
    # Outsiders can't reach the club at all.
    assert authenticated_client.get(f"{base}/posts").status_code == 404
    assert authenticated_client.post(f"{base}/posts", json={"body": "hi"}).status_code == 404
    _as(authenticated_client, owner)
    current = authenticated_client.get(f"/api/lists/{list_id}").json()["club"]["current"]
    assert [p["username"] for p in current["members"]] == ["testuser"] and current["average"] is None
    assert [p["body"] for p in current["posts"]] == ["Not for me."]
    assert db_session.query(models.ClubProgress).filter_by(user_id=sam.id).count() == 0


def test_deleting_the_list_removes_its_club(authenticated_client, db_session):
    _, _, list_id, first, _, _ = _club(authenticated_client, db_session)
    round_id = _start(authenticated_client, list_id, first)
    authenticated_client.post(f"/api/lists/{list_id}/club/{round_id}/posts", json={"body": "Starting tonight."})
    assert authenticated_client.delete(f"/api/lists/{list_id}").status_code == 204
    db_session.expire_all()
    assert db_session.query(models.ClubRound).count() == 0
    assert db_session.query(models.ClubPost).count() == 0
    assert db_session.query(models.ClubProgress).count() == 0


def test_clubs_shortcut_and_page_copy(authenticated_client):
    response = authenticated_client.get("/clubs", follow_redirects=False)
    assert response.status_code == 302 and response.headers["location"] == "/lists"
    page = authenticated_client.get("/lists")
    assert "SHARED LISTS AND WATCH CLUBS" in page.text and "Spoilers stay hidden until you finish" in page.text
