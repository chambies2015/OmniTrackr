"""Selected public collections become private copies only after confirmation."""
from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import Session

from app import auth, models
from app.database import Base
from app.routers import collections


INTRO = (
    "These are the stories I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)
COMPLETION = {"movies": "watched", "tv-shows": "watched", "anime": "watched",
              "video-games": "played", "music": "listened", "books": "read"}
METADATA = {
    "movies": {"director": "A Director", "year": 2024, "poster_url": "https://example.test/movie.png"},
    "tv-shows": {"year": 2023, "seasons": 2, "episodes": 16, "poster_url": "https://example.test/tv.png"},
    "anime": {"year": 2022, "seasons": 1, "episodes": 12, "poster_url": "https://example.test/anime.png"},
    "video-games": {"release_date": datetime(2021, 2, 3), "genres": "Adventure",
                    "cover_art_url": "https://example.test/game.png", "rawg_link": "https://example.test/game"},
    "music": {"artist": "An Artist", "year": 2020, "genre": "Ambient",
              "cover_art_url": "https://example.test/album.png"},
    "books": {"author": "An Author", "year": 2019, "genre": "Fiction",
              "cover_art_url": "https://example.test/book.png"},
}


class Elements(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.elements = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username})


@pytest.fixture
def shelf(db_session):
    author = models.User(username="collection_author", email="author@example.test", hashed_password="unused",
                         is_active=True, is_verified=True)
    reader = models.User(username="collection_reader", email="reader@example.test", hashed_password="unused",
                         is_active=True, is_verified=True)
    db_session.add_all([author, reader])
    db_session.flush()
    source = models.Collection(user_id=author.id, name="Stories for a quiet weekend", description=INTRO,
                               cover_url="https://example.test/collection.png", is_public=True,
                               moderation_status="approved")
    db_session.add(source)
    db_session.flush()
    media = {}
    entries = {}
    for position, (category, (model, _label)) in enumerate(collections.CATEGORIES.items()):
        item = model(user_id=author.id, title=f"Quiet {category}", rating=9, review="The curator's personal review",
                     review_public=True, **{COMPLETION[category]: True}, **METADATA[category])
        db_session.add(item)
        db_session.flush()
        entry = models.CollectionItem(collection_id=source.id, category=category, item_id=item.id,
                                      position=position, curator_note=f"Why this {category} fits the weekend.")
        db_session.add(entry)
        media[category] = item
        entries[category] = entry
    db_session.commit()
    return SimpleNamespace(author=author, reader=reader, source=source, media=media, entries=entries)


def preview(client, shelf):
    return client.get(f"/collections/public/{shelf.source.id}/save-preview")


def save(client, shelf, version, item_ids):
    return client.post(f"/collections/public/{shelf.source.id}/save", json={"version": version, "item_ids": item_ids})


def reader_counts(db, shelf):
    return (db.query(models.Collection).filter_by(user_id=shelf.reader.id).count(),
            tuple(db.query(model).filter_by(user_id=shelf.reader.id).count()
                  for model, _ in collections.CATEGORIES.values()),
            db.query(models.CollectionSaveReceipt).filter_by(user_id=shelf.reader.id).count())


def assert_private_response(response):
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-robots-tag"].startswith("noindex")


def test_preview_requires_authentication_and_never_creates_library_data(client, db_session, shelf):
    before = reader_counts(db_session, shelf)
    guest = preview(client, shelf)
    assert guest.status_code == 401
    assert_private_response(guest)
    unauthorized_save = save(client, shelf, "0" * 64, [shelf.entries["movies"].id])
    assert unauthorized_save.status_code == 401
    assert_private_response(unauthorized_save)
    sign_in(client, shelf.reader)
    response = preview(client, shelf)
    assert response.status_code == 200
    assert_private_response(response)
    payload = response.json()
    assert payload["collection_name"] == shelf.source.name
    assert len(payload["version"]) == 64 and int(payload["version"], 16) >= 0
    assert [row["id"] for row in payload["items"]] == [entry.id for entry in shelf.entries.values()]
    assert [(row["category"], row["category_label"], row["title"], row["existing"]) for row in payload["items"]] == [
        (category, label, shelf.media[category].title, False)
        for category, (_model, label) in collections.CATEGORIES.items()
    ]
    assert "personal review" not in response.text
    assert reader_counts(db_session, shelf) == before


