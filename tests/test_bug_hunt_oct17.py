"""Functional fixes from the October 17 site-wide bug hunt."""
from datetime import date, datetime, timedelta

from app import crud, import_studio, models
from app import release_radar as radar
from app import year_in_review
from app.crud import export_import
from app.crud.statistics import _rating_bucket


def member(db, name, **extra):
    fields = {"email": f"{name}@example.com", "is_active": True, "is_verified": True, **extra}
    user = models.User(username=name, hashed_password="x", **fields)
    db.add(user)
    db.flush()
    return user


def me(db):
    return db.query(models.User).filter(models.User.username == "testuser").one()


# ---------------------------------------------------------------- library page

def test_rating_sort_lists_unrated_titles_last_both_ways(authenticated_client, db_session):
    user = me(db_session)
    db_session.add_all([
        models.Movie(user_id=user.id, title="Unrated", director="A", year=2000, rating=None),
        models.Movie(user_id=user.id, title="Low", director="A", year=2000, rating=3),
        models.Movie(user_id=user.id, title="High", director="A", year=2000, rating=9),
    ])
    db_session.commit()
    for order, expected in (("desc", ["High", "Low", "Unrated"]), ("asc", ["Low", "High", "Unrated"])):
        page = authenticated_client.get(f"/library/page/movies?sort_by=rating&order={order}").json()
        assert [item["title"] for item in page["items"]] == expected


def test_library_page_search_treats_percent_and_underscore_literally(authenticated_client, db_session):
    user = me(db_session)
    db_session.add_all([
        models.Movie(user_id=user.id, title="100% Wolf", director="A", year=2020),
        models.Movie(user_id=user.id, title="1000 Wolves", director="A", year=2020),
        models.Movie(user_id=user.id, title="snake_case", director="A", year=2020),
        models.Movie(user_id=user.id, title="snakeXcase", director="A", year=2020),
    ])
    db_session.commit()
    titles = lambda q: [i["title"] for i in authenticated_client.get(f"/library/page/movies?search={q}").json()["items"]]
    assert titles("100%25") == ["100% Wolf"]
    assert titles("snake_") == ["snake_case"]
    assert titles("WOLF") == ["100% Wolf"]


# ---------------------------------------------------------------- import studio

def test_import_studio_reads_a_zero_rating_as_unrated():
    goodreads = b"Title,Author,My Rating,Year Published,Exclusive Shelf\nPiranesi,Susanna Clarke,0,2020,to-read\n"
    _, rows = import_studio.parse_csv(goodreads)
    assert rows[0].data["rating"] is None
    mal = b"series_title,series_episodes,my_score,my_status,series_start\nFrieren,28,0,Plan to Watch,2023-09-29\n"
    _, rows = import_studio.parse_csv(mal)
    assert rows[0].data["rating"] is None
    _, rows = import_studio.parse_csv(mal.replace(b",0,Plan", b",9,Plan"))
    assert rows[0].data["rating"] == 9


# ---------------------------------------------------------------- backups

def test_backup_import_drops_values_for_fields_the_tab_no_longer_has(db_session):
    ann = member(db_session, "ann")
    db_session.commit()
    created, _, errors = export_import.import_custom_tabs(db_session, ann.id, [{
        "name": "Podcasts",
        "fields": [{"key": "score", "label": "Score", "field_type": "number", "required": False, "order": 0}],
        "items": [{"title": "Serial", "field_values": {"score": 8, "region": "US"}}],
    }])
    assert created == 1 and errors == []
    item = db_session.query(models.CustomTabItem).one()
    assert item.title == "Serial"
    assert "region" not in item.field_values


# ---------------------------------------------------------------- friends

def test_dismissed_friend_request_comes_back_when_sent_again(db_session):
    ann, bea = member(db_session, "ann"), member(db_session, "bea")
    db_session.commit()
    request = crud.create_friend_request(db_session, ann.id, bea.id)
    db_session.query(models.Notification).filter_by(user_id=bea.id).delete()
    db_session.commit()
    try:
        crud.create_friend_request(db_session, ann.id, bea.id)
    except ValueError as error:
        assert "already exists" in str(error)
    note = db_session.query(models.Notification).filter_by(user_id=bea.id).one()
    assert note.friend_request_id == request.id


def test_sending_a_request_back_accepts_the_pending_one(db_session):
    ann, bea = member(db_session, "ann"), member(db_session, "bea")
    db_session.commit()
    crud.create_friend_request(db_session, ann.id, bea.id)
    crud.create_friend_request(db_session, bea.id, ann.id)
    assert crud.are_friends(db_session, ann.id, bea.id)


