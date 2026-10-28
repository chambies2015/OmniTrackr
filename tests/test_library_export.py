"""Library exports beyond the JSON backup: spreadsheet ZIP, Letterboxd and Goodreads layouts."""
import csv
import io
import zipfile
from datetime import datetime

from app import library_export, models
from app.import_studio import parse_csv


def owner(db):
    return db.query(models.User).filter(models.User.username == "testuser").one()


def rows(text):
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def seed(db):
    user = owner(db)
    arrival = models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016,
                           rating=9.0, watched=True, review="Heptapods, then grief.")
    heat = models.Movie(user_id=user.id, title="Heat", director="Michael Mann", year=1995, watched=False)
    dune = models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965, rating=7.0, read=True,
                       review="=HYPERLINK(\"http://evil\")")
    tbr = models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", year=2020, read=False)
    game = models.VideoGame(user_id=user.id, title="Hades", release_date=datetime(2020, 9, 17), genres="Roguelike",
                            rating=9.5, played=True)
    db.add_all([arrival, heat, dune, tbr, game])
    db.commit()
    for when, action in ((datetime(2024, 1, 5, 12), "completed"), (datetime(2025, 3, 2, 12), "revisited")):
        db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=arrival.id, title="Arrival",
                                    action=action, occurred_at=when))
    db.add(models.ActivityEntry(user_id=user.id, category="books", item_id=dune.id, title="Dune",
                                action="completed", occurred_at=datetime(2023, 8, 1, 12)))
    db.commit()
    return user


def test_unknown_format_is_404(authenticated_client):
    assert authenticated_client.get("/export/mal/").status_code == 404


def test_exports_need_an_account(client):
    assert client.get("/export/spreadsheet/").status_code in (401, 403)


def test_spreadsheet_zip_holds_every_shelf_and_reimports(authenticated_client, db_session):
    seed(db_session)
    response = authenticated_client.get("/export/spreadsheet/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"README.txt", "library.csv", "journal.csv", "collections.csv", "progress.csv"} <= names
    library_text = archive.read("library.csv").decode("utf-8")
    library = {row["title"]: row for row in rows(library_text)}
    assert set(library) == {"Arrival", "Heat", "Dune", "Piranesi", "Hades"}
    assert library["Arrival"]["creator"] == "Denis Villeneuve"
    assert library["Arrival"]["rating"] == "9"
    assert library["Heat"]["completed"] == "no"
    assert library["Hades"]["release_date"] == "2020-09-17"
    assert library["Hades"]["genre"] == "Roguelike"
    # A stored formula is shown as text, never run.
    assert library["Dune"]["review"].startswith("'=")
    journal = rows(archive.read("journal.csv").decode("utf-8"))
    assert [entry["action"] for entry in journal] == ["revisited", "completed", "completed"]

    # library.csv goes back in through the Import Studio's spreadsheet option.
    source, parsed = parse_csv(archive.read("library.csv"), "auto", None, None, "library.csv")
    assert source == "generic"
    assert not [row.error for row in parsed if row.error]
    assert {row.category for row in parsed} == {"movies", "books", "video-games"}


def test_custom_tabs_get_their_own_file(authenticated_client):
    tab = authenticated_client.post("/custom-tabs/", json={
        "name": "Board Games", "source_type": "none", "allow_uploads": False,
        "fields": [{"key": "players", "label": "Players", "field_type": "text", "required": False, "order": 0}],
    })
    assert tab.status_code in (200, 201), tab.text
    item = authenticated_client.post(f"/custom-tabs/{tab.json()['id']}/items",
                                     json={"title": "Catan", "field_values": {"players": "3-4"}})
    assert item.status_code in (200, 201), item.text
    archive = zipfile.ZipFile(io.BytesIO(authenticated_client.get("/export/spreadsheet/").content))
    board = rows(archive.read("custom-tabs/board-games.csv").decode("utf-8"))
    # "3-4" doesn't start with a formula character; "-" in the middle is left alone.
    assert board == [{"title": "Catan", "Players": "3-4", "poster_url": ""}]


def test_letterboxd_writes_one_row_per_watch(authenticated_client, db_session):
    seed(db_session)
    response = authenticated_client.get("/export/letterboxd/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    films = rows(response.text)
    assert [film["Title"] for film in films] == ["Arrival", "Arrival"]
    first, second = films
    assert (first["WatchedDate"], first["Rewatch"], first["Rating"], first["Review"]) == ("2024-01-05", "", "", "")
    assert (second["WatchedDate"], second["Rewatch"], second["Rating"]) == ("2025-03-02", "Yes", "4.5")
    assert second["Review"] == "Heptapods, then grief."
    assert second["Directors"] == "Denis Villeneuve"


def test_letterboxd_watchlist_is_the_unwatched_films(authenticated_client, db_session):
    seed(db_session)
    films = rows(authenticated_client.get("/export/letterboxd-watchlist/").text)
    assert films == [{"Title": "Heat", "Year": "1995", "Directors": "Michael Mann"}]


def test_goodreads_layout_round_trips_through_the_import_studio(authenticated_client, db_session):
    seed(db_session)
    response = authenticated_client.get("/export/goodreads/")
    books = {row["Title"]: row for row in rows(response.text)}
    assert books["Dune"]["My Rating"] == "4"
    assert books["Dune"]["Exclusive Shelf"] == "read"
    assert books["Dune"]["Date Read"] == "2023/08/01"
    assert books["Dune"]["Author l-f"] == "Herbert, Frank"
    assert books["Piranesi"]["Exclusive Shelf"] == "to-read"
    assert books["Piranesi"]["My Rating"] == "0"
    source, parsed = parse_csv(response.content, "auto", None, None, "goodreads.csv")
    assert source == "goodreads"
    assert {row.title for row in parsed if not row.error} == {"Dune", "Piranesi"}


def test_five_star_scale():
    assert library_export._five_star(None, 0.5) == ""
    assert library_export._five_star(0, 0.5) == ""
    assert library_export._five_star(0.4, 0.5) == "0.5"
    assert library_export._five_star(7.3, 0.5) == "3.5"
    assert library_export._five_star(10, 0.5) == "5"
    assert library_export._five_star(5, 1) == "2"
    assert library_export._five_star(1, 1) == "1"


def test_exports_leave_the_library_alone(authenticated_client, db_session):
    seed(db_session)
    before = [(m.title, m.rating, m.watched, m.review) for m in db_session.query(models.Movie).order_by(models.Movie.id)]
    for fmt in library_export.FORMATS:
        assert authenticated_client.get(f"/export/{fmt}/").status_code == 200
    db_session.expire_all()
    after = [(m.title, m.rating, m.watched, m.review) for m in db_session.query(models.Movie).order_by(models.Movie.id)]
    assert before == after