def test_save_page_escapes_content_and_returns_to_exact_collection_after_auth(client, db_session, shelf):
    shelf.source.name = '\"><img src=x onerror=alert(1)> {{ITEMS}}'
    shelf.source.description = '<script>alert(1)</script> ' + INTRO
    shelf.media["movies"].title = '<img src=x onerror=alert(2)>'
    db_session.commit()
    before = reader_counts(db_session, shelf)
    response = client.get(f"/collections/public/{shelf.source.id}/save")
    assert response.status_code == 200
    assert_private_response(response)
    assert '<meta name="robots" content="noindex, follow">' in response.text
    assert '<img src=x' not in response.text and '<script>alert' not in response.text
    assert '&lt;img src=x' in response.text and '{{ITEMS}}' in response.text
    for prohibited in ("/static/ad-loader.js", "googlesyndication", "googletagmanager", "/static/analytics.js"):
        assert prohibited not in response.text
    links = [attrs["href"] for tag, attrs in Elements(response.text).elements if tag == "a" and "href" in attrs]
    signin = next(link for link in links if link.startswith("/?next="))
    assert parse_qs(urlsplit(signin).query) == {"next": [f"/collections/public/{shelf.source.id}/save"]}
    assert reader_counts(db_session, shelf) == before
    detail = client.get(f"/collections/public/{shelf.source.id}")
    assert f'href="/collections/public/{shelf.source.id}/save"' in detail.text


def test_mixed_media_save_copies_public_metadata_only_and_preserves_existing_library(client, db_session, shelf):
    existing = models.Book(user_id=shelf.reader.id, title="Quiet books", author="An Author", year=2019,
                           rating=3, read=True, review="My private opinion", review_public=False,
                           genre="My category", cover_art_url="https://example.test/my-cover.png")
    db_session.add(existing)
    db_session.commit()
    original = {column.name: getattr(existing, column.name) for column in models.Book.__table__.columns}
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    assert [row["existing"] for row in payload["items"]] == [False, False, False, False, False, True]
    # Deliberately reversed input: the copy still follows the curator's order.
    response = save(client, shelf, payload["version"], [row["id"] for row in reversed(payload["items"])])
    assert response.status_code == 200
    assert_private_response(response)
    result = response.json()
    assert result["created"] == 5 and result["reused"] == 1 and result["already_saved"] is False
    copied = db_session.get(models.Collection, result["collection_id"])
    assert copied.user_id == shelf.reader.id and copied.is_public is False
    assert copied.description == INTRO and copied.cover_url == shelf.source.cover_url
    assert copied.name != shelf.source.name
    assert len(copied.items) == 6
    for position, entry in enumerate(copied.items):
        assert entry.position == position
        assert entry.category == list(collections.CATEGORIES)[position]
        assert entry.curator_note == shelf.entries[entry.category].curator_note
        model = collections.CATEGORIES[entry.category][0]
        item = db_session.get(model, entry.item_id)
        assert item.user_id == shelf.reader.id
        if entry.category == "books":
            assert item.id == existing.id
        else:
            for field in collections.COPY_FIELDS[entry.category]:
                assert getattr(item, field) == getattr(shelf.media[entry.category], field)
            assert item.rating is None and item.review is None and item.review_public is False
            assert getattr(item, COMPLETION[entry.category]) is False
    db_session.refresh(existing)
    assert original == {field: getattr(existing, field) for field in original}
    assert reader_counts(db_session, shelf) == (1, (1, 1, 1, 1, 1, 1), 1)


def test_same_title_different_edition_is_not_reused(client, db_session, shelf):
    db_session.add(models.Book(user_id=shelf.reader.id, title="Quiet books", author="Different author", year=2019,
                               review="Do not touch this edition", read=True))
    db_session.commit()
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    assert next(row for row in payload["items"] if row["category"] == "books")["existing"] is False
    result = save(client, shelf, payload["version"], [shelf.entries["books"].id])
    assert result.status_code == 200 and result.json()["created"] == 1
    editions = db_session.query(models.Book).filter_by(user_id=shelf.reader.id).all()
    assert len(editions) == 2
    assert {book.author for book in editions} == {"An Author", "Different author"}


