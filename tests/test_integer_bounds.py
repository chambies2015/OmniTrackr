"""Integer inputs must fail validation before reaching database bind parameters."""
import json
from datetime import datetime

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app import models, schemas
from app.crud import export_import as importer
from app.main import app


SQL_MAX = 2**31 - 1
HUGE = 10**100
MEDIA = [
    ("movies", "Movie", {"director": "Creator", "year": 2000}),
    ("tv-shows", "TVShow", {"year": 2000}),
    ("anime", "Anime", {"year": 2000}),
    ("music", "Music", {"artist": "Creator", "year": 2000}),
    ("books", "Book", {"author": "Creator", "year": 2000}),
]


@pytest.mark.parametrize("category,name,metadata", MEDIA)
@pytest.mark.parametrize("suffix", ["Create", "Update", "Import"])
@pytest.mark.parametrize("value", [10000, HUGE])
def test_year_write_bounds(category, name, metadata, suffix, value):
    schema = getattr(schemas, name + suffix)
    payload = {"title": "Bounded", **metadata, "year": value}
    with pytest.raises(ValidationError):
        schema(**payload)
    assert schema(**{**payload, "year": 9999}).year == 9999


@pytest.mark.parametrize("name", ["TVShow", "Anime"])
@pytest.mark.parametrize("suffix", ["Create", "Update", "Import"])
@pytest.mark.parametrize("field", ["seasons", "episodes"])
@pytest.mark.parametrize("value", [SQL_MAX + 1, HUGE])
def test_series_count_write_bounds(name, suffix, field, value):
    schema = getattr(schemas, name + suffix)
    payload = {"title": "Bounded", "year": 2000, field: value}
    with pytest.raises(ValidationError):
        schema(**payload)
    assert getattr(schema(**{**payload, field: SQL_MAX}), field) == SQL_MAX


@pytest.mark.parametrize("category,name,metadata", MEDIA)
def test_read_schema_keeps_existing_integer_metadata(category, name, metadata):
    schema = getattr(schemas, name)
    assert schema(id=1, title="Historical", **{**metadata, "year": 10000}).year == 10000


@pytest.mark.parametrize("schema,field,payload", [
    (schemas.ActivityEntryCreate, "item_id", {"category": "movies"}),
    (schemas.ActivityEntryImport, "item_id", {"category": "movies", "title": "Movie", "action": "noted", "occurred_at": datetime(2020, 1, 1)}),
    (schemas.NextUpItemCreate, "item_id", {"category": "movies"}),
    (schemas.CompletionMomentCreate, "item_id", {"category": "movies"}),
    (schemas.CollectionItemCreate, "item_id", {"category": "movies"}),
    (schemas.RecommendationInviteCreate, "friend_id", {}),
    (schemas.NextUpItemMove, "position", {}),
    (schemas.CollectionItemMove, "position", {}),
    (schemas.CustomTabFieldCreate, "order", {"key": "count", "label": "Count", "field_type": "number"}),
])
def test_database_body_integer_bounds(schema, field, payload):
    with pytest.raises(ValidationError):
        schema(**{**payload, field: HUGE})
    assert getattr(schema(**{**payload, field: SQL_MAX}), field) == SQL_MAX


@pytest.mark.parametrize("category,name,metadata", MEDIA)
@pytest.mark.parametrize("update", [False, True])
def test_api_rejects_oversized_year_without_database_error(authenticated_client, category, name, metadata, update):
    client = authenticated_client
    payload = {"title": "Safe", **metadata}
    if update:
        created = client.post(f"/{category}/", json=payload)
        assert created.status_code == 201
        response = client.put(f"/{category}/{created.json()['id']}", json={"year": HUGE})
    else:
        response = client.post(f"/{category}/", json={**payload, "year": HUGE})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("file_upload", [False, True])
