"""Shared lists: members build one list together, invite friends or share a join link."""
import pytest

from app import auth, models, shared_lists, title_search
from app.crud.friends import create_friendship
from tests.test_title_pages import add_movie, member


@pytest.fixture(autouse=True)
def fresh_search_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _as(client, user):
    client.headers = {}
    client.cookies.clear()
    if user is None:
        return
    token = auth.create_user_access_token(user)
    client.headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set(auth.AUTH_COOKIE_NAME, token)


def _new_list(client, name="Couch queue", description="Stuff we both want to see"):
    response = client.post("/api/lists", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()["id"]


def _token(client, list_id):
    return client.post(f"/api/lists/{list_id}/link").json()["url"].rsplit("/", 1)[1]


def _friends(db, a, b):
    create_friendship(db, min(a.id, b.id), max(a.id, b.id))


def test_create_add_and_see_who_added_what(authenticated_client, db_session):
    list_id = _new_list(authenticated_client, name="  Couch   queue ")
    added = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Arrival", "year": 2016})
    assert added.status_code == 201 and added.json()["state"] == "created"
    again = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "  arrival ", "year": 2016})
    assert again.json()["state"] == "existing" and again.json()["id"] == added.json()["id"]

    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    assert data["name"] == "Couch queue" and data["is_owner"] is True
    [item] = data["open"]
    assert item["title"] == "Arrival" and item["added_by"]["username"] == "testuser"
    # The person who adds a title is in for it.
    assert item["voted"] is True and [v["username"] for v in item["votes"]] == ["testuser"]
    assert item["in_library"] is False and item["url"] is None

    overview = authenticated_client.get("/api/lists").json()["lists"]
    assert overview[0]["name"] == "Couch queue" and overview[0]["open_count"] == 1


def test_search_result_takes_name_and_art_from_the_site(authenticated_client, db_session):
    tracker = member(db_session, "tracker")
    add_movie(db_session, tracker, title="Interstellar", year=2014, poster_url="https://img.example/interstellar.jpg")
    db_session.commit()
    list_id = _new_list(authenticated_client)
    response = authenticated_client.post(f"/api/lists/{list_id}/items", json={
        "kind": "movie", "title": "<b>whatever</b>", "slug": "interstellar-2014"})
    assert response.status_code == 201
    [item] = authenticated_client.get(f"/api/lists/{list_id}").json()["open"]
    assert item["title"] == "Interstellar" and item["year"] == 2014
    assert item["image"] == "https://img.example/interstellar.jpg"
    assert item["url"] == "/titles/movie/interstellar-2014"

    # An unknown slug keeps the typed title and never trusts art from the request.
    authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Solaris", "slug": "nope"})
    solaris = [i for i in authenticated_client.get(f"/api/lists/{list_id}").json()["open"] if i["title"] == "Solaris"][0]
    assert solaris["image"] is None and solaris["url"] is None


def test_join_link_preview_signup_and_join(authenticated_client, db_session):
    owner = _me(db_session)
    list_id = _new_list(authenticated_client)
    authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "anime", "title": "Frieren"})
    token = _token(authenticated_client, list_id)

    _as(authenticated_client, None)
    page = authenticated_client.get(f"/lists/join/{token}")
    assert page.status_code == 200
    assert "Join “Couch queue”" in page.text and "Frieren" in page.text and "testuser" in page.text
    assert f'href="/?next=%2Flists%2Fjoin%2F{token}#signup"' in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow" and page.headers["cache-control"] == "private, no-store"
    assert authenticated_client.get("/lists/join/" + "x" * 20).status_code == 404
    assert authenticated_client.post(f"/api/lists/join/{token}").status_code == 401

    friend = member(db_session, "sam")
    db_session.commit()
    _as(authenticated_client, friend)
    page = authenticated_client.get(f"/lists/join/{token}")
    assert "data-list-join" in page.text
    joined = authenticated_client.post(f"/api/lists/join/{token}")
    assert joined.status_code == 200 and joined.json() == {"id": list_id, "url": f"/lists/{list_id}", "joined": True}
    assert authenticated_client.post(f"/api/lists/join/{token}").json()["joined"] is False
    note = db_session.query(models.Notification).filter_by(user_id=owner.id, type="shared_list_joined").one()
    assert note.message == 'sam joined your shared list "Couch queue".' and note.link == f"/lists/{list_id}"

    # A member adds too, and the owner is told once until they open the list.
    for title in ("Dandadan", "Mushishi"):
        authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "anime", "title": title})
    notes = db_session.query(models.Notification).filter_by(user_id=owner.id, type="shared_list_item").all()
    assert [n.message for n in notes] == ['sam added Dandadan to "Couch queue".']
    _as(authenticated_client, owner)
    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    assert sorted(i["title"] for i in data["open"] if i["new"]) == ["Dandadan", "Mushishi"]
    assert [m["username"] for m in data["members"]] == ["testuser", "sam"]
    db_session.expire_all()
    assert all(n.read_at is not None for n in db_session.query(models.Notification).filter_by(user_id=owner.id))
    # Seen now.
    assert not any(i["new"] for i in authenticated_client.get(f"/api/lists/{list_id}").json()["open"])


