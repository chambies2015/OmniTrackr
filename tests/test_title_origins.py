"""Why I added it: who recommended a title, or where the member heard of it."""
import io
import json
import zipfile

import pytest

from app import models
from app.library_lifecycle import delete_owned_media
from app.routers.library import CATEGORIES
from tests.test_friend_recs import _as, _friend, _me
from tests.test_library_tags import add, page
from tests.test_shared_lists import _new_list, _token
from tests.test_title_pages import add_movie, member


def put(client, category, item_id, **body):
    return client.put(f"/library/origins/{category}/{item_id}", json=body)


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_save_show_on_rows_filter_and_clear_on_each_shelf(authenticated_client, db_session, category):
    me = _me(db_session)
    first = add(db_session, me, category, "First")
    second = add(db_session, me, category, "Second")
    add(db_session, me, category, "Third")

    saved = put(authenticated_client, category, first.id, source="person", who="  Aunt   May ", note=" Said I'd cry ")
    assert saved.status_code == 200, saved.text
    assert saved.headers["cache-control"] == "private, no-store"
    origin = saved.json()["origin"]
    assert (origin["source"], origin["who"], origin["note"], origin["friend"]) == ("person", "Aunt May", "Said I'd cry", None)
    assert put(authenticated_client, category, second.id, source="person", who="aunt may").status_code == 200

    rows = {row["title"]: row["origin"] for row in page(authenticated_client, category)["items"]}
    assert rows["Third"] is None and rows["First"]["who"] == "Aunt May"

    by_may = page(authenticated_client, category, recommended_by="AUNT  MAY")
    assert {row["title"] for row in by_may["items"]} == {"First", "Second"} and by_may["total"] == 2
    people = authenticated_client.get("/library/recommenders", params={"category": category}).json()
    assert people == [{"key": "aunt may", "name": "aunt may", "count": 2}]

    assert authenticated_client.delete(f"/library/origins/{category}/{first.id}").status_code == 204
    assert authenticated_client.get(f"/library/origins/{category}/{first.id}").json() == {"origin": None}
    assert page(authenticated_client, category, recommended_by="aunt may")["total"] == 1


def test_sources_other_than_people_are_not_recommenders(authenticated_client, db_session):
    me = _me(db_session)
    movie = add(db_session, me, "movies", "Heat")
    saved = put(authenticated_client, "movies", movie.id, source="article", who="Polygon", note="Best heist films list")
    assert saved.json()["origin"]["source_label"] == "An article or website"
    assert authenticated_client.get("/library/recommenders", params={"category": "movies"}).json() == []
    assert page(authenticated_client, "movies", recommended_by="polygon")["total"] == 0


def test_validation(authenticated_client, db_session):
    me = _me(db_session)
    movie = add(db_session, me, "movies", "Heat")
    assert put(authenticated_client, "movies", movie.id, source="rumour").status_code == 422
    assert put(authenticated_client, "movies", movie.id, source="person").status_code == 422
    assert put(authenticated_client, "movies", movie.id, source="friend").status_code == 422
    assert put(authenticated_client, "movies", movie.id, source="other", note="x" * 281).status_code == 422
    assert put(authenticated_client, "movies", movie.id, source="other", who="a\u0007b").status_code == 422
    assert put(authenticated_client, "movies", 999999, source="browsing").status_code == 404
    assert put(authenticated_client, "nope", movie.id, source="browsing").status_code == 404


