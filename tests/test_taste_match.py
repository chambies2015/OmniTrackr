"""Taste Match: compare libraries with a friend, privacy-aware, and save a friend's favorite."""
from datetime import datetime

from app import crud, models, taste_match
from app.auth import AUTH_COOKIE_NAME
from tests.test_title_pages import member


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _movie(db, user, title, rating=None, year=2014, **extra):
    db.add(models.Movie(user_id=user.id, title=title, year=year, rating=rating, director=extra.pop("director", "Someone"), **extra))
    db.flush()


def _book(db, user, title, rating=None):
    db.add(models.Book(user_id=user.id, title=title, author="An Author", year=2001, rating=rating))
    db.flush()


def _friends(db, a, b):
    crud.create_friendship(db, a.id, b.id)
    db.commit()


def test_score_lists_and_title_matching(authenticated_client, db_session):
    me, pal = _me(db_session), member(db_session, "pal")
    _friends(db_session, me, pal)
    # Same works, written differently.
    _movie(db_session, me, "The Matrix", 9, year=1999)
    _movie(db_session, pal, "matrix", 9.5, year=1999)
    _movie(db_session, me, "Spirited Away!", 8, year=2001)
    _movie(db_session, pal, "Spirited Away", 9, year=2001)
    _movie(db_session, me, "Cats", 2, year=2019)
    _movie(db_session, pal, "Cats", 8, year=2019)
    # A remake decades apart is a different work.
    _movie(db_session, me, "Dune", 9, year=1984)
    _movie(db_session, pal, "Dune", 2, year=2021)
    # Favorites only one side has.
    _movie(db_session, pal, "Paddington 2", 10, year=2017, poster_url="https://img.example/p2.jpg")
    _book(db_session, me, "Piranesi", 9)
    db_session.commit()

    response = authenticated_client.get(f"/api/taste-match/friends/{pal.id}")
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["shared_count"] == 3 and data["rated_count"] == 3
    # (1 - .5/5 + 1 - 1/5 + 1 - 6/5 clipped to 0) / 3
    assert data["score"] == round((0.9 + 0.8 + 0) / 3 * 100) == 57
    assert data["tier"] == "Good match"
    assert [item["title"] for item in data["both_loved"]] == ["The Matrix", "Spirited Away!"]
    assert [(item["title"], item["your_rating"], item["their_rating"]) for item in data["disagreements"]] == [("Cats", 2, 8)]
    assert [item["title"] for item in data["their_picks"]] == ["Paddington 2"]
    assert data["their_picks"][0]["image"] == "https://img.example/p2.jpg"
    assert [item["title"] for item in data["your_picks"]] == ["Dune", "Piranesi"]
    assert data["friend"] == {"id": pal.id, "username": pal.username}
    assert data["private_categories"] == []
    assert "review" not in str(data).lower()


def test_private_categories_are_never_read(authenticated_client, db_session):
    me, pal = _me(db_session), member(db_session, "pal")
    _friends(db_session, me, pal)
    pal.books_private = True
    _book(db_session, me, "Piranesi", 9)
    _book(db_session, pal, "Piranesi", 9)
    _book(db_session, pal, "Secret Diary", 10)
    db_session.commit()

    data = authenticated_client.get(f"/api/taste-match/friends/{pal.id}").json()
    assert data["shared_count"] == 0 and data["score"] is None
    assert "Books" in data["private_categories"]
    assert not data["their_picks"] and not data["your_picks"]
    assert all(row["category"] != "books" for row in data["categories"])
    added = authenticated_client.post(f"/api/taste-match/friends/{pal.id}/add",
                                      json={"category": "books", "title": "Secret Diary"})
    assert added.status_code == 404


def test_not_enough_overlap_has_no_score(authenticated_client, db_session):
    me, pal = _me(db_session), member(db_session, "pal")
    _friends(db_session, me, pal)
    _movie(db_session, me, "Heat", 9, year=1995)
    _movie(db_session, pal, "Heat", None, year=1995)
    db_session.commit()
    data = authenticated_client.get(f"/api/taste-match/friends/{pal.id}").json()
    assert data["score"] is None and data["tier"] is None
    assert data["shared_count"] == 1 and data["needed_for_score"] == 3


