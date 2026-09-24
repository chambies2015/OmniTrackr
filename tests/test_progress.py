"""Private checkpoints, safe retries, deletion, and additive storage."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import crud, models
from app.database import Base
from app.progress import (
    ProgressWrite, get_checkpoint_map, save_progress, serialize_checkpoint,
    stage_import_checkpoint, validate_checkpoint,
)


def put_progress(client, item, category="tv-shows", **overrides):
    data = {"unit": "episode", "position": 4, "season": 2, "note": "Private reminder", "expected_revision": 0}
    data.update(overrides)
    return client.put(f"/progress/{category}/{item['id']}", json=data)


def clear_progress(client, item, revision, category="tv-shows"):
    return client.request("DELETE", f"/progress/{category}/{item['id']}", json={"expected_revision": revision})


def test_progress_round_trip_preserves_media_and_journal(authenticated_client, test_tv_show_data, db_session):
    client = authenticated_client
    item = client.post("/tv-shows/", json=test_tv_show_data).json()
    journal_before = db_session.query(models.ActivityEntry).count()
    before = client.get(f"/tv-shows/{item['id']}").json()
    initial = client.get(f"/progress/tv-shows/{item['id']}")
    assert initial.status_code == 200
    assert initial.headers["Cache-Control"] == "private, no-store"
    assert initial.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert initial.json() == {"category": "tv-shows", "item_id": item["id"], "title": item["title"], "revision": 0, "checkpoint": None}

    response = put_progress(client, item, note="  <script>literal private text</script>  ")
    assert response.status_code == 200
    checkpoint = response.json()["checkpoint"]
    assert checkpoint == {
        "unit": "episode", "position": 4, "season": 2,
        "note": "<script>literal private text</script>", "revision": 1,
        "updated_at": checkpoint["updated_at"],
    }
    assert checkpoint["updated_at"].endswith("Z")
    assert client.get(f"/progress/tv-shows/{item['id']}").json() == response.json()
    assert client.get(f"/tv-shows/{item['id']}").json() == before
    assert db_session.query(models.ActivityEntry).count() == journal_before
    assert "checkpoint" not in before and "progress" not in before


def test_progress_update_clear_and_tombstone(authenticated_client, test_tv_show_data, db_session):
    client = authenticated_client
    item = client.post("/tv-shows/", json=test_tv_show_data).json()
    assert put_progress(client, item).json()["revision"] == 1
    assert put_progress(client, item, expected_revision=1, position=5, season=0, note="   ").json()["checkpoint"]["note"] is None
    cleared = clear_progress(client, item, 2)
    assert cleared.status_code == 200
    assert cleared.json()["revision"] == 3
    assert cleared.json()["checkpoint"] is None
    assert db_session.query(models.ProgressCheckpoint).one().unit is None
    # An open editor from before clear cannot resurrect its old stopping point.
    assert put_progress(client, item, expected_revision=2, position=6).status_code == 409
    assert put_progress(client, item, expected_revision=3, position=6).json()["revision"] == 4
    assert clear_progress(client, item, 2).status_code == 409


def test_uncertain_retries_do_not_increment_revision_or_clobber_newer_changes(authenticated_client, test_tv_show_data):
    client = authenticated_client
    item = client.post("/tv-shows/", json=test_tv_show_data).json()
    first = put_progress(client, item)
    assert put_progress(client, item).json() == first.json()
    assert put_progress(client, item, expected_revision=1).json() == first.json()
    assert put_progress(client, item, expected_revision=0, position=5).status_code == 409
    assert put_progress(client, item, expected_revision=1, position=5).json()["revision"] == 2
    assert put_progress(client, item, expected_revision=0).status_code == 409
    cleared = clear_progress(client, item, 2)
    assert clear_progress(client, item, 2).json() == cleared.json()
    assert clear_progress(client, item, 3).json() == cleared.json()
    assert put_progress(client, item, expected_revision=0).status_code == 409


def test_clearing_empty_checkpoint_retains_safe_revision(authenticated_client, test_tv_show_data):
    client = authenticated_client
    item = client.post("/tv-shows/", json=test_tv_show_data).json()
    first = clear_progress(client, item, 0)
    assert first.status_code == 200 and first.json()["revision"] == 1
    assert clear_progress(client, item, 0).json() == first.json()
    assert put_progress(client, item).status_code == 409


def test_checkpoint_validation_rejects_coercion_and_unbounded_data(authenticated_client, test_tv_show_data):
    client = authenticated_client
    item = client.post("/tv-shows/", json=test_tv_show_data).json()
    for invalid in (
        {"position": 0}, {"position": -1}, {"position": 1000001},
        {"position": True}, {"position": "2"}, {"position": 2.5},
        {"season": -1}, {"season": 10001}, {"season": True}, {"season": "2"},
        {"note": "x" * 301}, {"note": 42}, {"expected_revision": True},
        {"expected_revision": -1}, {"expected_revision": "0"},
        {"expected_revision": 2147483647}, {"unit": "page"},
        {"unit": "minutes"}, {"user_id": 2}, {"updated_at": "2026-01-01"},
    ):
        assert put_progress(client, item, **invalid).status_code == 422, invalid
    assert client.get(f"/progress/tv-shows/{item['id']}").json()["revision"] == 0
    for invalid_id in (0, -1, 2147483648, "NaN", "1.1"):
        assert client.get(f"/progress/tv-shows/{invalid_id}").status_code == 422
    for category in ("movies", "music", "video-games", "custom-tabs"):
        assert client.get(f"/progress/{category}/{item['id']}").status_code == 422
    for body in ({}, {"expected_revision": "0"}, {"expected_revision": 0, "item_id": 1}):
        assert client.request("DELETE", f"/progress/tv-shows/{item['id']}", json=body).status_code == 422


def test_books_use_pages_or_chapters_and_shows_allow_unknown_season(authenticated_client, test_book_data, test_anime_data):
    client = authenticated_client
    book = client.post("/books/", json=test_book_data).json()
    for unit in ("page", "chapter"):
        response = put_progress(client, book, "books", unit=unit, season=None, expected_revision=0 if unit == "page" else 1)
        assert response.status_code == 200
    assert put_progress(client, book, "books", unit="episode", season=None, expected_revision=2).status_code == 422
    assert put_progress(client, book, "books", unit="page", season=0, expected_revision=2).status_code == 422
    anime = client.post("/anime/", json=test_anime_data).json()
    response = put_progress(client, anime, "anime", season=None)
    assert response.status_code == 200 and response.json()["checkpoint"]["season"] is None


def test_checkpoint_authentication_and_ownership(client, authenticated_client, db_session, test_tv_show_data):
    client = authenticated_client
    owner = db_session.query(models.User).one()
    foreign = models.User(username="other-progress", email="other-progress@example.test", hashed_password="not-used", is_verified=True)
    db_session.add(foreign)
    db_session.flush()
    media = models.TVShow(user_id=foreign.id, title="Other private title")
    db_session.add(media)
    db_session.commit()
    item = {"id": media.id}
    assert client.get(f"/progress/tv-shows/{media.id}").status_code == 404
    assert put_progress(client, item).status_code == 404
    assert clear_progress(client, item, 0).status_code == 404
    assert client.get("/progress/books/999999").status_code == 404
    assert get_checkpoint_map(db_session, owner.id) == {}
    client.headers.clear()
    client.cookies.clear()
    assert client.get(f"/progress/tv-shows/{media.id}").status_code == 401
    assert put_progress(client, item).status_code == 401
    assert clear_progress(client, item, 0).status_code == 401


@pytest.mark.parametrize("category,fixture_name", [("tv-shows", "test_tv_show_data"), ("anime", "test_anime_data"), ("books", "test_book_data")])
def test_delete_media_removes_checkpoint_and_reused_id_starts_clean(authenticated_client, db_session, request, category, fixture_name):
    client = authenticated_client
    item = client.post(f"/{category}/", json=request.getfixturevalue(fixture_name)).json()
    unit = "page" if category == "books" else "episode"
    assert put_progress(client, item, category, unit=unit, season=None).status_code == 200
    assert client.delete(f"/{category}/{item['id']}").status_code == 200
    assert db_session.query(models.ProgressCheckpoint).count() == 0
    assert client.get(f"/progress/{category}/{item['id']}").status_code == 404
    replacement = client.post(f"/{category}/", json=request.getfixturevalue(fixture_name)).json()
    assert client.get(f"/progress/{category}/{replacement['id']}").json()["checkpoint"] is None


def test_private_batch_helper_and_backup_restore_preserve_current_choices(authenticated_client, db_session, test_book_data):
    client = authenticated_client
    user = db_session.query(models.User).one()
    item = client.post("/books/", json=test_book_data).json()
    data = {"unit": "page", "position": 125, "note": "Bookmark"}
    assert stage_import_checkpoint(db_session, user.id, "books", item["id"], data)
    db_session.commit()
    mapping = get_checkpoint_map(db_session, user.id)
    assert set(mapping) == {("books", item["id"])}
    assert serialize_checkpoint(mapping[("books", item["id"])])["position"] == 125
    assert get_checkpoint_map(db_session, user.id + 1) == {}
    assert not stage_import_checkpoint(db_session, user.id, "books", item["id"], {**data, "position": 10})
    db_session.commit()
    assert clear_progress(client, item, 1, "books").json()["revision"] == 2
    assert not stage_import_checkpoint(db_session, user.id, "books", item["id"], data)
    db_session.commit()
    assert get_checkpoint_map(db_session, user.id) == {}
    assert client.get(f"/progress/books/{item['id']}").json()["checkpoint"] is None
    with pytest.raises(ValueError):
        validate_checkpoint("books", {**data, "revision": 9000})
    with pytest.raises(ValueError):
        validate_checkpoint("tv-shows", data)


def test_user_deletion_cascades_checkpoint(authenticated_client, db_session, test_tv_show_data):
    item = authenticated_client.post("/tv-shows/", json=test_tv_show_data).json()
    assert put_progress(authenticated_client, item).status_code == 200
    db_session.delete(db_session.query(models.User).one())
    db_session.commit()
    assert db_session.query(models.ProgressCheckpoint).count() == 0


def test_friend_media_does_not_expose_stopping_point(authenticated_client, db_session):
    user = db_session.query(models.User).one()
    friend = models.User(username="checkpoint-friend", email="checkpoint-friend@example.test", hashed_password="unused")
    db_session.add(friend)
    db_session.flush()
    media = models.TVShow(user_id=friend.id, title="Shared show")
    db_session.add(media)
    db_session.flush()
    db_session.add(models.Friendship(user1_id=user.id, user2_id=friend.id))
    db_session.add(models.ProgressCheckpoint(user_id=friend.id, category="tv-shows", item_id=media.id,
        unit="episode", position=24, note="Private secret reminder", revision=1))
    db_session.commit()
    response = authenticated_client.get(f"/friends/{friend.id}/tv-shows")
    assert response.status_code == 200
    assert response.json()["tv_shows"][0]["title"] == "Shared show"
    assert "checkpoint" not in response.text and "Private secret reminder" not in response.text
    assert authenticated_client.get(f"/progress/tv-shows/{media.id}").status_code == 404


def test_failed_commit_rolls_back_checkpoint(authenticated_client, db_session, test_tv_show_data, monkeypatch):
    item = authenticated_client.post("/tv-shows/", json=test_tv_show_data).json()
    user_id = db_session.query(models.User.id).scalar()

    def fail_commit():
        raise RuntimeError("Simulated disconnected commit")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Simulated"):
        save_progress(db_session, user_id, "tv-shows", item["id"],
            ProgressWrite(unit="episode", position=4, expected_revision=0))
    assert db_session.query(models.ProgressCheckpoint).count() == 0


@pytest.mark.parametrize("same_payload", [False, True])
def test_concurrent_writes_serialize_without_lost_updates(tmp_path, same_payload):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress-concurrency.sqlite'}", connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user = models.User(username="concurrent", email="concurrent@example.test", hashed_password="unused")
        db.add(user)
        db.flush()
        media = models.TVShow(user_id=user.id, title="Concurrent series")
        db.add(media)
        db.commit()
        user_id, item_id = user.id, media.id

    def write(position):
        with factory() as db:
            try:
                result = save_progress(db, user_id, "tv-shows", item_id, ProgressWrite(unit="episode", position=position, expected_revision=0))
                return 200, result
            except HTTPException as exc:
                return exc.status_code, None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, [4, 4 if same_payload else 5]))
        assert sorted(status for status, _ in results) == ([200, 200] if same_payload else [200, 409])
        with factory() as db:
            checkpoint = db.query(models.ProgressCheckpoint).one()
            assert checkpoint.revision == 1
            assert checkpoint.position in (4, 5)
    finally:
        engine.dispose()


def test_concurrent_media_deletion_leaves_no_orphan_checkpoint(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress-delete.sqlite'}", connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user = models.User(username="deleting", email="deleting@example.test", hashed_password="unused")
        db.add(user)
        db.flush()
        media = models.Book(user_id=user.id, title="Deleting book")
        db.add(media)
        db.commit()
        user_id, item_id = user.id, media.id
    barrier = Barrier(2)

    def write():
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                save_progress(db, user_id, "books", item_id, ProgressWrite(unit="page", position=50, expected_revision=0))
                return 200
            except HTTPException as exc:
                return exc.status_code

    def delete():
        with factory() as db:
            barrier.wait(timeout=10)
            assert crud.delete_book(db, user_id, item_id) is not None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            written, deleted = pool.submit(write), pool.submit(delete)
            assert written.result() in (200, 404)
            deleted.result()
        with factory() as db:
            assert db.query(models.Book).count() == 0
            assert db.query(models.ProgressCheckpoint).count() == 0
    finally:
        engine.dispose()


def test_additive_table_creation_preserves_existing_media(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'progress-migration.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user = models.User(username="legacy", email="legacy@example.test", hashed_password="unused")
        db.add(user)
        db.flush()
        db.add(models.Book(user_id=user.id, title="Existing book", read=True, rating=8.5, review="Keep this"))
        db.commit()
    models.ProgressCheckpoint.__table__.drop(engine)
    def schema_columns():
        return [{**column, "type": str(column["type"])} for column in inspect(engine).get_columns("books")]

    before_columns = schema_columns()
    Base.metadata.create_all(engine)
    assert schema_columns() == before_columns
    with factory() as db:
        book = db.query(models.Book).one()
        assert (book.title, book.read, book.rating, book.review) == ("Existing book", True, 8.5, "Keep this")
        assert db.query(models.ProgressCheckpoint).count() == 0
    engine.dispose()