def test_friend_link_needs_a_real_friend(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    stranger = member(db_session, "zed")
    db_session.commit()
    movie = add(db_session, me, "movies", "Heat")

    linked = put(authenticated_client, "movies", movie.id, source="friend", friend_id=dana.id, who="ignored")
    assert linked.json()["origin"]["friend"] == {"id": dana.id, "username": "dana"}
    assert linked.json()["origin"]["who"] == "dana"

    # A stranger's id never links and never reveals their username.
    assert put(authenticated_client, "movies", movie.id, source="friend", friend_id=stranger.id).status_code == 422
    typed = put(authenticated_client, "movies", movie.id, source="friend", friend_id=stranger.id, who="Zee")
    assert typed.json()["origin"] == {**typed.json()["origin"], "source": "person", "friend": None, "who": "Zee"}


def test_origins_are_private(authenticated_client, db_session):
    me = _me(db_session)
    movie = add(db_session, me, "movies", "Heat")
    assert put(authenticated_client, "movies", movie.id, source="person", who="Sam", note="secret").status_code == 200
    dana = _friend(db_session, me)

    _as(authenticated_client, dana)
    assert authenticated_client.get(f"/library/origins/movies/{movie.id}").status_code == 404
    assert put(authenticated_client, "movies", movie.id, source="other").status_code == 404
    assert authenticated_client.delete(f"/library/origins/movies/{movie.id}").status_code == 404
    assert authenticated_client.get("/library/recommenders").json()["people"] == []
    assert db_session.query(models.TitleOrigin).filter_by(user_id=me.id).one().note == "secret"

    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    assert authenticated_client.get(f"/library/origins/movies/{movie.id}").status_code == 401


def test_friend_recommendation_prefills_the_origin(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, me)
    db_session.commit()
    authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": movie.id, "friend_ids": [dana.id], "note": "The docking scene!"})

    _as(authenticated_client, dana)
    rec = authenticated_client.get("/api/friend-recs/inbox").json()["items"][0]
    added = authenticated_client.post(f"/api/friend-recs/{rec['id']}/add", json={}).json()
    origin = authenticated_client.get(f"/library/origins/movies/{added['item_id']}").json()["origin"]
    assert origin["source"] == "friend" and origin["friend"]["username"] == "testuser"
    assert origin["note"] == "The docking scene!"


def test_prefill_never_overwrites_what_the_member_wrote(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    theirs = add_movie(db_session, dana)
    db_session.commit()
    saved = authenticated_client.post("/api/friend-feed/save", json={
        "friend_id": dana.id, "category": "movies", "item_id": theirs.id}).json()
    origin = authenticated_client.get(f"/library/origins/movies/{saved['item_id']}").json()["origin"]
    assert origin["friend"]["username"] == "dana" and origin["note"] == "Saved from the friends feed"

    put(authenticated_client, "movies", saved["item_id"], source="person", who="My brother")
    authenticated_client.post("/api/friend-feed/save", json={
        "friend_id": dana.id, "category": "movies", "item_id": theirs.id})
    origin = authenticated_client.get(f"/library/origins/movies/{saved['item_id']}").json()["origin"]
    assert origin["who"] == "My brother"


def test_shared_list_credits_the_friend_who_added_it(authenticated_client, db_session):
    me = _me(db_session)
    list_id = _new_list(authenticated_client, name="Couch queue")
    mine = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "game", "title": "Celeste"}).json()["id"]
    token = _token(authenticated_client, list_id)
    sam = _friend(db_session, me, "sam")
    _as(authenticated_client, sam)
    authenticated_client.post(f"/api/lists/join/{token}")
    theirs = authenticated_client.post(f"/api/lists/{list_id}/items", json={"kind": "movie", "title": "Arrival", "year": 2016}).json()["id"]

    _as(authenticated_client, me)
    authenticated_client.post(f"/api/lists/{list_id}/items/{theirs}/library")
    authenticated_client.post(f"/api/lists/{list_id}/items/{mine}/library")
    origins = {row.category: row for row in db_session.query(models.TitleOrigin).filter_by(user_id=me.id)}
    assert origins["movies"].source == "friend" and origins["movies"].friend_id == sam.id
    assert origins["movies"].note == 'From the shared list "Couch queue"'
    assert origins["video-games"].source == "other" and origins["video-games"].friend_id is None


