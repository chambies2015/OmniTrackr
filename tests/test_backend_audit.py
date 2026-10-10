"""Regression coverage for native backup integrity and nullable catalog metadata."""
import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from app import auth, models, schemas
from app.crud import export_import as importer, statistics
from app.import_studio import parse_csv
from app.routers.activity import import_activity_entries


MEDIA = [
    ("movies", models.Movie, schemas.MovieCreate, importer.import_movies, {"director": "Creator", "year": 2000}),
    ("tv_shows", models.TVShow, schemas.TVShowCreate, importer.import_tv_shows, {"year": 2000}),
    ("anime", models.Anime, schemas.AnimeCreate, importer.import_anime, {"year": 2000}),
    ("video_games", models.VideoGame, schemas.VideoGameCreate, importer.import_video_games, {"release_date": datetime(2000, 1, 2)}),
    ("music", models.Music, schemas.MusicCreate, importer.import_music, {"artist": "Creator", "year": 2000}),
    ("books", models.Book, schemas.BookCreate, importer.import_books, {"author": "Creator", "year": 2000}),
]


def new_user(db, username="audit"):
    user = models.User(username=username, email=f"{username}@example.invalid", hashed_password="unused", is_verified=True)
    db.add(user)
    db.commit()
    return user


def owner(db):
    return db.query(models.User).filter_by(username="testuser").one()


@pytest.mark.parametrize("key,model,schema,apply,metadata", MEDIA)
def test_native_import_batch_deduplicates_and_rounds(db_session, key, model, schema, apply, metadata):
    user = new_user(db_session)
    first = schema(title="Repeated", rating=7.84, **metadata)
    second = schema(title="Repeated", rating=8.24, **metadata)
    assert apply(db_session, user.id, [first, second]) == (1, 1, [])
    item = db_session.query(model).filter_by(user_id=user.id).one()
    assert item.rating == 8.2


@pytest.mark.parametrize("key,model,schema,apply,metadata", [MEDIA[0], MEDIA[4], MEDIA[5]])
def test_native_import_preserves_same_title_creator_editions(db_session, key, model, schema, apply, metadata):
    user = new_user(db_session)
    entries = [schema(title="Edition", **{**metadata, "year": year}) for year in (2000, 2020)]
    assert apply(db_session, user.id, entries) == (2, 0, [])
    assert apply(db_session, user.id, entries) == (0, 2, [])
    assert sorted(row.year for row in db_session.query(model).filter_by(user_id=user.id)) == [2000, 2020]


@pytest.mark.parametrize("file_upload", [False, True])
def test_native_backup_roundtrip_nullable_metadata_and_game_collection(authenticated_client, db_session, file_upload):
    client, db = authenticated_client, db_session
    user = owner(db)
    source_rows = []
    for key, model, _, _, metadata in MEDIA:
        nullable = {field: None for field in metadata}
        row = model(user_id=user.id, title=key, rating=0, review="Private backup note", **nullable)
        db.add(row)
        source_rows.append(row)
    dated_game = models.VideoGame(user_id=user.id, title="Dated game", release_date=datetime(2020, 1, 2, 3, 4, 5))
    db.add(dated_game)
    db.flush()
    collection = models.Collection(user_id=user.id, name="Portable games")
    db.add(collection)
    db.flush()
    db.add(models.CollectionItem(collection_id=collection.id, category="video-games", item_id=dated_game.id, position=0))
    db.commit()
    response = client.get("/export/")
    assert response.status_code == 200
    backup = response.json()
    restored_owner = new_user(db, "restore")
    client.cookies.clear()
    client.headers = {"Authorization": f"Bearer {auth.create_access_token({'sub': restored_owner.username})}"}
    if file_upload:
        response = client.post("/import/file/", files={"file": ("backup.JSON", json.dumps(backup), "application/json")})
    else:
        response = client.post("/import/", json=backup)
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []
    for key, model, _, _, metadata in MEDIA:
        row = db.query(model).filter_by(user_id=restored_owner.id, title=key).one()
        assert all(getattr(row, field) is None for field in metadata)
        assert row.rating == 0 and row.review == "Private backup note"
    restored_collection = db.query(models.Collection).filter_by(user_id=restored_owner.id).one()
    assert len(restored_collection.items) == 1
    restored_game = db.get(models.VideoGame, restored_collection.items[0].item_id)
    assert restored_game.user_id == restored_owner.id and restored_game.title == "Dated game"