def test_expired_pending_request_no_longer_blocks_a_new_one(db_session):
    ann, bea = member(db_session, "ann"), member(db_session, "bea")
    db_session.commit()
    old = crud.create_friend_request(db_session, ann.id, bea.id)
    old.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    fresh = crud.create_friend_request(db_session, ann.id, bea.id)
    assert fresh.id != old.id
    assert crud.get_friend_request(db_session, old.id).status == "expired"


def test_cancelling_a_request_removes_the_receivers_notification(db_session):
    ann, bea = member(db_session, "ann"), member(db_session, "bea")
    db_session.commit()
    request = crud.create_friend_request(db_session, ann.id, bea.id)
    crud.cancel_friend_request(db_session, request.id, ann.id)
    assert db_session.query(models.Notification).filter_by(user_id=bea.id).count() == 0


def test_friend_request_finds_usernames_regardless_of_case(authenticated_client, db_session):
    member(db_session, "bea")
    member(db_session, "gone", is_active=False)
    db_session.commit()
    assert authenticated_client.post("/friends/request", json={"receiver_username": "Bea"}).status_code == 200
    assert authenticated_client.post("/friends/request", json={"receiver_username": "gone"}).status_code == 404


# ---------------------------------------------------------------- account and sign-in

def test_wrong_password_in_account_settings_is_not_a_signed_out_error(authenticated_client):
    response = authenticated_client.put("/account/password", json={
        "current_password": "wrongpassword", "new_password": "newpassword123",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect current password"
    assert authenticated_client.get("/account/me").status_code == 200


def test_sign_in_and_email_lookups_ignore_case(client, authenticated_client, db_session):
    login = lambda name: client.post("/auth/login", data={"username": name, "password": "testpassword123"})
    assert login("TestUser").status_code == 200
    assert login("TEST@example.com").status_code == 200
    duplicate = client.post("/auth/register", json={
        "email": "Test@Example.com", "username": "someoneelse", "password": "testpassword123",
    })
    assert duplicate.status_code == 400
    assert crud.get_user_by_email(db_session, "TEST@EXAMPLE.COM").username == "testuser"


def test_case_lookup_never_picks_between_two_matching_accounts(db_session):
    member(db_session, "Twin")
    member(db_session, "twin2", email="Twin@example.org")
    db_session.add(models.User(username="TWIN", email="twin@example.org", hashed_password="x",
                               is_active=True, is_verified=True))
    db_session.commit()
    assert crud.get_user_by_username_or_email(db_session, "twin") is None
    assert crud.get_user_by_username_or_email(db_session, "TWIN").username == "TWIN"


# ---------------------------------------------------------------- goals and recaps

def test_deleting_a_finished_title_does_not_count_it_twice(authenticated_client, db_session):
    user = me(db_session)
    movie = models.Movie(user_id=user.id, title="Alien", director="Scott", year=1979, watched=True)
    db_session.add(movie)
    db_session.commit()
    when = datetime(date.today().year, 1, 5)
    db_session.add_all([
        models.ActivityEntry(user_id=user.id, category="movies", item_id=movie.id, title="Alien",
                             action="completed", occurred_at=when),
        models.CompletionMoment(user_id=user.id, category="movies", item_id=movie.id, title="Alien",
                                completed_at=when),
    ])
    db_session.commit()
    assert year_in_review.finished_counts(db_session, user.id, when.year)["movies"] == 1
    assert authenticated_client.delete(f"/movies/{movie.id}").status_code in (200, 204)
    db_session.expire_all()
    assert year_in_review.finished_counts(db_session, user.id, when.year)["movies"] == 1


def test_rating_chart_rounds_halves_up():
    assert [_rating_bucket(r) for r in (0.4, 0.5, 2.5, 7.5, 8.5, 8.49, 10)] == [0, 1, 3, 8, 9, 8, 10]


# ---------------------------------------------------------------- release radar links

def test_radar_links_open_the_period_that_lists_the_title():
    today = date(2026, 10, 25)  # Within ten days of month end, the movies page features November.
    current = radar.current_window("movies", today).slug
    featured = radar.featured_window("movies", today).slug
    assert current != featured
    assert radar.item_path({"category": "movies", "window": current}, today) == f"/release-radar/movies/{current}"
    assert radar.item_path({"category": "movies", "window": featured}, today) == "/release-radar/movies"
    assert radar.item_path({"category": "movies"}, today) == "/release-radar/movies"
    assert radar.item_path({"category": "movies", "window": "1999-01"}, today) == "/release-radar/movies"