@pytest.mark.parametrize("field", ["year", "episodes"])
def test_native_import_rejects_oversized_integers(authenticated_client, file_upload, field):
    payload = {"movies": [], "tv_shows": [{"title": "Oversized", "year": 2000, field: HUGE}]}
    if file_upload:
        response = authenticated_client.post("/import/file/", files={"file": ("backup.json", json.dumps(payload), "application/json")})
    else:
        response = authenticated_client.post("/import/", json=payload)
    assert response.status_code == (400 if file_upload else 422), response.text
    assert field in response.text


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/movies/{id}", None),
    ("put", "/tv-shows/{id}", {"year": 2000}),
    ("delete", "/anime/{id}", None),
    ("get", "/video-games/{id}", None),
    ("get", "/music/{id}", None),
    ("get", "/books/{id}", None),
    ("get", "/library/item/movies/{id}", None),
    ("get", "/custom-tabs/{id}/items", None),
    ("get", "/friends/{id}/profile", None),
    ("post", "/friends/requests/{id}/accept", None),
    ("delete", "/notifications/{id}", None),
    ("delete", "/next-up/{id}", None),
    ("patch", "/activity/{id}", {"note": "Safe"}),
    ("patch", "/completion-moments/{id}", {"takeaway": "Safe"}),
    ("patch", "/collections/{id}", {"name": "Safe"}),
    ("post", "/recommendations/requests/{id}/close", None),
    ("get", "/custom-tab-posters/{id}", None),
])
def test_private_routes_reject_oversized_ids(authenticated_client, method, path, payload):
    response = authenticated_client.request(method, path.format(id=HUGE), json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("path", [
    "/api/public/reviews/{id}?category=movies",
    "/reviews/{id}?category=movies",
    "/collections/public/{id}",
    "/collections/public/{id}/save",
    "/u/id/{id}",
    "/u/id/{id}/card.png",
    "/profile-pictures/{id}",
])
@pytest.mark.parametrize("value", [str(SQL_MAX + 1), str(HUGE), "1" * 5000], ids=["sql-overflow", "oversized-decimal", "python-digit-limit"])
def test_public_routes_reject_oversized_ids(client, path, value):
    response = client.get(path.format(id=value))
    expected = 404 if path.startswith("/u/id/") and len(value) > 10 else 422
    assert response.status_code == expected, response.text


def test_every_database_path_id_is_bounded():
    checked = 0
    def routes(router):
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from routes(route.original_router)

    for route in routes(app.router):
        if not isinstance(route, APIRoute) or route.path.startswith(("/auth", "/account", "/import-studio")):
            continue
        for field in route.dependant.path_params:
            if field.name.endswith("_id"):
                _, errors = field.validate(HUGE)
                assert errors, f"Unbounded path ID: {route.path} {field.name}"
                _, errors = field.validate(SQL_MAX)
                assert not errors, f"Valid database ID rejected: {route.path} {field.name}"
                checked += 1
    assert checked >= 70


@pytest.mark.parametrize("path", ["/library/page/movies?focus_id={id}", "/activity/?offset={id}", "/api/public/reviews?offset={id}", "/api/public/review-feed?offset={id}"])
def test_database_query_integers_are_bounded(authenticated_client, path):
    response = authenticated_client.get(path.format(id=HUGE))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("year", [HUGE, SQL_MAX + 1, "1" * 100], ids=["huge-integer", "sql-overflow", "huge-string"])
def test_native_collection_identity_skips_oversized_year(authenticated_client, db_session, year):
    response = authenticated_client.post("/import/", json={"collections": [{"name": "Unsafe identity", "items": [{"category": "movies", "title": "Missing", "year": year}]}]})
    assert response.status_code == 200, response.text
    assert db_session.query(models.CollectionItem).count() == 0


@pytest.mark.parametrize("prefix", ["1" * 5000, str(SQL_MAX + 1), "0"], ids=["python-digit-limit", "sql-overflow", "zero"])
def test_legacy_profile_filename_rejects_oversized_prefix(client, prefix):
    response = client.get(f"/static/profile_pictures/{prefix}_image.jpg", follow_redirects=False)
    assert response.status_code == 404, response.text


def test_legacy_profile_filename_keeps_valid_redirect(client):
    response = client.get(f"/static/profile_pictures/{SQL_MAX}_image.jpg", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == f"/profile-pictures/{SQL_MAX}"


@pytest.mark.parametrize("model,schema,apply,metadata", [
    (models.Movie, schemas.MovieImport, importer.import_movies, {"director": "Creator", "year": 2000}),
    (models.TVShow, schemas.TVShowImport, importer.import_tv_shows, {"year": 2000}),
    (models.Anime, schemas.AnimeImport, importer.import_anime, {"year": 2000}),
    (models.VideoGame, schemas.VideoGameCreate, importer.import_video_games, {"release_date": datetime(2000, 1, 2)}),
    (models.Music, schemas.MusicImport, importer.import_music, {"artist": "Creator", "year": 2000}),
    (models.Book, schemas.BookImport, importer.import_books, {"author": "Creator", "year": 2000}),
])
def test_native_import_explicit_false_removes_public_review(db_session, model, schema, apply, metadata):
    user = models.User(username="bounds", email="bounds@example.invalid", hashed_password="unused", is_verified=True)
    db_session.add(user)
    db_session.flush()
    item = model(user_id=user.id, title="Private restore", review="Previously public", review_public=True, **metadata)
    db_session.add(item)
    db_session.commit()
    payload = schema(title=item.title, review="Private restored note", review_public=False, **metadata)
    assert apply(db_session, user.id, [payload]) == (0, 1, [])
    db_session.refresh(item)
    assert item.review_public is False
    assert item.review == "Private restored note"