def test_collection_restore_null_identity_and_duplicate_references(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    known = models.Book(user_id=user.id, title="Shared title", author="Writer", year=2020)
    unknown = models.Book(user_id=user.id, title="Shared title", author=None, year=None)
    db.add_all([known, unknown])
    db.commit()
    item = {"category": "books", "title": "Shared title", "author": None, "year": None}
    payload = {"collections": [{"name": "Exact edition", "items": [item, item, {"category": [], "title": "Invalid"}]}]}
    response = client.post("/import/", json=payload)
    assert response.status_code == 200, response.text
    collection = db.query(models.Collection).filter_by(name="Exact edition").one()
    assert [entry.item_id for entry in collection.items] == [unknown.id]


def test_collection_restore_skips_ambiguous_old_backup_item(authenticated_client, db_session):
    user = owner(db_session)
    db_session.add_all([models.Book(user_id=user.id, title="Edition", author="Writer", year=year) for year in (2000, 2020)])
    db_session.commit()
    response = authenticated_client.post("/import/", json={"collections": [{"name": "Old backup", "items": [{"category": "books", "title": "Edition"}]}]})
    assert response.status_code == 200
    assert db_session.query(models.CollectionItem).count() == 0


@pytest.mark.parametrize("key,model,schema,apply,metadata", MEDIA)
@pytest.mark.parametrize("field,value", [("title", None), ("title", "  "), ("review_public", None)])
def test_media_update_rejects_unusable_required_values(key, model, schema, apply, metadata, field, value):
    update = getattr(schemas, schema.__name__.removesuffix("Create") + "Update")
    with pytest.raises(ValidationError):
        update(**{field: value})
    assert update().model_dump(exclude_unset=True) == {}
    assert update(rating=None).rating is None


@pytest.mark.parametrize("field", ["name", "source_type", "allow_uploads", "fields"])
def test_custom_tab_update_rejects_null(field):
    with pytest.raises(ValidationError):
        schemas.CustomTabUpdate(**{field: None})


def test_custom_item_field_values_null_rejected():
    with pytest.raises(ValidationError):
        schemas.CustomTabItemUpdate(field_values=None)


def test_statistics_handle_missing_metadata_and_zero_rating(db_session):
    user = new_user(db_session)
    for key, model, _, _, metadata in MEDIA:
        db_session.add(model(user_id=user.id, title=key, rating=0, **{field: None for field in metadata}))
    db_session.commit()
    assert statistics.get_year_statistics(db_session, user.id)["all_years"] == []
    assert statistics.get_director_statistics(db_session, user.id)["top_directors"] == []
    overall = statistics.get_rating_statistics(db_session, user.id)
    assert overall["rating_distribution"] == {"0": 6}
    for apply in (statistics.get_movie_statistics, statistics.get_tv_show_statistics, statistics.get_anime_statistics,
                  statistics.get_video_game_statistics, statistics.get_music_statistics, statistics.get_books_statistics):
        result = apply(db_session, user.id)
        assert result["year_stats"]["all_years"] == []
        assert result["watch_stats"]["total_items"] == 1
        assert result["rating_stats"]["rating_distribution"] == {"0": 1}


def test_activity_backup_ids_do_not_rebind_and_batch_duplicates_are_skipped(db_session):
    user = new_user(db_session)
    unrelated = models.Movie(user_id=user.id, title="Unrelated", director="Creator", year=2000)
    correct = models.Movie(user_id=user.id, title="Journal title", director="Creator", year=2020)
    db_session.add_all([unrelated, correct])
    db_session.commit()
    entry = schemas.ActivityEntryImport(category="movies", item_id=unrelated.id, title=correct.title,
                                        action="completed", occurred_at=datetime(2026, 1, 1))
    assert import_activity_entries(db_session, user.id, [entry, entry]) == (1, 1)
    assert db_session.query(models.ActivityEntry).one().item_id == correct.id


def test_custom_tab_reimport_does_not_multiply_identical_items(authenticated_client, db_session):
    tab = {"name": "Journal", "fields": [], "items": [{"title": "Entry", "field_values": {}}, {"title": "Entry", "field_values": {}}]}
    for _ in range(2):
        response = authenticated_client.post("/import/", json={"custom_tabs": [tab]})
        assert response.status_code == 200
        assert response.json()["errors"] == []
    assert db_session.query(models.CustomTabItem).count() == 2


@pytest.mark.parametrize("source,content,mapping,expected", [
    ("letterboxd", b"Name,Year,Alternative,Done,Note\nOriginal,2000,Chosen,no,\n", {"title": "Alternative", "status": "Done", "review": "Note"}, ("Chosen", False)),
    ("goodreads", b"Title,Author,Exclusive Shelf,Date Read,Alternative,Maker,Done\nOriginal,Old writer,read,2020-01-01,Chosen,Chosen writer,no\n", {"title": "Alternative", "creator": "Maker", "status": "Done"}, ("Chosen", False)),
    ("myanimelist", b"series_title,my_status,Alternative,Done,Year\nOriginal,Completed,Chosen,no,2020\n", {"title": "Alternative", "status": "Done", "year": "Year"}, ("Chosen", False)),
])
def test_source_adapters_honor_explicit_mappings(source, content, mapping, expected):
    _, rows = parse_csv(content, source, column_mapping=mapping)
    data = rows[0].data
    assert data is not None
    assert (data["title"], data.get("watched", data.get("read"))) == expected
    if source == "goodreads":
        assert data["author"] == "Chosen writer"
    elif source == "myanimelist":
        assert data["year"] == 2020


@pytest.mark.parametrize("body", [[], "movies", 1, None])
def test_json_import_requires_object(authenticated_client, body):
    response = authenticated_client.post("/import/file/", files={"file": ("backup.json", json.dumps(body), "application/json")})
    assert response.status_code == 400


def test_failed_native_commit_rolls_back_sqlite_savepoints(db_session, monkeypatch):
    user = new_user(db_session)
    def fail_commit():
        raise RuntimeError("Simulated commit failure")
    monkeypatch.setattr(db_session, "commit", fail_commit)
    result = importer.import_movies(db_session, user.id, [schemas.MovieCreate(title="Rollback", director="Creator", year=2020)])
    assert result[0:2] == (0, 0) and result[2]
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 0


def test_concurrent_csv_applies_only_create_one_copy(tmp_path, monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from io import BytesIO
    from types import SimpleNamespace
    from fastapi import UploadFile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.import_studio import fingerprint
    from app.routers import import_studio as routes

    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-import.db'}", connect_args={"check_same_thread": False, "timeout": 5})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        user_id = new_user(db).id
    content = b"title,director,year\nConcurrent,Creator,2020\n"
    digest = fingerprint(content, "generic", "movies", "")
    first_classified = threading.Event()
    second_classified = threading.Event()
    order_lock = threading.Lock()
    calls = 0
    original = routes.classify_rows

    def coordinate_classification(db, owner_id, rows):
        nonlocal calls
        with order_lock:
            calls += 1
            first = calls == 1
        result = original(db, owner_id, rows)
        if first:
            first_classified.set()
            # Without the owner lock, both requests classify the empty library.
            # With it, the second classification follows the first commit.
            second_classified.wait(timeout=0.5)
        else:
            second_classified.set()
        return result

    monkeypatch.setattr(routes, "classify_rows", coordinate_classification)
    def apply():
        with factory() as db:
            return asyncio.run(routes.apply_import(
                file=UploadFile(filename="library.csv", file=BytesIO(content)),
                fingerprint_confirmation=digest, source="generic", category="movies", mapping_json="",
                current_user=SimpleNamespace(id=user_id), db=db,
            ))
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(apply)
            assert first_classified.wait(timeout=5)
            second = workers.submit(apply)
            results = [first.result(timeout=10), second.result(timeout=10)]
        assert sum(result["created_count"] for result in results) == 1
        assert sum(result["duplicate_count"] for result in results) == 1
        with factory() as db:
            assert db.query(models.Movie).filter_by(user_id=user_id).count() == 1
    finally:
        engine.dispose()