def test_same_edition_matches_spacing_and_case_without_rewriting_reader_data(client, db_session, shelf):
    existing = models.Book(user_id=shelf.reader.id, title="  QUIET BOOKS  ", author=" AN AUTHOR ", year=2019,
                           review="Keep my formatting and opinion", read=True)
    db_session.add(existing)
    db_session.commit()
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    assert next(row for row in payload["items"] if row["category"] == "books")["existing"] is True
    result = save(client, shelf, payload["version"], [shelf.entries["books"].id]).json()
    copied = db_session.get(models.Collection, result["collection_id"])
    assert copied.items[0].item_id == existing.id and result["reused"] == 1
    db_session.refresh(existing)
    assert (existing.title, existing.author, existing.review, existing.read) == (
        "  QUIET BOOKS  ", " AN AUTHOR ", "Keep my formatting and opinion", True,
    )


def test_duplicate_editions_in_source_share_one_private_library_record_and_membership(client, db_session, shelf):
    duplicate = models.Movie(user_id=shelf.author.id, title=shelf.media["movies"].title, **METADATA["movies"])
    db_session.add(duplicate)
    db_session.flush()
    entry = models.CollectionItem(collection_id=shelf.source.id, category="movies", item_id=duplicate.id,
                                  position=10, curator_note="A duplicate listing of the same edition")
    db_session.add(entry)
    db_session.commit()
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    selected = [shelf.entries["movies"].id, entry.id]
    response = save(client, shelf, payload["version"], selected)
    assert response.status_code == 200
    copied = db_session.get(models.Collection, response.json()["collection_id"])
    assert len(copied.items) == 1 and copied.items[0].curator_note == shelf.entries["movies"].curator_note
    assert db_session.query(models.Movie).filter_by(user_id=shelf.reader.id).count() == 1
    assert save(client, shelf, payload["version"], selected).json()["collection_id"] == copied.id


@pytest.mark.parametrize("bad_ids", [[], [0], [-1], [True], [False], [1.0], ["1"], [None], None, "1", [1] * 51])
def test_invalid_selection_types_and_bounds_make_no_writes(client, db_session, shelf, bad_ids):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    before = reader_counts(db_session, shelf)
    response = save(client, shelf, payload["version"], bad_ids)
    assert response.status_code == 422
    assert_private_response(response)
    assert reader_counts(db_session, shelf) == before


@pytest.mark.parametrize("path", ["/collections/public/not-an-id/save", "/collections/public/1/save-preview"])
def test_save_route_failures_remain_private_and_noindexed(client, path):
    response = client.get(path)
    assert response.status_code in {401, 422}
    assert_private_response(response)


@pytest.mark.parametrize("invalid", ["duplicate", "unknown", "other_collection"])
def test_invalid_selected_entries_make_no_writes(client, db_session, shelf, invalid):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    item_ids = [shelf.entries["movies"].id] * 2 if invalid == "duplicate" else [999999]
    if invalid == "other_collection":
        other = models.Collection(user_id=shelf.author.id, name="Other private source")
        db_session.add(other)
        db_session.flush()
        entry = models.CollectionItem(collection_id=other.id, category="movies", item_id=shelf.media["movies"].id)
        db_session.add(entry)
        db_session.commit()
        item_ids = [entry.id]
    before = reader_counts(db_session, shelf)
    response = save(client, shelf, payload["version"], item_ids)
    assert response.status_code == 422
    assert reader_counts(db_session, shelf) == before


@pytest.mark.parametrize("version", ["", "abc", "g" * 64, 42, None, "a" * 65])
def test_invalid_versions_make_no_writes(client, db_session, shelf, version):
    sign_in(client, shelf.reader)
    before = reader_counts(db_session, shelf)
    response = save(client, shelf, version, [shelf.entries["movies"].id])
    assert response.status_code == 422
    assert_private_response(response)
    assert reader_counts(db_session, shelf) == before


