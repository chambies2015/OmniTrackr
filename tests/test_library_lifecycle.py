"""Deleted library IDs must not turn existing references into unrelated new titles."""
from datetime import datetime

import pytest

from app import models


MEDIA = [
    ("movies", models.Movie, "watched", "movie"),
    ("tv-shows", models.TVShow, "watched", "tv_show"),
    ("anime", models.Anime, "watched", "anime"),
    ("video-games", models.VideoGame, "played", "video_game"),
    ("music", models.Music, "listened", "music"),
    ("books", models.Book, "read", "book"),
]


@pytest.mark.parametrize("category,model,done,review_category", MEDIA)
def test_delete_cleans_references_but_preserves_history(authenticated_client, db_session, category, model, done, review_category):
    client, db = authenticated_client, db_session
    user = db.query(models.User).filter_by(username="testuser").one()
    other = models.User(username="other", email="other@example.invalid", hashed_password="unused", is_verified=True)
    db.add(other)
    db.commit()
    unaffected = model(user_id=other.id, title="Unaffected", **{done: True})
    db.add(unaffected)
    db.commit()
    original = model(user_id=user.id, title="Original", rating=8, **{done: True})
    db.add(original)
    db.commit()
    original_id = original.id
    collection = models.Collection(user_id=user.id, name="Shelf")
    other_collection = models.Collection(user_id=other.id, name="Other shelf")
    db.add_all([collection, other_collection])
    db.flush()
    moment = models.CompletionMoment(user_id=user.id, category=category, item_id=original_id,
                                    title=original.title, rating=8, takeaway="Keep this reflection", favorite=True)
    activity = models.ActivityEntry(user_id=user.id, category=category, item_id=original_id,
                                    title=original.title, action="completed", note="Keep this journal entry")
    state = models.PublicReviewState(user_id=user.id, category=review_category, item_id=original_id, content_hash="old", report_count=1)
    db.add_all([moment, activity, state,
                models.NextUpItem(user_id=user.id, category=category, item_id=original_id, position=0),
                models.NextUpItem(user_id=other.id, category=category, item_id=unaffected.id, position=0),
                models.CollectionItem(collection_id=collection.id, category=category, item_id=original_id, position=0),
                models.CollectionItem(collection_id=other_collection.id, category=category, item_id=unaffected.id, position=0),
                models.ReviewReaction(category=review_category, item_id=original_id, visitor_hash="old-reader"),
                models.ReviewReaction(category=review_category, item_id=unaffected.id, visitor_hash="other-reader")])
    db.flush()
    db.add(models.PublicReviewReport(state_id=state.id, visitor_hash="old-reporter", reason="spam"))
    if category in {"tv-shows", "anime", "books"}:
        db.add(models.ProgressCheckpoint(user_id=user.id, category=category, item_id=original_id,
                                         unit="page" if category == "books" else "episode", position=5, revision=1))
    db.commit()
    moment_id, activity_id = moment.id, activity.id
    request = models.RecommendationRequest(owner_id=user.id, public_token="original-postcard", prompt="Suggest something", allowed_categories='["movies"]', expires_at=datetime(2099, 1, 1))
    db.add(request)
    db.flush()
    suggestion = models.RecommendationSubmission(request_id=request.id, guest_name="Reader", category=category,
                                                 title="Original", reason="Suggested earlier", status="accepted", accepted_item_id=original_id)
    db.add(suggestion)
    db.commit()
    suggestion_id = suggestion.id
    response = client.delete(f"/{category}/{original_id}")
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.query(models.NextUpItem).filter_by(user_id=user.id).count() == 0
    assert db.query(models.CollectionItem).filter_by(collection_id=collection.id).count() == 0
    assert db.query(models.ProgressCheckpoint).filter_by(user_id=user.id).count() == 0
    assert db.query(models.ReviewReaction).filter_by(category=review_category, item_id=original_id).count() == 0
    assert db.query(models.PublicReviewState).filter_by(category=review_category, item_id=original_id).count() == 0
    assert db.query(models.PublicReviewReport).count() == 0
    assert db.query(models.NextUpItem).filter_by(user_id=other.id).count() == 1
    assert db.query(models.CollectionItem).filter_by(collection_id=other_collection.id).count() == 1
    assert db.query(models.ReviewReaction).filter_by(item_id=unaffected.id, category=review_category).count() == 1
    detached_suggestion = db.get(models.RecommendationSubmission, suggestion_id)
    assert detached_suggestion.status == "accepted" and detached_suggestion.accepted_item_id is None
    detached = db.get(models.CompletionMoment, moment_id)
    assert detached.item_id == -moment_id
    assert detached.title == "Original" and detached.takeaway == "Keep this reflection" and detached.favorite
    journal = db.get(models.ActivityEntry, activity_id)
    assert journal.item_id is None and journal.note == "Keep this journal entry"

    # Existing SQLite tables deliberately reuse the removed highest ID here.
    replacement = model(user_id=user.id, title="Replacement", **{done: True})
    db.add(replacement)
    db.commit()
    assert replacement.id == original_id
    assert client.get("/next-up/").json() == []
    assert client.post(f"/completion-moments/{moment_id}/review", json={"review": "Must not attach to replacement", "public": False}).status_code == 404
    assert db.get(model, replacement.id).review is None
    replay = client.get("/completion-moments/replay/")
    assert replay.status_code == 200
    assert replay.json()["highlights"][0]["title"] == "Original"
    fresh = client.post("/completion-moments/", json={"category": category, "item_id": replacement.id})
    assert fresh.status_code == 200 and fresh.json()["id"] != moment_id
    # Deleting another title retains a different tombstone rather than colliding.
    fresh_id = fresh.json()["id"]
    assert client.delete(f"/{category}/{replacement.id}").status_code == 200
    assert db.get(models.CompletionMoment, fresh_id).item_id == -fresh_id
    assert db.query(models.CompletionMoment).filter_by(user_id=user.id).count() == 2


