"""Private library tags and saved shelf views."""
import pytest

from app import models
from app.library_lifecycle import delete_owned_media
from app.routers.library import CATEGORIES


def owner(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


def stranger(db_session):
    user = models.User(username="other", email="other@example.test", hashed_password="unused")
    db_session.add(user)
    db_session.flush()
    return user


def add(db_session, user, category, title, **fields):
    model = CATEGORIES[category][0]
    item = model(user_id=user.id, title=title, **fields)
    db_session.add(item)
    db_session.commit()
    return item


def page(client, category, **params):
    response = client.get(f"/library/page/{category}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_tags_save_show_on_rows_and_filter_each_shelf(authenticated_client, db_session, category):
    me = owner(db_session)
    first = add(db_session, me, category, "First")
    second = add(db_session, me, category, "Second")
    add(db_session, me, category, "Untagged")

    saved = authenticated_client.put(f"/library/tags/{category}/{first.id}", json={"tags": ["Cozy", "#with Sam  "]})
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"tags": ["Cozy", "with Sam"]}
    # A later spelling reuses the one already in the library.
    assert authenticated_client.put(f"/library/tags/{category}/{second.id}", json={"tags": ["cozy", "COZY"]}).json() == {"tags": ["Cozy"]}

    rows = {row["title"]: row["tags"] for row in page(authenticated_client, category)["items"]}
    assert rows == {"First": ["Cozy", "with Sam"], "Second": ["Cozy"], "Untagged": []}

    tagged = page(authenticated_client, category, tag="cozy")
    assert {row["title"] for row in tagged["items"]} == {"First", "Second"}
    assert tagged["total"] == 2
    assert [row["title"] for row in page(authenticated_client, category, tag="#With sam")["items"]] == ["First"]
    assert page(authenticated_client, category, tag="nothing")["total"] == 0

    counts = authenticated_client.get("/library/tags", params={"category": category}).json()
    assert counts == [{"label": "Cozy", "count": 2}, {"label": "with Sam", "count": 1}]

    assert authenticated_client.put(f"/library/tags/{category}/{first.id}", json={"tags": []}).json() == {"tags": []}
    assert page(authenticated_client, category, tag="with sam")["total"] == 0


def test_tags_stay_private_and_need_an_owned_title(authenticated_client, db_session):
    me, other = owner(db_session), stranger(db_session)
    theirs = add(db_session, other, "movies", "Their film")
    mine = add(db_session, me, "movies", "My film")
    db_session.add(models.LibraryTag(user_id=other.id, category="movies", item_id=mine.id, label="spy", label_key="spy"))
    db_session.commit()

    assert authenticated_client.put(f"/library/tags/movies/{theirs.id}", json={"tags": ["mine now"]}).status_code == 404
    assert authenticated_client.put(f"/library/tags/books/{mine.id}", json={"tags": ["wrong shelf"]}).status_code == 404
    assert authenticated_client.put("/library/tags/films/1", json={"tags": ["x"]}).status_code == 404
    # Another member's tag on a matching id never shows up or filters.
    assert page(authenticated_client, "movies")["items"][0]["tags"] == []
    assert page(authenticated_client, "movies", tag="spy")["total"] == 0
    assert authenticated_client.get("/library/tags").json() == []


def test_tag_limits_and_cleaning(authenticated_client, db_session):
    item = add(db_session, owner(db_session), "books", "Dune")
    url = f"/library/tags/books/{item.id}"
    assert authenticated_client.put(url, json={"tags": [f"tag {n}" for n in range(11)]}).status_code == 422
    assert authenticated_client.put(url, json={"tags": ["x" * 33]}).status_code == 422
    assert authenticated_client.put(url, json={"tags": ["a,b"]}).status_code == 422
    assert authenticated_client.put(url, json={"tags": ["bad\u0000tag"]}).status_code == 422
    assert authenticated_client.put(url, json={"tags": ["  ", "#", "ok"]}).json() == {"tags": ["ok"]}
    # Ten distinct tags, with duplicates folded away, are allowed.
    tags = [f"tag {n}" for n in range(10)] + ["TAG 0"]
    assert len(authenticated_client.put(url, json={"tags": tags}).json()["tags"]) == 10


def test_deleting_a_title_removes_its_tags(authenticated_client, db_session):
    me = owner(db_session)
    item = add(db_session, me, "anime", "Frieren")
    authenticated_client.put(f"/library/tags/anime/{item.id}", json={"tags": ["comfort"]})
    delete_owned_media(db_session, me.id, "anime", item.id)
    assert db_session.query(models.LibraryTag).count() == 0
    assert authenticated_client.get("/library/tags").json() == []


def test_all_shelf_tag_list_counts_across_categories(authenticated_client, db_session):
    me = owner(db_session)
    film = add(db_session, me, "movies", "Heat")
    book = add(db_session, me, "books", "Emma")
    authenticated_client.put(f"/library/tags/movies/{film.id}", json={"tags": ["Rewatch", "with Sam"]})
    authenticated_client.put(f"/library/tags/books/{book.id}", json={"tags": ["rewatch"]})
    assert authenticated_client.get("/library/tags").json() == [
        {"label": "Rewatch", "count": 2}, {"label": "with Sam", "count": 1},
    ]
    assert authenticated_client.get("/library/tags", params={"category": "nope"}).status_code == 404


def test_saved_views_round_trip(authenticated_client, db_session):
    filters = {"search": " nolan ", "sort": "rating-desc", "completion": "unfinished",
               "unrated": True, "has_progress": True, "tag": "#Cozy"}
    created = authenticated_client.post("/library/views/movies", json={"name": "  Cozy   picks ", "filters": filters})
    assert created.status_code == 200, created.text
    view = created.json()
    assert view["name"] == "Cozy picks"
    # Movies have no saved progress, so that filter is dropped rather than refused.
    assert view["filters"] == {"search": "nolan", "sort": "rating-desc", "completion": "unfinished",
                               "unrated": True, "has_progress": False, "tag": "Cozy"}
    assert authenticated_client.get("/library/views/movies").json() == [view]
    assert authenticated_client.get("/library/views/books").json() == []

    # The same name, in any case, updates the view instead of adding another.
    updated = authenticated_client.post("/library/views/movies", json={"name": "cozy PICKS", "filters": {"completion": "finished"}})
    assert updated.json()["id"] == view["id"]
    assert updated.json()["filters"]["completion"] == "finished"
    assert len(authenticated_client.get("/library/views/movies").json()) == 1

    assert authenticated_client.delete(f"/library/views/books/{view['id']}").status_code == 404
    assert authenticated_client.delete(f"/library/views/movies/{view['id']}").status_code == 204
    assert authenticated_client.get("/library/views/movies").json() == []


def test_saved_view_validation_and_limit(authenticated_client, db_session):
    post = lambda name, **filters: authenticated_client.post("/library/views/tv-shows", json={"name": name, "filters": filters})
    assert post("Bad sort", sort="title-asc").status_code == 422
    assert post("Bad state", completion="maybe").status_code == 422
    assert post("   ").status_code == 422
    assert post("x" * 41).status_code == 422
    assert authenticated_client.post("/library/views/films", json={"name": "x", "filters": {}}).status_code == 404
    assert post("Progress", has_progress=True).json()["filters"]["has_progress"] is True
    for n in range(11):
        assert post(f"View {n}").status_code == 200
    full = post("One too many")
    assert full.status_code == 422
    assert "12 saved views" in full.json()["detail"]


def test_saved_views_are_private(authenticated_client, db_session):
    other = stranger(db_session)
    view = models.SavedLibraryView(user_id=other.id, category="music", name="Theirs", name_key="theirs", filters="{}")
    db_session.add(view)
    db_session.commit()
    assert authenticated_client.get("/library/views/music").json() == []
    assert authenticated_client.delete(f"/library/views/music/{view.id}").status_code == 404
    assert db_session.query(models.SavedLibraryView).count() == 1