@pytest.mark.parametrize("change", ["private", "inactive", "rejected", "suspended", "short", "too_few", "deleted"])
def test_source_withdrawal_is_checked_again_before_save(client, db_session, shelf, change):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    if change == "private": shelf.source.is_public = False
    if change == "inactive": shelf.author.is_active = False
    if change == "rejected": shelf.source.moderation_status = "rejected"
    if change == "short": shelf.source.description = "No longer publishable."
    if change == "suspended":
        shelf.source.report_content_hash = collections._approval_content_hash(shelf.source, db_session)
        shelf.source.suspended_at = datetime.utcnow()
    if change == "too_few":
        for item in list(shelf.media.values())[:4]:
            db_session.delete(item)
    if change == "deleted": db_session.delete(shelf.source)
    db_session.commit()
    before = reader_counts(db_session, shelf)
    assert preview(client, shelf).status_code == 404
    result = save(client, shelf, payload["version"], [payload["items"][0]["id"]])
    assert result.status_code == 404
    assert_private_response(result)
    assert client.get(f"/collections/public/{shelf.source.id}/save").status_code == 404
    assert reader_counts(db_session, shelf) == before


@pytest.mark.parametrize("change", ["name", "description", "cover", "order", "note", "title", "director", "year",
                                   "author", "artist", "episodes", "seasons", "genre", "release_date", "rawg_link", "art"])
def test_changed_copy_metadata_requires_fresh_preview(client, db_session, shelf, change):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    if change == "name": shelf.source.name = "A revised collection"
    if change == "description": shelf.source.description += " Read these slowly."
    if change == "cover": shelf.source.cover_url = "https://example.test/revised.png"
    if change == "order": shelf.entries["movies"].position = 20
    if change == "note": shelf.entries["movies"].curator_note = "A different reason to choose this."
    if change == "title": shelf.media["movies"].title = "Another title"
    if change == "director": shelf.media["movies"].director = "Another director"
    if change == "year": shelf.media["movies"].year = 2025
    if change == "author": shelf.media["books"].author = "Another author"
    if change == "artist": shelf.media["music"].artist = "Another artist"
    if change == "episodes": shelf.media["anime"].episodes = 13
    if change == "seasons": shelf.media["tv-shows"].seasons = 3
    if change == "genre": shelf.media["music"].genre = "Jazz"
    if change == "release_date": shelf.media["video-games"].release_date = datetime(2022, 1, 1)
    if change == "rawg_link": shelf.media["video-games"].rawg_link = "https://example.test/new-game"
    if change == "art": shelf.media["books"].cover_art_url = "https://example.test/revised-book.png"
    db_session.commit()
    before = reader_counts(db_session, shelf)
    stale = save(client, shelf, payload["version"], [row["id"] for row in payload["items"]])
    assert stale.status_code == 409
    assert_private_response(stale)
    assert reader_counts(db_session, shelf) == before
    updated = preview(client, shelf).json()
    assert updated["version"] != payload["version"]
    assert save(client, shelf, updated["version"], [row["id"] for row in updated["items"]]).status_code == 200


