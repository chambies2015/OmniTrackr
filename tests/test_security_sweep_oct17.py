"""Fixes from the October 17 full security sweep."""
import time
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app import auth, crud, google_signin, models, schemas, year_in_review
from app.import_studio import MAX_IMPORT_ROWS, _read_csv
from app.routers.titles import _script_json
from app.site_chrome import apply_site_chrome


def member(db, name, email=None, password="testpassword123", **extra):
    fields = {"is_active": True, "is_verified": True, **extra}
    user = models.User(username=name, email=email or f"{name}@example.com",
                       hashed_password=auth.get_password_hash(password), **fields)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def signed_in(client, user):
    client.headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    return client


# ---------------------------------------------------------------- imports

def test_csv_row_cap_stops_reading_at_the_limit():
    flood = b"title\n" + b"x\n" * 2_000_000
    started = time.monotonic()
    with pytest.raises(ValueError, match="limited to"):
        _read_csv(flood)
    assert time.monotonic() - started < 5


def test_csv_at_the_row_cap_still_imports():
    rows, headers = _read_csv(b"title\n" + b"x\n" * MAX_IMPORT_ROWS)
    assert len(rows) == MAX_IMPORT_ROWS and headers == {"title"}


def test_backup_import_caps_each_list():
    movie = {"title": "a", "director": None, "year": None}
    schemas.ImportData(movies=[movie] * 10)
    with pytest.raises(ValidationError):
        schemas.ImportData(movies=[movie] * (schemas.MAX_IMPORT_LIST_ITEMS + 1))


def test_backup_import_still_works_through_the_threadpool(authenticated_client):
    response = authenticated_client.post("/import/", json={"movies": [{"title": "Arrival", "director": None, "year": None}], "tv_shows": []})
    assert response.status_code == 200, response.text
    assert response.json()["movies_created"] == 1


def test_sensitive_routes_are_rate_limited():
    from app.main import limiter
    limited = set(limiter._route_limits)
    for name in (
        "app.routers.account.change_username", "app.routers.account.change_email",
        "app.routers.account.change_password", "app.routers.account.deactivate_account",
        "app.routers.import_studio.preview_import", "app.routers.import_studio.apply_import",
        "app.routers.export_import.import_data", "app.routers.export_import.import_from_file",
        "app.routers.custom_tabs.upload_custom_tab_item_poster",
    ):
        assert name in limited, name


# ---------------------------------------------------------------- sign-in identity

def test_an_email_equal_to_a_username_cannot_capture_that_sign_in(client, db_session):
    member(db_session, "squatter", email="alice")  # an older row from before emails were checked
    member(db_session, "alice")
    response = client.post("/auth/login", data={"username": "alice", "password": "testpassword123"})
    assert response.status_code == 200, response.text


def test_signup_rejects_invalid_and_case_variant_emails(client, db_session):
    member(db_session, "victim", email="victim@gmail.com")
    bad = client.post("/auth/register", json={"email": "alice", "username": "alice1", "password": "testpassword123"})
    assert bad.status_code == 400 and "valid email" in bad.json()["detail"]
    copy = client.post("/auth/register", json={"email": "Victim@Gmail.com", "username": "copycat", "password": "testpassword123"})
    assert copy.status_code == 400 and "already registered" in copy.json()["detail"]


def test_email_change_rejects_a_case_variant_of_another_account(client, db_session):
    member(db_session, "victim", email="victim@gmail.com")
    me = member(db_session, "mover")
    response = signed_in(client, me).put("/account/email", json={"new_email": "VICTIM@gmail.com", "password": "testpassword123"})
    assert response.status_code == 400


def test_google_sign_in_prefers_the_exact_verified_account(db_session):
    copy = member(db_session, "copycat", email="Victim@Gmail.com", is_verified=False)
    real = member(db_session, "victim", email="victim@gmail.com")
    assert copy.id < real.id
    user, outcome = google_signin.find_or_create_user(
        db_session, {"sub": "g-1", "email": "victim@gmail.com", "email_verified": True, "name": "Victim"})
    assert user.id == real.id and outcome == "linked"


# ---------------------------------------------------------------- deactivated members