def test_best_recommenders_ranks_by_how_much_you_liked_their_picks(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    picks = [
        ("movies", "Heat", "dana", 9.0, True), ("books", "Dune", "dana", 7.0, True), ("anime", "Mushishi", "dana", None, False),
        ("movies", "Cats", "Uncle Bob", 3.0, True), ("music", "Blue", "Uncle Bob", None, False),
        ("video-games", "Hades", "Priya", None, False),
    ]
    for category, title, who, rating, done in picks:
        field = CATEGORIES[category][3]
        item = add(db_session, me, category, title, rating=rating, **{field: done})
        if who == "dana":
            body = {"source": "friend", "friend_id": dana.id}
        else:
            body = {"source": "person", "who": who}
        assert put(authenticated_client, category, item.id, **body).status_code == 200

    data = authenticated_client.get("/library/recommenders").json()
    assert data["total_people"] == 3 and data["total_titles"] == 6
    first, second, third = data["people"]
    assert (first["name"], first["titles"], first["finished"], first["average_rating"]) == ("dana", 3, 2, 8.0)
    assert first["best"] == {"title": "Heat", "rating": 9.0, "category": "movies"}
    assert (second["name"], second["average_rating"]) == ("Uncle Bob", 3.0)
    assert (third["name"], third["average_rating"], third["top_shelf"]) == ("Priya", None, "video-games")


def test_deleting_a_title_removes_its_origin(authenticated_client, db_session):
    me = _me(db_session)
    movie = add(db_session, me, "movies", "Heat")
    put(authenticated_client, "movies", movie.id, source="person", who="Sam")
    delete_owned_media(db_session, me.id, "movies", movie.id)
    assert db_session.query(models.TitleOrigin).count() == 0


def test_friend_leaving_keeps_the_name(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add(db_session, me, "movies", "Heat")
    put(authenticated_client, "movies", movie.id, source="friend", friend_id=dana.id)
    dana.is_active = False
    db_session.commit()
    origin = authenticated_client.get(f"/library/origins/movies/{movie.id}").json()["origin"]
    assert origin["friend"] is None and origin["who"] == "dana"
    assert page(authenticated_client, "movies", recommended_by="dana")["total"] == 1


def test_json_backup_round_trip(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    heat = add(db_session, me, "movies", "Heat", director="Michael Mann", year=1995)
    dune = add(db_session, me, "books", "Dune", author="Frank Herbert", year=1965)
    put(authenticated_client, "movies", heat.id, source="friend", friend_id=dana.id, note="Diner scene")
    put(authenticated_client, "books", dune.id, source="video", who="A booktube video")

    backup = authenticated_client.get("/export/").json()
    assert backup["export_metadata"]["total_title_origins"] == 2
    rows = {row["title"]: row for row in backup["title_origins"]}
    assert rows["Heat"]["who"] == "dana" and rows["Heat"]["director"] == "Michael Mann"
    assert rows["Dune"]["source"] == "video" and rows["Dune"]["author"] == "Frank Herbert"

    db_session.query(models.TitleOrigin).delete()
    db_session.commit()
    restored = authenticated_client.post("/import/", json=backup)
    assert restored.status_code == 200, restored.text
    assert (restored.json()["origins_created"], restored.json()["origins_skipped"]) == (2, 0)
    heat_origin = authenticated_client.get(f"/library/origins/movies/{heat.id}").json()["origin"]
    assert heat_origin["friend"]["id"] == dana.id and heat_origin["note"] == "Diner scene"

    # Importing again leaves the existing notes alone.
    put(authenticated_client, "books", dune.id, source="person", who="Mum")
    again = authenticated_client.post("/import/", json=backup).json()
    assert (again["origins_created"], again["origins_skipped"]) == (0, 2)
    assert authenticated_client.get(f"/library/origins/books/{dune.id}").json()["origin"]["who"] == "Mum"


def test_import_skips_junk(authenticated_client, db_session):
    me = _me(db_session)
    add(db_session, me, "movies", "Heat")
    result = authenticated_client.post("/import/", json={"title_origins": [
        {"category": "movies", "title": "Missing", "source": "person", "who": "Sam"},
        {"category": "movies", "title": "Heat", "source": "nonsense"},
        {"category": "rocks", "title": "Heat", "source": "other"},
        {"category": "movies", "title": "Heat", "source": "person", "who": "x" * 500},
    ]})
    assert result.status_code == 200, result.text
    # The over-long name is trimmed rather than dropped.
    assert (result.json()["origins_created"], result.json()["origins_skipped"]) == (1, 3)


def test_spreadsheet_export_has_a_why_added_file(authenticated_client, db_session):
    me = _me(db_session)
    heat = add(db_session, me, "movies", "Heat")
    put(authenticated_client, "movies", heat.id, source="person", who="=cmd()", note="Diner")
    response = authenticated_client.get("/export/spreadsheet/")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    text = archive.read("why-added.csv").decode("utf-8-sig")
    assert text.splitlines()[0] == "category,title,source,who,note,updated_at"
    assert "Heat,person,'=cmd(),Diner" in text
    assert "why-added.csv" in archive.read("README.txt").decode("utf-8")


def test_saved_view_keeps_the_recommender(authenticated_client):
    saved = authenticated_client.post("/library/views/movies", json={
        "name": "From May", "filters": {"recommended_by": "  Aunt May "}})
    assert saved.status_code == 200, saved.text
    assert saved.json()["filters"]["recommended_by"] == "aunt may"
