"""Library items record when they were added, without inventing dates for older items."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import migrations, models

CREATE_PAYLOADS = {
    "/movies/": {"title": "Arrival", "director": "Denis Villeneuve", "year": 2016},
    "/tv-shows/": {"title": "Severance", "year": 2022},
    "/anime/": {"title": "Frieren", "year": 2023},
    "/video-games/": {"title": "Hades"},
    "/music/": {"title": "Blonde", "artist": "Frank Ocean", "year": 2016},
    "/books/": {"title": "Piranesi", "author": "Susanna Clarke", "year": 2020},
}

MEDIA_MODELS = {
    "movies": models.Movie, "tv_shows": models.TVShow, "anime": models.Anime,
    "video_games": models.VideoGame, "music": models.Music, "books": models.Book,
}


@pytest.mark.parametrize("file_upload", [False, True])
def test_all_backup_categories_preserve_dates_without_rewriting_existing_rows(
    authenticated_client, db_session, file_upload,
):
    dated = "2020-01-02T03:04:05+02:00"
    payload = {}
    for path, fields in CREATE_PAYLOADS.items():
        category = path.strip("/").replace("-", "_")
        payload[category] = [
            dict(fields, title=f"{category}-dated", added_at=dated, review_public=False),
            dict(fields, title=f"{category}-unknown", added_at=None),
            dict(fields, title=f"{category}-missing"),
            dict(fields, title=f"{category}-future", added_at="2999-01-01T00:00:00"),
        ]

    def restore(data):
        if file_upload:
            return authenticated_client.post(
                "/import/file/", files={"file": ("backup.json", json.dumps(data), "application/json")},
            )
        return authenticated_client.post("/import/", json=data)

    response = restore(payload)
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []
    for category, model in MEDIA_MODELS.items():
        rows = {row.title: row for row in db_session.query(model).all()}
        assert rows[f"{category}-dated"].added_at == datetime(2020, 1, 2, 1, 4, 5)
        assert all(rows[f"{category}-{suffix}"].added_at is None for suffix in ("unknown", "missing", "future"))

    exported = authenticated_client.get("/export/").json()
    for category in MEDIA_MODELS:
        for row in exported[category]:
            row["added_at"] = "2000-01-01T00:00:00"
            row["rating"] = 8.6
    response = restore(exported)
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []
    db_session.expire_all()
    for category, model in MEDIA_MODELS.items():
        rows = {row.title: row for row in db_session.query(model).all()}
        assert len(rows) == 4
        assert rows[f"{category}-dated"].added_at == datetime(2020, 1, 2, 1, 4, 5)
        assert all(rows[f"{category}-{suffix}"].added_at is None for suffix in ("unknown", "missing", "future"))
        assert all(row.rating == 8.6 and row.review_public is False for row in rows.values())


def test_new_items_record_added_at(authenticated_client):
    before = datetime.utcnow() - timedelta(seconds=5)
    for path, payload in CREATE_PAYLOADS.items():
        response = authenticated_client.post(path, json=payload)
        assert response.status_code in (200, 201), (path, response.text)
        added_at = response.json()["added_at"]
        assert added_at is not None, path
        assert datetime.fromisoformat(added_at.replace("Z", "")) >= before


def test_clients_cannot_set_added_at_on_create(authenticated_client):
    payload = dict(CREATE_PAYLOADS["/movies/"], added_at="2001-01-01T00:00:00")
    response = authenticated_client.post("/movies/", json=payload)
    assert response.status_code in (200, 201)
    assert not response.json()["added_at"].startswith("2001")


def test_updates_leave_added_at_alone(authenticated_client, db_session):
    created = authenticated_client.post("/movies/", json=CREATE_PAYLOADS["/movies/"]).json()
    response = authenticated_client.put(f"/movies/{created['id']}", json={"rating": 9})
    assert response.status_code == 200
    assert response.json()["added_at"] == created["added_at"]


def test_existing_items_without_a_date_stay_unknown(authenticated_client, db_session):
    created = authenticated_client.post("/books/", json=CREATE_PAYLOADS["/books/"]).json()
    book = db_session.get(models.Book, created["id"])
    book.added_at = None  # As left by the migration for rows that predate tracking.
    db_session.commit()

    listed = authenticated_client.get("/books/").json()
    assert listed[0]["added_at"] is None
    exported = authenticated_client.get("/export/").json()
    assert exported["books"][0]["added_at"] is None


def test_backup_round_trip_keeps_add_dates_and_unknowns(authenticated_client, db_session):
    backup = {
        "movies": [
            {"title": "Dated", "director": "A", "year": 2000, "added_at": "2026-09-14T10:30:00"},
            {"title": "Undated", "director": "B", "year": 2001},
            {"title": "Future", "director": "C", "year": 2002, "added_at": "2999-01-01T00:00:00"},
        ],
        "tv_shows": [],
    }
    files = {"file": ("backup.json", json.dumps(backup).encode(), "application/json")}
    response = authenticated_client.post("/import/file/", files=files)
    assert response.status_code == 200, response.text

    rows = {m.title: m.added_at for m in db_session.query(models.Movie).all()}
    assert rows["Dated"] == datetime(2026, 9, 14, 10, 30)
    assert rows["Undated"] is None
    assert rows["Future"] is None


def test_import_never_rewrites_an_existing_items_date(authenticated_client, db_session):
    created = authenticated_client.post("/movies/", json=CREATE_PAYLOADS["/movies/"]).json()
    backup = {"movies": [dict(CREATE_PAYLOADS["/movies/"], added_at="2020-01-01T00:00:00")], "tv_shows": []}
    files = {"file": ("backup.json", json.dumps(backup).encode(), "application/json")}
    assert authenticated_client.post("/import/file/", files=files).status_code == 200
    db_session.expire_all()
    movie = db_session.get(models.Movie, created["id"])
    assert movie.added_at.year != 2020


def test_migration_adds_nullable_column_without_touching_rows(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE movies (id INTEGER PRIMARY KEY, title VARCHAR, user_id INTEGER)"))
        conn.execute(text("INSERT INTO movies (id, title, user_id) VALUES (1, 'Old favourite', 7)"))
        conn.commit()
    monkeypatch.setattr(migrations, "engine", engine)

    migrations.add_library_added_at_columns()
    migrations.add_library_added_at_columns()  # Safe to run on every boot.

    assert "added_at" in {c["name"] for c in inspect(engine).get_columns("movies")}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, title, user_id, added_at FROM movies")).one()
    assert tuple(row) == (1, "Old favourite", 7, None)
