"""Checkpoints remain private across public discovery, copies, and backup restores."""
import json
from types import SimpleNamespace

import pytest

from app import auth, models
from app.progress import CATEGORIES, ProgressWrite, save_progress


REVIEW = (
    "This story uses patient pacing to support the lead performance instead of simply slowing the action down. "
    "The middle section repeats one conflict, but the final act rewards that setup with a credible emotional turn. "
    "I would recommend it to viewers who enjoy quiet character work, careful sound design, and endings that value "
    "resolution over surprise. The setting feels lived in, and the conversations reward close attention."
)
INTRO = (
    "These are the stories I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)
REVIEW_CATEGORY = {"tv-shows": "tv_show", "anime": "anime", "books": "book"}
PRIVATE_NOTE = "CHECKPOINT PRIVATE SENTINEL"


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username})


def assert_no_checkpoint(value):
    if isinstance(value, dict):
        assert not ({"progress", "checkpoint", "progress_checkpoints"} & set(value))
        for nested in value.values():
            assert_no_checkpoint(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_checkpoint(nested)
    elif isinstance(value, str):
        assert PRIVATE_NOTE not in value


@pytest.fixture
def shared_progress(db_session):
    author = models.User(username="progress-author", email="progress-author@example.test", hashed_password="unused",
                         is_active=True, is_verified=True, reviews_public=True)
    reader = models.User(username="progress-reader", email="progress-reader@example.test", hashed_password="unused",
                         is_active=True, is_verified=True)
    db_session.add_all([author, reader])
    db_session.flush()
    collection = models.Collection(user_id=author.id, name="Stories to pause and return to", description=INTRO,
                                   is_public=True, moderation_status="approved")
    db_session.add(collection)
    db_session.flush()
    items = {}
    for index, (category, model) in enumerate(CATEGORIES.items()):
        personal = {"read": False, "author": "Élodie Автор"} if category == "books" else {"watched": False, "seasons": 4, "episodes": 40}
        item = model(user_id=author.id, title=f"Épisode История {category}", year=2020 + index,
                     rating=8, review=REVIEW, review_public=True, **personal)
        db_session.add(item)
        db_session.flush()
        db_session.add(models.CollectionItem(collection_id=collection.id, category=category, item_id=item.id,
                                             position=index, curator_note=f"A thoughtful {category} choice."))
        items[category] = item
    db_session.commit()
    for category, item in items.items():
        save_progress(db_session, author.id, category, item.id, ProgressWrite(
            unit="chapter" if category == "books" else "episode", position=17,
            season=None if category == "books" else 0, note=f"{PRIVATE_NOTE} {category}", expected_revision=0,
        ))
    return SimpleNamespace(author=author, reader=reader, collection=collection, items=items)


@pytest.mark.parametrize("category", ["tv-shows", "anime", "books"])
def test_public_review_and_saved_title_exclude_private_progress(client, db_session, shared_progress, category):
    source = shared_progress.items[category]
    review_category = REVIEW_CATEGORY[category]
    responses = [
        client.get("/api/public/reviews", params={"category": review_category}),
        client.get("/api/public/review-feed", params={"category": review_category}),
        client.get(f"/api/public/reviews/{source.id}", params={"category": review_category}),
    ]
    for response in responses:
        assert response.status_code == 200
        assert_no_checkpoint(response.json())
        assert source.title in response.text
    public_page = client.get(f"/reviews/{source.id}", params={"category": review_category})
    assert public_page.status_code == 200
    assert PRIVATE_NOTE not in public_page.text
    sign_in(client, shared_progress.reader)
    preview = client.get(f"/api/public/reviews/{source.id}/save-preview", params={"category": review_category})
    assert preview.status_code == 200
    assert_no_checkpoint(preview.json())
    saved = client.post(f"/api/public/reviews/{source.id}/save", params={"category": review_category},
                        json={"version": preview.json()["version"]})
    assert saved.status_code == 200
    assert saved.json()["created"] is True
    assert_no_checkpoint(saved.json())
    copy = client.get(f"/progress/{category}/{saved.json()['item_id']}")
    assert copy.status_code == 200 and copy.json()["checkpoint"] is None
    assert db_session.query(models.ProgressCheckpoint).filter_by(user_id=shared_progress.reader.id).count() == 0
    assert db_session.query(models.ProgressCheckpoint).filter_by(user_id=shared_progress.author.id).count() == 3


def test_public_collection_copy_omits_author_progress_and_preserves_reader_progress(client, db_session, shared_progress):
    shelf = shared_progress
    for path in ("/collections/explore", f"/collections/public/{shelf.collection.id}", f"/collections/public/{shelf.collection.id}/save"):
        response = client.get(path)
        assert response.status_code == 200
        assert PRIVATE_NOTE not in response.text
    source_book = shelf.items["books"]
    existing = models.Book(user_id=shelf.reader.id, title=source_book.title, author=source_book.author,
                           year=source_book.year, read=True, rating=2, review="Reader's own opinion")
    db_session.add(existing)
    db_session.commit()
    saved_before = save_progress(db_session, shelf.reader.id, "books", existing.id,
        ProgressWrite(unit="page", position=203, note="Reader's own private bookmark", expected_revision=0))
    sign_in(client, shelf.reader)
    preview = client.get(f"/collections/public/{shelf.collection.id}/save-preview")
    assert preview.status_code == 200
    assert_no_checkpoint(preview.json())
    saved = client.post(f"/collections/public/{shelf.collection.id}/save", json={
        "version": preview.json()["version"], "item_ids": [item["id"] for item in preview.json()["items"]],
    })
    assert saved.status_code == 200
    assert saved.json()["created"] == 2 and saved.json()["reused"] == 1
    assert_no_checkpoint(saved.json())
    copied = db_session.get(models.Collection, saved.json()["collection_id"])
    assert not copied.is_public and copied.user_id == shelf.reader.id
    for item in copied.items:
        progress = client.get(f"/progress/{item.category}/{item.item_id}").json()
        if item.category == "books":
            assert item.item_id == existing.id and progress == saved_before
        else:
            assert progress["revision"] == 0 and progress["checkpoint"] is None
    assert db_session.query(models.ProgressCheckpoint).filter_by(user_id=shelf.author.id).count() == 3
    assert db_session.query(models.ProgressCheckpoint).filter_by(user_id=shelf.reader.id).count() == 1


@pytest.mark.parametrize("use_file", [False, True])
def test_backup_round_trip_restores_all_supported_media_privately(client, db_session, shared_progress, use_file):
    shelf = shared_progress
    sign_in(client, shelf.author)
    exported = client.get("/export/")
    assert exported.status_code == 200 and exported.headers["Cache-Control"] == "private, no-store"
    backup = exported.json()
    assert len(backup["progress_checkpoints"]) == 3
    original = {row["category"]: row["checkpoint"] for row in backup["progress_checkpoints"]}
    assert set(original) == set(CATEGORIES)
    for row in backup["progress_checkpoints"]:
        assert "item_id" not in row and "user_id" not in row and "revision" not in row["checkpoint"]
    sign_in(client, shelf.reader)
    if use_file:
        restored = client.post("/import/file/", files={"file": ("backup.json", json.dumps(backup).encode(), "application/json")})
    else:
        restored = client.post("/import/", json=backup)
    assert restored.status_code == 200
    assert restored.json()["progress_created"] == 3 and restored.json()["progress_skipped"] == 0
    assert restored.json()["errors"] == []
    for category, model in CATEGORIES.items():
        media = db_session.query(model).filter_by(user_id=shelf.reader.id).one()
        assert media.id != shelf.items[category].id
        assert media.title == shelf.items[category].title
        progress = client.get(f"/progress/{category}/{media.id}")
        assert progress.status_code == 200
        assert {key: progress.json()["checkpoint"][key] for key in original[category]} == original[category]
        assert progress.json()["revision"] == 1
    assert not db_session.query(models.Collection).filter_by(user_id=shelf.reader.id).one().is_public
    repeated = client.post("/import/", json=backup)
    assert repeated.status_code == 200
    assert repeated.json()["progress_created"] == 0 and repeated.json()["progress_skipped"] == 3
