"""The JSON backup carries library tags and saved views, and an import puts them back without overwriting."""
from app import models
from tests.test_friend_recs import _me
from tests.test_library_tags import add


def tag(client, category, item_id, *labels):
    response = client.put(f"/library/tags/{category}/{item_id}", json={"tags": list(labels)})
    assert response.status_code == 200, response.text


def save_view(client, category, name, **filters):
    response = client.post(f"/library/views/{category}", json={"name": name, "filters": filters})
    assert response.status_code == 200, response.text


def test_round_trip_restores_tags_and_views(authenticated_client, db_session):
    me = _me(db_session)
    heat = add(db_session, me, "movies", "Heat", director="Michael Mann", year=1995)
    remake = add(db_session, me, "movies", "Heat", director="Someone Else", year=2030)
    dune = add(db_session, me, "books", "Dune", author="Frank Herbert", year=1965)
    tag(authenticated_client, "movies", heat.id, "Comfort watch", "with Sam")
    tag(authenticated_client, "books", dune.id, "Reread")
    save_view(authenticated_client, "movies", "Comfort", tag="comfort watch", sort="rating-desc")
    save_view(authenticated_client, "books", "To finish", completion="unfinished")

    backup = authenticated_client.get("/export/").json()
    assert backup["export_metadata"]["total_tagged_titles"] == 2
    assert backup["export_metadata"]["total_saved_views"] == 2
    rows = {(row["category"], row["title"]): row for row in backup["library_tags"]}
    assert rows[("movies", "Heat")]["tags"] == ["Comfort watch", "with Sam"]
    assert rows[("movies", "Heat")]["director"] == "Michael Mann"
    views = {view["name"]: view for view in backup["saved_views"]}
    assert views["Comfort"]["category"] == "movies" and views["Comfort"]["filters"]["sort"] == "rating-desc"

    db_session.query(models.LibraryTag).delete()
    db_session.query(models.SavedLibraryView).delete()
    db_session.commit()
    tag(authenticated_client, "movies", heat.id, "comfort WATCH")  # kept, and its spelling wins

    restored = authenticated_client.post("/import/", json=backup)
    assert restored.status_code == 200, restored.text
    result = restored.json()
    assert (result["tags_created"], result["tags_skipped"]) == (2, 1)
    assert (result["views_created"], result["views_skipped"]) == (2, 0)
    labels = {label for (label,) in db_session.query(models.LibraryTag.label).filter_by(item_id=heat.id, category="movies")}
    assert labels == {"comfort WATCH", "with Sam"}
    assert db_session.query(models.LibraryTag).filter_by(item_id=remake.id, category="movies").count() == 0
    listed = authenticated_client.get("/library/views/books").json()
    assert [view["name"] for view in listed] == ["To finish"] and listed[0]["filters"]["completion"] == "unfinished"

    again = authenticated_client.post("/import/", json=backup).json()
    assert (again["tags_created"], again["views_created"], again["views_skipped"]) == (0, 0, 2)


def test_import_skips_bad_tags_and_views(authenticated_client, db_session):
    me = _me(db_session)
    heat = add(db_session, me, "movies", "Heat", director="Michael Mann", year=1995)
    result = authenticated_client.post("/import/", json={
        "library_tags": [
            {"category": "movies", "title": "Heat", "tags": ["fine", "has,comma", 7, "x" * 40]
             + [f"t{i}" for i in range(15)]},
            {"category": "nope", "title": "Heat", "tags": ["a"]},
            {"category": "movies", "title": "Missing", "tags": ["a", "b"]},
            {"category": "movies", "title": "Heat", "tags": "not a list"},
        ],
        "saved_views": [
            {"category": "movies", "name": "Bad sort", "filters": {"sort": "evil"}},
            {"category": "movies", "name": "", "filters": {}},
            {"category": "games", "name": "Wrong shelf", "filters": {}},
            {"category": "movies", "name": "Long search", "filters": {"search": "x" * 600}},
            {"category": "movies", "name": "Progress", "filters": {"has_progress": True}},
        ],
    })
    assert result.status_code == 200, result.text
    body = result.json()
    on_heat = db_session.query(models.LibraryTag).filter_by(item_id=heat.id, category="movies").count()
    assert on_heat == 10 and body["tags_created"] == 10
    assert (body["views_created"], body["views_skipped"]) == (1, 4)
    [view] = authenticated_client.get("/library/views/movies").json()
    assert view["name"] == "Progress" and view["filters"]["has_progress"] is False


def test_other_members_backups_cannot_touch_my_shelves(authenticated_client, db_session):
    other = models.User(username="intruder", email="in@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.commit()
    theirs = add(db_session, other, "movies", "Heat", director="Michael Mann", year=1995)
    result = authenticated_client.post("/import/", json={
        "library_tags": [{"category": "movies", "title": "Heat", "tags": ["mine now"]}]}).json()
    assert result["tags_created"] == 0
    assert db_session.query(models.LibraryTag).filter_by(item_id=theirs.id).count() == 0