def test_reset_link_retires_the_old_one(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    old = _token(authenticated_client, list_id)
    fresh = authenticated_client.post(f"/api/lists/{list_id}/link", json={"reset": True}).json()["url"].rsplit("/", 1)[1]
    assert fresh != old
    assert authenticated_client.get(f"/lists/join/{old}").status_code == 404
    assert authenticated_client.get(f"/lists/join/{fresh}").status_code == 200


def test_removing_someone_retires_the_link_they_had(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    old = _token(authenticated_client, list_id)
    owner, sam, kim = _me(db_session), member(db_session, "sam"), member(db_session, "kim")
    db_session.commit()
    for person in (sam, kim):
        _as(authenticated_client, person)
        assert authenticated_client.post(f"/api/lists/join/{old}").json()["joined"] is True

    # Leaving on your own keeps the link as it was.
    assert authenticated_client.delete(f"/api/lists/{list_id}/members/{kim.id}").status_code == 204
    _as(authenticated_client, owner)
    assert _token(authenticated_client, list_id) == old

    assert authenticated_client.delete(f"/api/lists/{list_id}/members/{sam.id}").status_code == 204
    fresh = _token(authenticated_client, list_id)
    assert fresh != old
    _as(authenticated_client, sam)
    assert authenticated_client.post(f"/api/lists/join/{old}").status_code == 404
    assert authenticated_client.get(f"/api/lists/{list_id}").status_code == 404


def test_invite_friends_only(authenticated_client, db_session):
    owner = _me(db_session)
    friend, stranger = member(db_session, "alex"), member(db_session, "stranger")
    _friends(db_session, owner, friend)
    db_session.commit()
    list_id = _new_list(authenticated_client)
    assert authenticated_client.get(f"/api/lists/{list_id}/friends").json()["friends"] == [{"id": friend.id, "username": "alex"}]
    assert authenticated_client.post(f"/api/lists/{list_id}/members", json={"user_id": stranger.id}).status_code == 404
    response = authenticated_client.post(f"/api/lists/{list_id}/members", json={"user_id": friend.id})
    assert response.status_code == 201 and response.json() == {"username": "alex"}
    assert authenticated_client.get(f"/api/lists/{list_id}/friends").json()["friends"] == []
    note = db_session.query(models.Notification).filter_by(user_id=friend.id, type="shared_list_added").one()
    assert note.message == 'testuser added you to the shared list "Couch queue".'


def test_outsiders_see_nothing(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    outsider = member(db_session, "outsider")
    db_session.commit()
    _as(authenticated_client, outsider)
    for method, path in (("get", f"/api/lists/{list_id}"), ("post", f"/api/lists/{list_id}/link"),
                         ("get", f"/api/lists/{list_id}/friends")):
        assert getattr(authenticated_client, method)(path).status_code == 404
    assert authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "X"}).status_code == 404
    assert authenticated_client.get(f"/lists/{list_id}").status_code == 404
    _as(authenticated_client, None)
    page = authenticated_client.get(f"/lists/{list_id}", follow_redirects=False)
    assert page.status_code == 200 and "Log in to see your shared lists" in page.text
    assert f'href="/?next=%2Flists%2F{list_id}#landing-auth"' in page.text
    assert f'href="/?next=%2Flists%2F{list_id}#signup"' in page.text


def test_owner_and_member_permissions(authenticated_client, db_session):
    owner = _me(db_session)
    list_id = _new_list(authenticated_client)
    mine = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "book", "title": "Piranesi"}).json()["id"]
    token = _token(authenticated_client, list_id)
    sam = member(db_session, "sam")
    db_session.commit()
    _as(authenticated_client, sam)
    authenticated_client.post(f"/api/lists/join/{token}")
    theirs = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "book", "title": "Dune"}).json()["id"]

    assert authenticated_client.delete(f"/api/lists/{list_id}/items/{mine}").status_code == 403
    assert authenticated_client.patch(f"/api/lists/{list_id}", json={"name": "Mine now"}).status_code == 403
    assert authenticated_client.post(f"/api/lists/{list_id}/link", json={"reset": True}).status_code == 403
    assert authenticated_client.delete(f"/api/lists/{list_id}").status_code == 403
    assert authenticated_client.delete(f"/api/lists/{list_id}/members/{owner.id}").status_code == 400
    # Anyone in the list can mark a title done or say they're in.
    assert authenticated_client.patch(f"/api/lists/{list_id}/items/{mine}", json={"done": True}).json()["done"] is True
    assert authenticated_client.put(f"/api/lists/{list_id}/items/{mine}/vote", json={"wanted": True}).status_code == 200
    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    assert [i["title"] for i in data["done"]] == ["Piranesi"] and data["done"][0]["done_by"]["username"] == "sam"
    assert authenticated_client.delete(f"/api/lists/{list_id}/items/{theirs}").status_code == 204

    # Leaving keeps the credit on titles they added, drops their "I'm in"s.
    authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "book", "title": "Circe"})
    assert authenticated_client.delete(f"/api/lists/{list_id}/members/{sam.id}").status_code == 204
    assert authenticated_client.get(f"/api/lists/{list_id}").status_code == 404
    _as(authenticated_client, owner)
    data = authenticated_client.get(f"/api/lists/{list_id}").json()
    circe = [i for i in data["open"] if i["title"] == "Circe"][0]
    assert circe["added_by"]["username"] == "sam" and circe["votes"] == []
    assert authenticated_client.delete(f"/api/lists/{list_id}").status_code == 204
    assert db_session.query(models.SharedListItem).count() == 0 and db_session.query(models.SharedListVote).count() == 0


