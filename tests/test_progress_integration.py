"""Checkpoints across private recommendations, portable backups, and restore merges."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from app import auth, models, return_prompt


def owner(db):
    return db.query(models.User).filter_by(username="testuser").one()


def save(client, category, item, position=4, **extra):
    payload = {"unit": "page" if category == "books" else "episode", "position": position,
               "expected_revision": 0, "note": "Private checkpoint sentinel"}
    payload.update(extra)
    response = client.put(f"/progress/{category}/{item.id}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def add_book(db, user_id, **fields):
    book = models.Book(user_id=user_id, title="The Lantern Atlas", author="Sample Author", year=2024, **fields)
    db.add(book)
    db.commit()
    return book


def switch_user(client, db):
    user = models.User(username="restore_reader", email="restore@example.invalid", hashed_password="unused", is_verified=True)
    db.add(user)
    db.commit()
    client.cookies.clear()
    client.headers = {"Authorization": f"Bearer {auth.create_access_token({'sub': user.username})}"}
    return user


def test_continue_prioritizes_recent_checkpoints_across_categories(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    book = add_book(db, user.id)
    show = models.TVShow(user_id=user.id, title="Quiet Observatory", year=2025, watched=False)
    completed = models.Anime(user_id=user.id, title="Already finished", watched=True)
    db.add_all([show, completed] + [models.Movie(user_id=user.id, title=f"New movie {i}", watched=False) for i in range(8)])
    db.commit()
    save(client, "books", book, 42)
    save(client, "tv-shows", show, 3, season=2)
    save(client, "anime", completed, 8)
    book_checkpoint = db.query(models.ProgressCheckpoint).filter_by(category="books").one()
    book_checkpoint.updated_at = datetime.utcnow() - timedelta(days=1)
    db.commit()
    before = db.query(models.ProgressCheckpoint).count()
    response = client.get("/statistics/pulse/")
    assert response.status_code == 200
    items = response.json()["continue_items"]
    assert [(item["category"], item["id"]) for item in items[:2]] == [("tv-shows", show.id), ("books", book.id)]
    assert items[0]["progress"]["season"] == 2
    assert items[1]["progress"]["position"] == 42
    assert not any(item["category"] == "anime" for item in items)
    assert db.query(models.ProgressCheckpoint).count() == before
    client.request("DELETE", f"/progress/tv-shows/{show.id}", json={"expected_revision": 1})
    after = client.get("/statistics/pulse/").json()["continue_items"]
    assert after[0]["category"] == "books"
    assert not any(item.get("progress") for item in after if item["category"] == "tv-shows")


def test_queue_order_today_and_return_deck_keep_private_checkpoints(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    book = add_book(db, user.id)
    show = models.TVShow(user_id=user.id, title="First chosen", watched=False)
    db.add_all([show] + [models.Movie(user_id=user.id, title=f"Film {i}") for i in range(3)])
    db.commit()
    for category, item in [("tv-shows", show), ("books", book)]:
        assert client.post("/next-up/", json={"category": category, "item_id": item.id}).status_code == 201
        save(client, category, item)
    queue = client.get("/next-up/").json()
    assert [item["category"] for item in queue] == ["tv-shows", "books"]
    assert all(item["progress"]["position"] == 4 for item in queue)
    assert client.get("/statistics/today/").json()["pick"]["category"] == "tv-shows"
    token = return_prompt.create_return_prompt_token(7, user.id)
    deck = client.get("/statistics/return-deck/", headers={"X-Return-Prompt": token})
    assert deck.status_code == 200
    assert deck.json()["primary"]["progress"]["position"] == 4
    assert deck.json()["alternative"]["progress"]["unit"] == "page"
    switch_user(client, db)
    assert client.get("/next-up/").json() == []
    assert client.get("/statistics/pulse/").json()["continue_items"] == []
    assert client.get("/export/").json()["progress_checkpoints"] == []


@pytest.mark.parametrize("file_upload", [False, True])
def test_backup_round_trip_remaps_owner_and_preserves_existing_progress(authenticated_client, db_session, file_upload):
    client, db = authenticated_client, db_session
    book = add_book(db, owner(db).id, rating=8, review="Separate review")
    save(client, "books", book, 57, unit="chapter")
    backup = client.get("/export/").json()
    assert backup["export_metadata"]["version"] == "1.3"
    assert backup["export_metadata"]["total_progress_checkpoints"] == 1
    entry = backup["progress_checkpoints"][0]
    assert entry["title"] == book.title and entry["year"] == book.year and entry["author"] == book.author
    assert "item_id" not in entry and "user_id" not in entry and "revision" not in entry["checkpoint"]
    # Imported database IDs and timestamps are never authority for ownership or recency.
    entry.update(item_id=book.id, user_id=book.user_id, updated_at="9999-01-01T00:00:00Z")
    other = switch_user(client, db)
    def restore():
        if file_upload:
            return client.post("/import/file/", files={"file": ("backup.json", json.dumps(backup), "application/json")})
        return client.post("/import/", json=backup)
    response = restore()
    assert response.status_code == 200, response.text
    assert response.json()["progress_created"] == 1
    restored = db.query(models.Book).filter_by(user_id=other.id).one()
    assert restored.id != book.id
    checkpoint = client.get(f"/progress/books/{restored.id}").json()
    assert checkpoint["checkpoint"]["position"] == 57 and checkpoint["revision"] == 1
    assert not checkpoint["checkpoint"]["updated_at"].startswith("9999")
    save(client, "books", restored, 70, expected_revision=1)
    assert restore().json()["progress_skipped"] == 1
    assert client.get(f"/progress/books/{restored.id}").json()["checkpoint"]["position"] == 70
    client.request("DELETE", f"/progress/books/{restored.id}", json={"expected_revision": 2})
    assert restore().json()["progress_skipped"] == 1
    assert client.get(f"/progress/books/{restored.id}").json()["checkpoint"] is None
    assert client.get("/export/").json()["progress_checkpoints"] == []


def test_restore_skips_ambiguous_editions_missing_identity_and_malformed_payloads(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    book = add_book(db, user.id)
    add_book(db, user.id)
    base = {"category": "books", "title": book.title, "year": book.year, "author": book.author,
            "checkpoint": {"unit": "page", "position": 3}}
    entries = [base, {**base, "year": 2023}, {**base, "author": "Another author"},
               {**base, "category": []}, {**base, "category": {}}, {**base, "title": 123},
               {**base, "year": True}, {**base, "year": 10**40}, {**base, "checkpoint": None},
               {**base, "checkpoint": {"unit": "page", "position": 3, "user_id": 1}},
               {key: value for key, value in base.items() if key != "year"},
               {key: value for key, value in base.items() if key != "author"}]
    result = client.post("/import/", json={"progress_checkpoints": entries})
    assert result.status_code == 200, result.text
    assert result.json()["progress_created"] == 0 and result.json()["progress_skipped"] == len(entries)
    assert db.query(models.ProgressCheckpoint).count() == 0


def test_restore_null_edition_identity_is_exact_and_duplicates_skip(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    unknown = models.Book(user_id=user.id, title="A Title", year=None, author=None)
    known = models.Book(user_id=user.id, title="A Title", year=2024, author="A Writer")
    db.add_all([known, unknown])
    db.commit()
    entry = {"category": "books", "title": " a title ", "year": None, "author": None,
             "checkpoint": {"unit": "page", "position": 10}}
    result = client.post("/import/", json={"progress_checkpoints": [entry, entry]})
    assert result.status_code == 200
    assert result.json()["progress_created"] == result.json()["progress_skipped"] == 1
    checkpoint = db.query(models.ProgressCheckpoint).one()
    assert checkpoint.item_id == unknown.id


def test_legacy_backups_remain_valid_and_do_not_touch_progress(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    book = add_book(db, owner(db).id)
    before = save(client, "books", book)
    for response in (
        client.post("/import/", json={"movies": [], "tv_shows": []}),
        client.post("/import/file/", files={"file": ("old.json", '{"movies":[],"tv_shows":[]}', "application/json")}),
    ):
        assert response.status_code == 200
        assert response.json()["progress_created"] == response.json()["progress_skipped"] == 0
    assert client.get(f"/progress/books/{book.id}").json() == before


@pytest.mark.parametrize("title, author", [
    ("Épisode • Ночь", "Élodie Ирина"),
    ("\u00a0Book\u00a0", "\tAuthor\n"),
    ("Title " + "a" * 501, "Author"),
])
def test_unicode_title_and_author_restore_their_exported_edition(authenticated_client, db_session, title, author):
    client, db = authenticated_client, db_session
    book = models.Book(user_id=owner(db).id, title=title, author=author, year=2024)
    db.add(book)
    db.commit()
    save(client, "books", book)
    backup = client.get("/export/").json()
    switch_user(client, db)
    response = client.post("/import/", json=backup)
    assert response.status_code == 200
    assert response.json()["progress_created"] == 1


def test_continue_checkpoint_reads_stay_bounded_for_large_library(authenticated_client, db_session):
    client, db = authenticated_client, db_session
    user = owner(db)
    for i in range(100):
        db.add(models.Book(user_id=user.id, title=f"Book {i}"))
    db.commit()
    now = datetime.utcnow()
    for book in db.query(models.Book).all():
        db.add(models.ProgressCheckpoint(user_id=user.id, category="books", item_id=book.id,
                                        unit="page", position=book.id, revision=1, updated_at=now))
    db.commit()
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        response = client.get("/statistics/pulse/")
    finally:
        event.remove(db.bind, "before_cursor_execute", record)
    assert response.status_code == 200 and len(response.json()["continue_items"]) == 6
    assert len(statements) <= 15
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