def test_strangers_get_nothing(authenticated_client, db_session):
    stranger = member(db_session, "stranger")
    _movie(db_session, stranger, "Heat", 9)
    db_session.commit()
    assert authenticated_client.get(f"/api/taste-match/friends/{stranger.id}").status_code == 403
    assert authenticated_client.post(f"/api/taste-match/friends/{stranger.id}/add",
                                     json={"category": "movies", "title": "Heat"}).status_code == 403
    assert authenticated_client.get("/api/taste-match/friends/0").status_code == 422


def test_add_copies_public_details_only(authenticated_client, db_session):
    me, pal = _me(db_session), member(db_session, "pal")
    _friends(db_session, me, pal)
    _movie(db_session, pal, "Paddington 2", 10, year=2017, director="Paul King", watched=True,
           review="Pal's private thoughts", poster_url="javascript:alert(1)")
    game = models.VideoGame(user_id=pal.id, title="Hades", rating=9.5, played=True,
                            release_date=datetime(2020, 9, 17), cover_art_url="https://img.example/hades.jpg")
    db_session.add(game)
    db_session.commit()

    response = authenticated_client.post(f"/api/taste-match/friends/{pal.id}/add",
                                         json={"category": "movies", "title": "paddington 2"})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "created" and data["title"] == "Paddington 2"
    copy = db_session.query(models.Movie).filter_by(user_id=me.id).one()
    assert (copy.title, copy.year, copy.director) == ("Paddington 2", 2017, "Paul King")
    assert copy.rating is None and not copy.review and copy.watched is False and copy.poster_url is None
    assert data["library_url"] == f"/?library_category=movies&library_item={copy.id}"

    again = authenticated_client.post(f"/api/taste-match/friends/{pal.id}/add",
                                      json={"category": "movies", "title": "Paddington 2"}).json()
    assert again["state"] == "existing"
    assert db_session.query(models.Movie).filter_by(user_id=me.id).count() == 1

    game_copy = authenticated_client.post(f"/api/taste-match/friends/{pal.id}/add",
                                          json={"category": "video-games", "title": "Hades"}).json()
    assert game_copy["state"] == "created"
    saved = db_session.query(models.VideoGame).filter_by(user_id=me.id).one()
    assert saved.played is False and saved.rating is None and saved.cover_art_url == "https://img.example/hades.jpg"
    # The friend's own entries are untouched.
    assert db_session.query(models.Movie).filter_by(user_id=pal.id).one().rating == 10


def test_friends_overview_sorts_best_match_first(authenticated_client, db_session):
    me, close, far, new = _me(db_session), member(db_session, "close"), member(db_session, "far"), member(db_session, "new")
    for friend in (close, far, new):
        _friends(db_session, me, friend)
    for index, title in enumerate(("Alien", "Aliens", "Heat")):
        _movie(db_session, me, title, 9, year=1980 + index * 5)
        _movie(db_session, close, title, 9, year=1980 + index * 5)
        _movie(db_session, far, title, 4, year=1980 + index * 5)
    db_session.commit()

    response = authenticated_client.get("/api/taste-match/friends")
    assert response.status_code == 200
    rows = response.json()["friends"]
    assert [row["friend_id"] for row in rows] == [close.id, far.id, new.id]
    assert rows[0]["score"] == 100 and rows[0]["tier"] == "Taste twins"
    assert rows[2]["score"] is None and rows[2]["shared_count"] == 0


def test_tiers():
    assert taste_match.tier(None) is None
    assert taste_match.tier(85) == "Taste twins"
    assert taste_match.tier(39) == "Opposites attract"


def test_dashboard_wires_the_panel(client):
    client.cookies.set(AUTH_COOKIE_NAME, "x")
    page = client.get("/").text
    assert 'id="friendTasteMatch"' in page
    assert "/static/taste-match.js?v=" in page and "/static/taste-match.css?v=" in page
    assert client.get("/static/taste-match.js").status_code == 200
