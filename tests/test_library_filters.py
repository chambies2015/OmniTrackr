"""Library filters apply to owned records before counting and pagination."""
import pytest

from app import models
from app.routers.library import CATEGORIES


def read_page(client, category, **params):
    response = client.get(f"/library/page/{category}", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_completion_and_unrated_filters_cover_each_category(authenticated_client, db_session, category):
    owner = db_session.query(models.User).filter_by(username="testuser").one()
    other = models.User(username="other", email="other@example.test", hashed_password="unused")
    db_session.add(other)
    db_session.flush()
    model, _, _, done, _ = CATEGORIES[category]
    rows = [
        model(user_id=owner.id, title="Unfinished unrated", rating=None, **{done: False}),
        model(user_id=owner.id, title="Unfinished zero", rating=0, **{done: False}),
        model(user_id=owner.id, title="Finished unrated", rating=None, **{done: True}),
        model(user_id=owner.id, title="Finished rated", rating=8, **{done: True}),
        model(user_id=owner.id, title="Legacy null completion", rating=None, **{done: False}),
    ]
    db_session.add_all(rows)
    db_session.add(model(user_id=other.id, title="Other user's unrated", rating=None, **{done: True}))
    db_session.flush()
    # Explicit SQL UPDATE avoids the model's default replacing an inserted None.
    db_session.query(model).filter(model.id == rows[-1].id).update({getattr(model, done): None})
    db_session.commit()
    expected = {
        "all": {row.id for row in rows},
        "unfinished": {rows[0].id, rows[1].id, rows[4].id},
        "finished": {rows[2].id, rows[3].id},
    }
    for completion, ids in expected.items():
        page = read_page(authenticated_client, category, completion=completion)
        assert {item["id"] for item in page["items"]} == ids
        assert page["total"] == len(ids)
        filtered = read_page(authenticated_client, category, completion=completion, unrated="true")
        unrated_ids = ids - {rows[1].id, rows[3].id}
        assert {item["id"] for item in filtered["items"]} == unrated_ids
        assert filtered["total"] == len(unrated_ids)
    # Existing clients and explicit disabled filters retain the old response.
    assert read_page(authenticated_client, category) == read_page(
        authenticated_client, category, completion="all", unrated="false", has_progress="false",
    )


@pytest.mark.parametrize("category", ["tv-shows", "anime", "books"])
def test_saved_progress_requires_owned_active_checkpoint_of_same_category(authenticated_client, db_session, category):
    owner = db_session.query(models.User).filter_by(username="testuser").one()
    other = models.User(username="other", email="other@example.test", hashed_password="unused")
    db_session.add(other)
    db_session.flush()
    model, _, _, done, _ = CATEGORIES[category]
    active = model(user_id=owner.id, title="Own active", **{done: True})
    cleared = model(user_id=owner.id, title="Own cleared")
    foreign_checkpoint = model(user_id=owner.id, title="Foreign checkpoint")
    wrong_category = model(user_id=owner.id, title="Wrong category")
    no_checkpoint = model(user_id=owner.id, title="No checkpoint")
    foreign_media = model(user_id=other.id, title="Other private title")
    db_session.add_all([active, cleared, foreign_checkpoint, wrong_category, no_checkpoint, foreign_media])
    db_session.flush()
    unit = "page" if category == "books" else "episode"
    db_session.add_all([
        models.ProgressCheckpoint(user_id=owner.id, category=category, item_id=active.id, unit=unit, position=5),
        models.ProgressCheckpoint(user_id=owner.id, category=category, item_id=cleared.id, unit=None, revision=3),
        models.ProgressCheckpoint(user_id=other.id, category=category, item_id=foreign_checkpoint.id, unit=unit, position=5),
        models.ProgressCheckpoint(user_id=owner.id, category="anime" if category != "anime" else "books",
                                  item_id=wrong_category.id, unit=unit, position=5),
        models.ProgressCheckpoint(user_id=other.id, category=category, item_id=foreign_media.id, unit=unit, position=5),
        models.ProgressCheckpoint(user_id=owner.id, category=category, item_id=999999, unit=unit, position=5),
    ])
    db_session.commit()
    page = read_page(authenticated_client, category, has_progress="true")
    assert page["total"] == 1
    assert [item["id"] for item in page["items"]] == [active.id]
    # Saved progress is independent of completion; users can keep both.
    assert read_page(authenticated_client, category, has_progress="true", completion="finished")["total"] == 1
    assert read_page(authenticated_client, category, has_progress="true", completion="unfinished")["total"] == 0
    assert all("checkpoint" not in item and "progress" not in item for item in page["items"])


def test_combined_filters_search_sort_focus_and_pagination_use_full_library(authenticated_client, db_session):
    owner = db_session.query(models.User).filter_by(username="testuser").one()
    matching = [models.Book(user_id=owner.id, title=f"Needle {i}", read=True, rating=None, year=1900 + i)
                for i in range(117)]
    rejected = [
        models.Book(user_id=owner.id, title="Needle unfinished", read=False, rating=None),
        models.Book(user_id=owner.id, title="Needle zero rated", read=True, rating=0),
        models.Book(user_id=owner.id, title="Needle no progress", read=True, rating=None),
        models.Book(user_id=owner.id, title="Unrelated title", read=True, rating=None),
    ]
    db_session.add_all(matching + rejected)
    db_session.flush()
    db_session.add_all([
        models.ProgressCheckpoint(user_id=owner.id, category="books", item_id=item.id, unit="page", position=50)
        for item in matching + rejected if item.title != "Needle no progress"
    ])
    db_session.commit()
    params = dict(search="Needle", completion="finished", unrated="true", has_progress="true",
                  sort_by="year", order="desc", limit=50)
    pages = [read_page(authenticated_client, "books", **params, offset=offset) for offset in (0, 50, 100)]
    assert [len(page["items"]) for page in pages] == [50, 50, 17]
    assert [page["total"] for page in pages] == [117, 117, 117]
    assert [item["id"] for page in pages for item in page["items"]] == [item.id for item in reversed(matching)]
    assert read_page(authenticated_client, "books", **params, offset=5000) == pages[-1]
    focused = read_page(authenticated_client, "books", **params, focus_id=matching[0].id)
    assert focused["items"][0]["id"] == matching[0].id
    assert focused["total"] == 117
    # Exact navigation may reorder matching records, but may never bypass filters.
    assert read_page(authenticated_client, "books", **params, focus_id=rejected[0].id) == pages[0]
    empty = read_page(authenticated_client, "books", **{**params, "search": "No such book"}, offset=5000)
    assert empty == {"items": [], "total": 0, "offset": 0, "limit": 50}


def test_saved_progress_filter_tracks_save_clear_stale_retry_and_deletion(authenticated_client, test_book_data, db_session):
    created = authenticated_client.post("/books/", json=test_book_data)
    assert created.status_code == 201
    item = created.json()
    endpoint = f"/progress/books/{item['id']}"
    body = {"unit": "page", "position": 60, "expected_revision": 0}
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 0
    assert authenticated_client.put(endpoint, json=body).status_code == 200
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 1
    assert authenticated_client.request("DELETE", endpoint, json={"expected_revision": 1}).status_code == 200
    assert db_session.query(models.ProgressCheckpoint).one().unit is None
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 0
    assert authenticated_client.put(endpoint, json=body).status_code == 409
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 0
    assert authenticated_client.put(endpoint, json={**body, "expected_revision": 2}).status_code == 200
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 1
    assert authenticated_client.delete(f"/books/{item['id']}").status_code == 200
    assert read_page(authenticated_client, "books", has_progress="true")["total"] == 0
    assert db_session.query(models.ProgressCheckpoint).count() == 0


@pytest.mark.parametrize("category", ["movies", "video-games", "music"])
def test_progress_filter_rejects_unsupported_categories(authenticated_client, category):
    response = authenticated_client.get(f"/library/page/{category}", params={"has_progress": "true"})
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Saved progress" in response.json()["detail"]


@pytest.mark.parametrize("params", [
    {"completion": "unknown"}, {"completion": "Finished"}, {"completion": ""},
    {"unrated": "maybe"}, {"has_progress": "maybe"},
])
def test_filter_validation(authenticated_client, params):
    assert authenticated_client.get("/library/page/books", params=params).status_code == 422