def test_votes_put_the_most_wanted_first(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    first = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "game", "title": "Hades"}).json()["id"]
    second = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "game", "title": "Celeste"}).json()["id"]
    token = _token(authenticated_client, list_id)
    sam = member(db_session, "sam")
    db_session.commit()
    _as(authenticated_client, sam)
    authenticated_client.post(f"/api/lists/join/{token}")
    authenticated_client.put(f"/api/lists/{list_id}/items/{second}/vote", json={"wanted": True})
    assert [i["id"] for i in authenticated_client.get(f"/api/lists/{list_id}").json()["open"]] == [second, first]
    authenticated_client.put(f"/api/lists/{list_id}/items/{second}/vote", json={"wanted": False})
    assert [i["id"] for i in authenticated_client.get(f"/api/lists/{list_id}").json()["open"]] == [first, second]


def test_add_to_my_library_is_a_copy(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    item = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Arrival", "year": 2016}).json()["id"]
    response = authenticated_client.post(f"/api/lists/{list_id}/items/{item}/library")
    assert response.status_code == 200 and response.json() == {"state": "created", "title": "Arrival"}
    movie = db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).one()
    assert movie.title == "Arrival" and movie.year == 2016 and not movie.watched
    assert authenticated_client.post(f"/api/lists/{list_id}/items/{item}/library").json()["state"] == "existing"
    assert authenticated_client.get(f"/api/lists/{list_id}").json()["open"][0]["in_library"] is True
    # Taking it off the list leaves the library alone.
    authenticated_client.delete(f"/api/lists/{list_id}/items/{item}")
    assert db_session.query(models.Movie).count() == 1


def test_limits_and_validation(authenticated_client, db_session, monkeypatch):
    assert authenticated_client.post("/api/lists", json={"name": "   "}).status_code == 422
    list_id = _new_list(authenticated_client)
    assert authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "podcast", "title": "X"}).status_code == 400
    assert authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "  "}).status_code == 400
    monkeypatch.setattr(shared_lists, "OWNED_MAX", 1)
    assert authenticated_client.post("/api/lists", json={"name": "Another"}).status_code == 400
    monkeypatch.setattr(shared_lists, "MEMBERS_MAX", 1)
    token = _token(authenticated_client, list_id)
    late = member(db_session, "late")
    db_session.commit()
    _as(authenticated_client, late)
    assert authenticated_client.post(f"/api/lists/join/{token}").status_code == 400
    assert "This list is full" in authenticated_client.get(f"/lists/join/{token}").text


def test_member_text_is_escaped_on_pages(authenticated_client, db_session):
    list_id = _new_list(authenticated_client, name="<script>{{CONTENT}}</script>")
    authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "<img src=x onerror=1>"})
    token = _token(authenticated_client, list_id)
    page = authenticated_client.get(f"/lists/{list_id}")
    assert "<script>{{" not in page.text and "&lt;script&gt;&#123;&#123;CONTENT&#125;&#125;" in page.text
    assert page.text.count('data-view="list"') == 1
    _as(authenticated_client, None)
    page = authenticated_client.get(f"/lists/join/{token}")
    assert "<img src=x" not in page.text and "&lt;img src=x onerror=1&gt;" in page.text


def test_pages_for_members(authenticated_client, db_session):
    page = authenticated_client.get("/lists")
    assert page.status_code == 200 and 'data-view="index"' in page.text
    assert page.headers["x-robots-tag"] == "noindex, follow"
    assert 'href="/">My library</a>' in page.text and "Start tracking</a>" not in page.text
    _as(authenticated_client, None)
    response = authenticated_client.get("/lists", follow_redirects=False)
    assert response.status_code == 200 and 'href="/?next=%2Flists#landing-auth"' in response.text
    assert response.headers["cache-control"] == "private, no-store"