@pytest.mark.parametrize("kind", ["next_up", "helpful", "report"])
def test_deletion_serializes_with_reference_writes(tmp_path, monkeypatch, kind):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from fastapi import Request
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import crud, schemas
    from app.database import Base
    from app.routers import next_up, reviews

    engine = create_engine(f"sqlite:///{tmp_path / 'reference-race.db'}", connect_args={"check_same_thread": False, "timeout": 5})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    review = (
        "The Matrix still feels sharp because every action scene is built around an idea about control and choice. "
        "The lobby shootout is pure style, but the quieter scenes on the ship give the story its weight. Some of the "
        "philosophy is spelled out a little too neatly, yet the final act earns its confidence and the effects hold up."
    )
    with factory() as db:
        user = models.User(username="race", email="race@example.invalid", hashed_password="unused", is_verified=True, reviews_public=True)
        db.add(user)
        db.flush()
        item = models.Movie(user_id=user.id, title="Race", director="Creator", year=2020, review=review, review_public=True)
        db.add(item)
        db.commit()
        user_id, item_id = user.id, item.id
    observed = threading.Event()
    deleted = threading.Event()
    if kind == "next_up":
        original = next_up._referenced_item
        def observe(*args, **kwargs):
            result = original(*args, **kwargs)
            if not observed.is_set():
                observed.set()
                deleted.wait(timeout=0.5)
            return result
        monkeypatch.setattr(next_up, "_referenced_item", observe)
    else:
        original = reviews.evaluate_public_review
        def observe(*args, **kwargs):
            result = original(*args, **kwargs)
            if not observed.is_set():
                observed.set()
                deleted.wait(timeout=0.5)
            return result
        monkeypatch.setattr(reviews, "evaluate_public_review", observe)

    def write():
        with factory() as db:
            if kind == "next_up":
                return asyncio.run(next_up.add_next_up(schemas.NextUpItemCreate(category="movies", item_id=item_id), SimpleNamespace(id=user_id), db))
            request = Request({"type": "http", "headers": [], "client": ("testclient", 1234), "path": "/"})
            if kind == "helpful":
                return asyncio.run(reviews.mark_review_helpful("movie", item_id, request, db))
            return asyncio.run(reviews.report_public_review("movie", item_id, schemas.PublicReviewReportCreate(reason="spam"), request, db))

    def delete():
        with factory() as db:
            result = crud.delete_movie(db, user_id, item_id)
            deleted.set()
            return result is not None

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            writing = workers.submit(write)
            assert observed.wait(timeout=5)
            removing = workers.submit(delete)
            writing.result(timeout=10)
            assert removing.result(timeout=10)
        with factory() as db:
            assert db.query(models.Movie).count() == 0
            assert db.query(models.NextUpItem).count() == 0
            assert db.query(models.ReviewReaction).count() == 0
            assert db.query(models.PublicReviewState).count() == 0
            assert db.query(models.PublicReviewReport).count() == 0
    finally:
        engine.dispose()
