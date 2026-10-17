"""New title writers share the owner transaction used by audited media deletion."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import crud, digest, models, schemas
from app.database import Base
from app.routers import completion_moments, titles
from tests.test_title_pages import LONG_REVIEW


@pytest.fixture
def title_store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'title-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        owner = models.User(username="writer", email="writer@example.invalid", hashed_password="unused", is_verified=True)
        source_owner = models.User(username="source", email="source@example.invalid", hashed_password="unused", is_verified=True)
        db.add_all([owner, source_owner])
        db.flush()
        db.add(models.Movie(user_id=source_owner.id, title="Interstellar", director="Nolan", year=2014))
        db.commit()
        user = SimpleNamespace(id=owner.id, username=owner.username)
    yield engine, factory, user
    engine.dispose()


def request():
    return Request({"type": "http", "headers": [], "client": ("testclient", 1234), "path": "/"})


@pytest.mark.parametrize("writer", ["add", "guest", "review"])
def test_title_writers_serialize_same_owner_checks(title_store, writer):
    engine, factory, user = title_store
    if writer == "review":
        with factory() as db:
            db.add(models.Movie(user_id=user.id, title="Interstellar", director="Nolan", year=2014, review="Loaded review"))
            db.commit()
    first_checked, second_done = threading.Event(), threading.Event()

    def pause_first_owned_check(connection, cursor, statement, parameters, context, executemany):
        if "lower(trim(movies.title))" in statement and not first_checked.is_set():
            first_checked.set()
            second_done.wait(timeout=0.5)

    event.listen(engine, "after_cursor_execute", pause_first_owned_check)

    def write(number):
        with factory() as db:
            try:
                if writer == "review":
                    result = titles.save_title_review(
                        "movie", "interstellar-2014",
                        titles.TitleReview(review=f"Review from writer {number}", public=False, expected_review="Loaded review"),
                        request(), Response(), user, db,
                    )
                elif writer == "guest":
                    result = titles.import_guest_list(
                        titles.GuestListImport(items=[{"kind": "movie", "slug": "interstellar-2014"}]),
                        request(), Response(), user, db,
                    )
                else:
                    result = titles.add_title("movie", "interstellar-2014", Response(), user, db)
                return 200, result
            except HTTPException as exc:
                return exc.status_code, None
            finally:
                if number == 2:
                    second_done.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(write, 1)
            assert first_checked.wait(timeout=5)
            second = workers.submit(write, 2)
            outcomes = [first.result(timeout=10), second.result(timeout=10)]
        with factory() as db:
            mine = db.query(models.Movie).filter_by(user_id=user.id).all()
            assert len(mine) == 1
            if writer == "review":
                assert sorted(code for code, _ in outcomes) == [200, 409]
                assert mine[0].review == "Review from writer 1"
            elif writer == "add":
                assert sorted(result["state"] for _, result in outcomes) == ["created", "existing"]
            else:
                assert sum(len(result["added"]) for _, result in outcomes) == 1
                assert sum(len(result["existing"]) for _, result in outcomes) == 1
    finally:
        event.remove(engine, "after_cursor_execute", pause_first_owned_check)


@pytest.mark.parametrize("writer", ["add", "review", "completion"])
def test_title_writer_response_survives_deletion_immediately_after_commit(title_store, monkeypatch, writer):
    _, factory, user = title_store
    with factory() as db:
        movie = models.Movie(user_id=user.id, title="Interstellar", director="Nolan", year=2014, watched=True)
        db.add(movie)
        db.flush()
        moment = models.CompletionMoment(user_id=user.id, category="movies", item_id=movie.id, title=movie.title)
        db.add(moment)
        db.commit()
        item_id, moment_id = movie.id, moment.id
    with factory() as db:
        commit = db.commit

        def commit_then_delete():
            commit()
            with factory() as deleting:
                assert crud.delete_movie(deleting, user.id, item_id) is not None

        monkeypatch.setattr(db, "commit", commit_then_delete)
        if writer == "add":
            result = titles.add_title("movie", "interstellar-2014", Response(), user, db)
            assert result == {"state": "existing", "title": "Interstellar", "category": "movies"}
        elif writer == "review":
            result = titles.save_title_review(
                "movie", "interstellar-2014", titles.TitleReview(review=LONG_REVIEW), request(), Response(), user, db,
            )
            assert result["review_url"] == f"/reviews/{item_id}?category=movie"
        else:
            result = asyncio.run(completion_moments.save_completion_review(
                moment_id, schemas.CompletionReview(review=LONG_REVIEW, public=True), user, db,
            ))
            assert result["review_url"] == f"/reviews/{item_id}?category=movie"
            assert result["title_url"] == "/titles/movie/interstellar-2014"
    with factory() as db:
        assert db.get(models.Movie, item_id) is None
        assert db.get(models.CompletionMoment, moment_id).item_id == -moment_id


def test_social_digest_does_not_attach_deleted_finish_to_reused_library_id(title_store):
    _, factory, user = title_store
    with factory() as db:
        movie = models.Movie(user_id=user.id, title="Interstellar", director="Nolan", year=2014, watched=True)
        db.add(movie)
        db.flush()
        item_id = movie.id
        moment = models.CompletionMoment(user_id=user.id, category="movies", item_id=item_id, title=movie.title)
        db.add(moment)
        db.commit()
        assert digest.recent_finish(db, user.id, datetime.utcnow())["title"] == "Interstellar"
        assert crud.delete_movie(db, user.id, item_id) is not None
        replacement = models.Movie(user_id=user.id, title="Replacement", director="Other", year=2026)
        db.add(replacement)
        db.commit()
        assert replacement.id == item_id
        assert digest.recent_finish(db, user.id, datetime.utcnow()) is None