def test_author_personal_progress_does_not_invalidate_preview_or_copy(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    source = shelf.media["movies"]
    source.rating = 1
    source.review = "A different personal opinion"
    source.review_public = False
    source.watched = False
    db_session.commit()
    assert preview(client, shelf).json()["version"] == payload["version"]
    result = save(client, shelf, payload["version"], [shelf.entries["movies"].id])
    assert result.status_code == 200


def test_repeat_save_reuses_same_copy_without_overwriting_reader_edits(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    selected = [row["id"] for row in payload["items"]][:3]
    first = save(client, shelf, payload["version"], selected).json()
    copied = db_session.get(models.Collection, first["collection_id"])
    copied.name = "My renamed collection"
    copied.description = "My personal introduction"
    copied.items[0].curator_note = "My own note"
    media = db_session.get(models.Movie, copied.items[0].item_id)
    media.rating, media.watched, media.review = 2, True, "My private note"
    db_session.commit()
    before = reader_counts(db_session, shelf)
    repeated = save(client, shelf, payload["version"], list(reversed(selected))).json()
    assert repeated["collection_id"] == copied.id and repeated["already_saved"] is True
    assert reader_counts(db_session, shelf) == before
    db_session.refresh(copied)
    db_session.refresh(media)
    assert copied.name == "My renamed collection" and copied.description == "My personal introduction"
    assert copied.items[0].curator_note == "My own note"
    assert (media.rating, media.watched, media.review) == (2, True, "My private note")


def test_new_selection_or_source_version_creates_distinct_explicit_private_copy(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    first_ids = [shelf.entries["movies"].id]
    first = save(client, shelf, payload["version"], first_ids).json()
    changed_selection = save(client, shelf, payload["version"], first_ids + [shelf.entries["books"].id]).json()
    assert changed_selection["collection_id"] != first["collection_id"]
    assert changed_selection["already_saved"] is False
    shelf.entries["movies"].curator_note = "A new public recommendation"
    db_session.commit()
    updated = preview(client, shelf).json()
    changed_version = save(client, shelf, updated["version"], first_ids).json()
    assert changed_version["collection_id"] not in {first["collection_id"], changed_selection["collection_id"]}
    assert reader_counts(db_session, shelf) == (3, (1, 0, 0, 0, 0, 1), 3)
    original = db_session.get(models.Collection, first["collection_id"])
    assert original.items[0].curator_note != shelf.entries["movies"].curator_note


def test_deleted_copy_can_be_saved_again_without_deleting_library_titles(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    selected = [shelf.entries["movies"].id]
    first = save(client, shelf, payload["version"], selected).json()
    assert client.delete(f"/collections/{first['collection_id']}").status_code == 204
    assert reader_counts(db_session, shelf) == (0, (1, 0, 0, 0, 0, 0), 0)
    second = save(client, shelf, payload["version"], selected).json()
    assert second["already_saved"] is False and second["created"] == 0 and second["reused"] == 1
    assert reader_counts(db_session, shelf) == (1, (1, 0, 0, 0, 0, 0), 1)


def test_source_deletion_does_not_delete_or_edit_the_private_copy(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    first = save(client, shelf, payload["version"], [row["id"] for row in payload["items"]]).json()
    copied = db_session.get(models.Collection, first["collection_id"])
    before = [(entry.category, entry.item_id, entry.curator_note) for entry in copied.items]
    db_session.delete(shelf.source)
    db_session.commit()
    db_session.expire_all()
    copied = db_session.get(models.Collection, first["collection_id"])
    assert copied is not None and copied.is_public is False
    assert [(entry.category, entry.item_id, entry.curator_note) for entry in copied.items] == before
    assert reader_counts(db_session, shelf) == (1, (1, 1, 1, 1, 1, 1), 1)


def test_receipts_are_scoped_to_the_saving_account(client, db_session, shelf):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    selected = [shelf.entries["movies"].id]
    first = save(client, shelf, payload["version"], selected).json()
    other = models.User(username="another_reader", email="another@example.test", hashed_password="unused",
                        is_active=True, is_verified=True)
    db_session.add(other)
    db_session.commit()
    sign_in(client, other)
    second = save(client, shelf, payload["version"], selected).json()
    assert second["collection_id"] != first["collection_id"] and second["already_saved"] is False
    assert db_session.get(models.Collection, second["collection_id"]).user_id == other.id


def test_legacy_copy_and_full_selection_share_retry_protection(client, db_session, shelf):
    sign_in(client, shelf.reader)
    legacy = client.post(f"/collections/public/{shelf.source.id}/copy")
    assert legacy.status_code == 201 and len(legacy.json()["items"]) == 6
    collection_id = legacy.json()["id"]
    repeated = client.post(f"/collections/public/{shelf.source.id}/copy")
    assert repeated.status_code == 201 and repeated.json()["id"] == collection_id
    payload = preview(client, shelf).json()
    result = save(client, shelf, payload["version"], [row["id"] for row in payload["items"]]).json()
    assert result["collection_id"] == collection_id and result["already_saved"] is True
    assert reader_counts(db_session, shelf) == (1, (1, 1, 1, 1, 1, 1), 1)


def test_interrupted_save_rolls_back_all_new_media_collection_and_receipt(client, db_session, shelf, monkeypatch):
    sign_in(client, shelf.reader)
    payload = preview(client, shelf).json()
    original = collections._copy_media_for_user
    calls = 0

    def fail_after_first_item(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic interrupted save")
        return original(*args, **kwargs)

    monkeypatch.setattr(collections, "_copy_media_for_user", fail_after_first_item)
    before = reader_counts(db_session, shelf)
    with pytest.raises(RuntimeError, match="Synthetic interrupted save"):
        save(client, shelf, payload["version"], [row["id"] for row in payload["items"]])
    assert reader_counts(db_session, shelf) == before
    monkeypatch.setattr(collections, "_copy_media_for_user", original)
    result = save(client, shelf, payload["version"], [row["id"] for row in payload["items"]])
    assert result.status_code == 200 and result.json()["already_saved"] is False


@pytest.mark.parametrize("delete_target", ["collection", "reader"])
def test_receipt_schema_upgrade_preserves_existing_data_and_foreign_key_deletion(delete_target):
    """Exercise the production create_all upgrade against a populated old schema."""
    isolated_engine = create_engine("sqlite:///:memory:")

    @event.listens_for(isolated_engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    receipt_table = models.CollectionSaveReceipt.__table__
    previous_tables = [table for table in Base.metadata.sorted_tables if table is not receipt_table]
    try:
        Base.metadata.create_all(isolated_engine, tables=previous_tables)
        assert receipt_table.name not in inspect(isolated_engine).get_table_names()
        with Session(isolated_engine) as db:
            author = models.User(username="existing_curator", email="old-curator@example.test",
                                 hashed_password="existing-hash", is_verified=True, is_active=True,
                                 movies_private=True)
            reader = models.User(username="existing_reader", email="old-reader@example.test",
                                 hashed_password="another-existing-hash", is_verified=True, is_active=True)
            db.add_all([author, reader])
            db.flush()
            source = models.Collection(user_id=author.id, name="Existing collection", description=INTRO,
                                       is_public=True, moderation_status="approved")
            db.add(source)
            db.flush()
            for position in range(3):
                movie = models.Movie(user_id=author.id, title=f"Existing film {position}", year=2024,
                                     rating=8, watched=True, review="An existing private review", review_public=False)
                db.add(movie)
                db.flush()
                db.add(models.CollectionItem(collection_id=source.id, category="movies", item_id=movie.id,
                                             position=position, curator_note=f"Existing public note {position}"))
            db.commit()
            author_id, reader_id, source_id = author.id, reader.id, source.id

            def snapshots():
                return {
                    table.name: [dict(row) for row in db.execute(select(table).order_by(table.c.id)).mappings()]
                    for table in (models.User.__table__, models.Movie.__table__,
                                  models.Collection.__table__, models.CollectionItem.__table__)
                }

            original = snapshots()
            db.commit()
            # Startup is repeatable and adds the new table without touching old rows.
            Base.metadata.create_all(isolated_engine)
            Base.metadata.create_all(isolated_engine)
            assert receipt_table.name in inspect(isolated_engine).get_table_names()
            assert snapshots() == original
            assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1

            saved, result = collections._save_public_selection(db, reader, source_id)
            saved_id = saved.id
            assert result["created"] == 3 and db.query(models.CollectionSaveReceipt).count() == 1
            db.delete(saved if delete_target == "collection" else reader)
            db.commit()
            assert db.get(models.Collection, saved_id) is None
            assert db.query(models.CollectionSaveReceipt).count() == 0
            if delete_target == "reader":
                assert db.get(models.User, reader_id) is None
                assert db.query(models.Movie).filter_by(user_id=reader_id).count() == 0
            else:
                assert db.get(models.User, reader_id) is not None
                assert db.query(models.Movie).filter_by(user_id=reader_id).count() == 3
            remaining = snapshots()
            assert next(row for row in remaining["users"] if row["id"] == author_id) == original["users"][0]
            assert [row for row in remaining["movies"] if row["user_id"] == author_id] == original["movies"]
            assert remaining["collections"] == original["collections"]
            assert remaining["collection_items"] == original["collection_items"]
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        isolated_engine.dispose()
