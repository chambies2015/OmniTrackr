"""Nov 21 2026 follow-up to the Essential 100 sweep: runs of adds in the friends feed, and
Essentials saves that tell a remake from the original, find anime films filed under movies,
and only undo titles from the lists."""
from datetime import datetime, timedelta

import pytest

from app import essentials, friend_feed, models, title_search
from tests.test_friend_recs import _friend, _me
from tests.test_title_pages import add_movie


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    essentials._details_cache.update({"index": None, "details": None})
    yield
    title_search.clear_cache()


def _feed(client):
    response = client.get("/api/friend-feed")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _ago(**delta):
    return datetime.utcnow() - timedelta(**delta)


# ---------------------------------------------------------------- friends feed runs

def test_an_import_of_finished_rated_titles_is_one_card(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    start = _ago(hours=1)
    for number in range(12):
        add_movie(db_session, dana, title=f"Imported {number}", year=1990 + number, watched=True,
                  rating=6.0 + number % 4, added_at=start + timedelta(seconds=number))
    for number in range(3):
        db_session.add(models.Book(user_id=dana.id, title=f"Book {number}", author="A", read=number < 2,
                                   added_at=start + timedelta(seconds=20 + number)))
    db_session.commit()
    items = _feed(authenticated_client)
    assert len(items) == 1
    burst = items[0]
    assert burst["type"] == "burst" and burst["count"] == 15 and burst["finished"] == 14
    assert len(burst["titles"]) == friend_feed.BURST_SHOWN and burst["titles"][0]["title"] == "Book 2"
    assert burst["id"].startswith(f"burst-{dana.id}-") and "T" in burst["id"]


def test_titles_flipped_to_finished_as_they_came_in_join_the_run(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movies = [add_movie(db_session, dana, title=f"Flip {number}", year=2000 + number) for number in range(6)]
    db_session.commit()
    for movie in movies:
        movie.watched = True
    db_session.commit()
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=dana.id, kind="finished").count() == 6
    items = _feed(authenticated_client)
    assert [item["type"] for item in items] == ["burst"]
    assert items[0]["count"] == 6 and items[0]["finished"] == 6


def test_a_few_adds_by_hand_keep_their_own_cards(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    for number in range(friend_feed.RUN_MIN - 1):
        add_movie(db_session, dana, title=f"By hand {number}", year=2001 + number, watched=True, rating=8.0,
                  added_at=_ago(minutes=30) + timedelta(seconds=number * 40))
    db_session.commit()
    items = _feed(authenticated_client)
    assert [item["type"] for item in items] == ["title"] * (friend_feed.RUN_MIN - 1)


def test_adds_spread_through_the_day_are_not_a_run(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    base = datetime.utcnow().replace(hour=0, minute=5, second=0, microsecond=0)
    if base > datetime.utcnow() - timedelta(hours=1):
        base -= timedelta(days=1)
    for number in range(6):
        add_movie(db_session, dana, title=f"Spread {number}", year=2001 + number, watched=True,
                  added_at=base + timedelta(minutes=10 * number))
    for number in range(5):  # Plain adds through the day still make the day's card.
        add_movie(db_session, dana, title=f"Plain {number}", year=1981 + number,
                  added_at=base + timedelta(minutes=10 * number + 5))
    db_session.commit()
    items = _feed(authenticated_client)
    bursts = [item for item in items if item["type"] == "burst"]
    assert len(bursts) == 1 and bursts[0]["count"] == 5 and bursts[0]["finished"] == 0
    assert bursts[0]["id"] == f"burst-{dana.id}-{base.date().isoformat()}"
    assert sorted(item["title"] for item in items if item["type"] == "title") == [f"Spread {n}" for n in range(6)]


def test_rating_old_titles_quickly_is_not_a_run(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    old = [add_movie(db_session, dana, title=f"Old {number}", year=1970 + number, added_at=_ago(days=200))
           for number in range(7)]
    db_session.commit()
    for movie in old:
        movie.rating = 7.5
    db_session.commit()
    items = _feed(authenticated_client)
    assert [item.get("kind") for item in items] == ["rated"] * 7


def test_two_runs_on_one_day_have_their_own_cards(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    for start in (_ago(hours=3), _ago(minutes=20)):
        for number in range(5):
            add_movie(db_session, dana, title=f"Run {start.minute}-{number}", year=1990 + number, watched=True,
                      added_at=start + timedelta(seconds=number))
    db_session.commit()
    items = _feed(authenticated_client)
    assert [item["type"] for item in items] == ["burst", "burst"]
    assert len({item["id"] for item in items}) == 2


def test_runs_are_per_friend(authenticated_client, db_session):
    me = _me(db_session)
    dana, sam = _friend(db_session, me), _friend(db_session, me, "sam")
    start = _ago(minutes=40)
    for number in range(6):
        friend = dana if number % 2 else sam
        add_movie(db_session, friend, title=f"Shared {number}", year=2000 + number, watched=True,
                  added_at=start + timedelta(seconds=number))
    db_session.commit()
    assert [item["type"] for item in _feed(authenticated_client)] == ["title"] * 6


# ---------------------------------------------------------------- Essentials saves

def _user(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


def _item(item_id):
    item = essentials.item_by_id(item_id)
    assert item is not None, item_id
    return item


def test_a_remake_of_the_same_name_does_not_block_the_original(authenticated_client, db_session):
    user = _user(db_session)
    add_movie(db_session, user, title="Nosferatu", year=2024, director="Robert Eggers", watched=True, rating=7.0)
    db_session.commit()
    body = authenticated_client.post("/api/essentials/save", json={"id": "movie/nosferatu-1922", "answer": "seen"}).json()
    assert body["state"] == "created" and body["done"] is True
    films = db_session.query(models.Movie).filter_by(user_id=user.id, title="Nosferatu").order_by(models.Movie.year).all()
    assert [(film.year, film.watched, film.rating) for film in films] == [(1922, True, None), (2024, True, 7.0)]
    again = authenticated_client.post("/api/essentials/save", json={"id": "movie/nosferatu-1922", "answer": "want"}).json()
    assert again["state"] == "existing" and again["item_id"] == body["item_id"]


def test_a_title_with_no_year_or_another_name_counts_as_the_same(authenticated_client, db_session):
    user = _user(db_session)
    add_movie(db_session, user, title="Nosferatu", year=None, watched=False)
    add_movie(db_session, user, title="Ladri di biciclette", year=1948, watched=True)
    db_session.commit()
    first = authenticated_client.post("/api/essentials/save", json={"id": "movie/nosferatu-1922", "answer": "seen"}).json()
    assert first["state"] == "existing" and first["done"] is False
    second = authenticated_client.post("/api/essentials/save", json={"id": "movie/bicycle-thieves-1948", "answer": "seen"}).json()
    assert second["state"] == "existing" and second["title"] == "Ladri di biciclette" and second["done"] is True
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 2


def test_an_anime_film_filed_under_movies_is_found_there(authenticated_client, db_session):
    user = _user(db_session)
    film = _item("anime/belladonna-of-sadness-1973")
    movie = add_movie(db_session, user, title=film["title"], year=film["year"], director="", watched=True)
    db_session.commit()
    body = authenticated_client.post("/api/essentials/save", json={"id": film["id"], "answer": "want"}).json()
    assert body["state"] == "existing" and body["category"] == "movies" and body["item_id"] == movie.id
    assert body["done"] is True and body["library_url"] == f"/?library_category=movies&library_item={movie.id}"
    imported = authenticated_client.post("/api/essentials/import", json={"ids": [film["id"]]}).json()
    assert imported == {"added": 0, "existing": 1, "missing": 0}
    assert db_session.query(models.Anime).filter_by(user_id=user.id).count() == 0


def test_an_album_of_the_same_name_by_someone_else_is_a_different_album(authenticated_client, db_session):
    user = _user(db_session)
    album = _item("album/in-the-wee-small-hours-1955")
    db_session.add(models.Music(user_id=user.id, title=album["title"], artist="A Tribute Band", year=2019, listened=True))
    db_session.commit()
    body = authenticated_client.post("/api/essentials/import", json={"ids": [album["id"]]}).json()
    assert body == {"added": 1, "existing": 0, "missing": 0}
    artists = sorted(row.artist for row in db_session.query(models.Music).filter_by(user_id=user.id))
    assert artists == ["A Tribute Band", "Frank Sinatra"]


def test_import_tells_remakes_apart_too(authenticated_client, db_session):
    user = _user(db_session)
    add_movie(db_session, user, title="Godzilla", year=2014, director="Gareth Edwards", watched=False)
    add_movie(db_session, user, title="Nosferatu", year=1922, director="", watched=False)
    db_session.commit()
    body = authenticated_client.post("/api/essentials/import",
                                     json={"ids": ["movie/godzilla-1954", "movie/nosferatu-1922"]}).json()
    assert body == {"added": 1, "existing": 1, "missing": 0}
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Godzilla", year=1954).one().watched is True
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Nosferatu").one().watched is False
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=user.id).count() == 0


def test_undo_only_takes_back_titles_from_the_lists(authenticated_client, db_session):
    user = _user(db_session)
    other = add_movie(db_session, user, title="Something I just added", year=2025)
    db_session.commit()
    refused = authenticated_client.post("/api/essentials/undo", json={"category": "movies", "item_id": other.id})
    assert refused.status_code == 409 and "isn't on the Essential 100" in refused.json()["detail"]
    assert db_session.query(models.Movie).filter_by(id=other.id).count() == 1
    game = essentials.get("games")["items"][0]
    body = authenticated_client.post("/api/essentials/save", json={"id": game["id"], "answer": "seen"}).json()
    assert body["state"] == "created" and body["category"] == "video-games"
    undo = authenticated_client.post("/api/essentials/undo", json={"category": body["category"], "item_id": body["item_id"]})
    assert undo.status_code == 200 and undo.json() == {"removed": True}


def test_anime_film_saved_under_movies_can_be_undone_from_the_anime_list(db_session):
    film = _item("anime/galaxy-express-999-1979")
    movie = models.Movie(user_id=1, title=film["title"], director="", year=film["year"])
    assert essentials.from_a_list("movie", movie)
    assert not essentials.from_a_list("movie", models.Movie(user_id=1, title=film["title"], director="", year=2010))
    assert essentials.kind_of(movie) == "movie" and essentials.kind_of(models.Anime(user_id=1, title="x")) == "anime"