def test_friends_cannot_read_a_deactivated_members_library(client, db_session):
    reader = member(db_session, "reader")
    gone = member(db_session, "gone")
    db_session.add(models.Friendship(user1_id=min(reader.id, gone.id), user2_id=max(reader.id, gone.id)))
    db_session.add(models.Movie(user_id=gone.id, title="Secret", review="private note"))
    db_session.commit()
    signed_in(client, reader)
    assert client.get(f"/friends/{gone.id}/movies").status_code == 200

    gone.is_active = False
    db_session.commit()
    assert client.get(f"/friends/{gone.id}/movies").status_code == 403
    assert client.get(f"/friends/{gone.id}/statistics").status_code == 403
    assert all(friend["id"] != gone.id for friend in client.get("/friends").json())
    assert client.post("/friends/request", json={"receiver_username": "gone"}).status_code == 404
    # The friendship itself is kept so reactivating restores it.
    assert crud.are_friends(db_session, reader.id, gone.id, include_deactivated=True)


def test_recommendation_postcard_of_a_deactivated_member_is_gone(client, db_session):
    owner = member(db_session, "postie")
    db_session.add(models.RecommendationRequest(
        owner_id=owner.id, public_token="tok-postcard-123", prompt="What should I watch?",
        allowed_categories="movies", max_responses=5, expires_at=datetime.utcnow() + timedelta(days=7)))
    db_session.commit()
    assert client.get("/recommendations/public/tok-postcard-123").status_code == 200
    owner.is_active = False
    db_session.commit()
    assert client.get("/recommendations/public/tok-postcard-123").status_code == 404


def test_making_a_category_private_updates_shared_recaps(authenticated_client, db_session):
    year = datetime.utcnow().year
    for path, payload, done in (("/movies/", {"title": "Arrival", "director": "D", "year": 2016}, "watched"),
                                ("/books/", {"title": "Piranesi", "author": "S", "year": 2020}, "read")):
        item = authenticated_client.post(path, json=dict(payload, **{done: True})).json()
        authenticated_client.post("/completion-moments/", json={"category": path.strip("/"), "item_id": item["id"]})
    state = authenticated_client.put(f"/api/year-in-review/{year}/share", json={}).json()
    path = "/" + state["url"].split("://", 1)[1].split("/", 1)[1]
    assert "Piranesi" in authenticated_client.get(path).text

    response = authenticated_client.put("/account/privacy", json={"books_private": True})
    assert response.status_code == 200, response.text
    page = authenticated_client.get(path).text
    assert "Piranesi" not in page and "Arrival" in page


# ---------------------------------------------------------------- page markup

def test_title_json_ld_cannot_open_a_comment_or_close_the_script():
    out = _script_json({"reviewBody": "<!--<script> </script> <!--SITE_NAV:--> a & b"})
    assert "<" not in out and ">" not in out and "&" not in out


def test_quoting_the_stylesheet_path_does_not_drop_site_assets():
    html = "<html><head></head><body><!--SITE_FOOTER-->/static/site.css</body></html>"
    assert 'href="/static/site.css' in apply_site_chrome(html)


def test_collection_name_cannot_pull_in_a_later_template_value(client, db_session):
    owner = member(db_session, "curator")
    collection = models.Collection(
        user_id=owner.id, name="{{STRUCTURED_DATA}}", is_public=True, moderation_status="approved",
        approved_at=datetime.utcnow(), published_at=datetime.utcnow(),
        description='a" style="position:fixed" x="' + " A carefully chosen shelf of films." * 12)
    db_session.add(collection)
    db_session.flush()
    for position, title in enumerate(("Alien", "Heat", "Ran")):
        movie = models.Movie(user_id=owner.id, title=title, director="X", year=1980)
        db_session.add(movie)
        db_session.flush()
        db_session.add(models.CollectionItem(collection_id=collection.id, category="movies", item_id=movie.id, position=position))
    db_session.commit()
    response = client.get(f"/collections/public/{collection.id}")
    assert response.status_code == 200, response.text
    assert "{{STRUCTURED_DATA}}" in response.text
    # The JSON-LD appears once, in its own script, never inside an attribute.
    assert response.text.count('"@context"') == 1
