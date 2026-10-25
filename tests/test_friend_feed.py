"""Friends feed: friends' recent adds, finishes, ratings and reviews, with cheers and one-tap saves."""
from datetime import datetime, timedelta

from app import friend_feed, models
from tests.test_friend_recs import _as, _friend, _me
from tests.test_title_pages import add_movie, member


def _feed(client, **params):
    response = client.get("/api/friend-feed", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def _titles(data):
    return [(item["friend"]["username"], item.get("kind"), item.get("title")) for item in data["items"]]


def test_no_friends_gives_an_empty_feed(authenticated_client):
    data = _feed(authenticated_client)
    assert data == {"items": [], "next_before": None, "friends": 0, "sharing": True}


def test_feed_shows_friend_adds_with_rating_and_status_but_never_strangers(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    stranger = member(db_session, "stranger")
    add_movie(db_session, dana, rating=9.0, watched=True, review="  Docking   scene  forever. ",
              poster_url="https://img.example.com/i.jpg")
    add_movie(db_session, stranger, title="Heat", year=1995)
    db_session.add(models.Book(user_id=dana.id, title="Dune", author="Frank Herbert", year=1965))
    db_session.commit()

    data = _feed(authenticated_client)
    assert data["friends"] == 1 and data["sharing"] is True
    assert sorted(_titles(data)) == [("dana", "added", "Dune"), ("dana", "added", "Interstellar")]
    movie = next(item for item in data["items"] if item["title"] == "Interstellar")
    assert movie["finished"] is True and movie["rating"] == 9.0 and movie["review"] == "Docking scene forever."
    assert movie["creator"] == "Christopher Nolan" and movie["year"] == 2014 and movie["category_label"] == "Movie"
    assert movie["image"] == "https://img.example.com/i.jpg" and movie["in_library"] is False
    assert movie["cheers"] == 0 and movie["cheered"] is False and movie["spoiler"] is False
    assert "Heat" not in str(data)


def test_private_categories_inactive_friends_and_old_adds_stay_out(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    gone = _friend(db_session, me, "gone")
    gone.is_active = False
    dana.books_private = True
    add_movie(db_session, dana, title="Old One", added_at=datetime.utcnow() - timedelta(days=45))
    add_movie(db_session, dana, title="Legacy").added_at = None  # predates add dates
    add_movie(db_session, gone, title="Hidden")
    db_session.add(models.Book(user_id=dana.id, title="Private Book", author="A"))
    db_session.commit()
    assert _feed(authenticated_client)["items"] == []


def test_finishing_rating_and_reviewing_an_existing_title_shows_up_and_undoing_hides_it(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, dana, added_at=datetime.utcnow() - timedelta(days=200))
    db_session.commit()
    assert _feed(authenticated_client)["items"] == []

    movie.watched = True
    movie.rating = 8.5
    db_session.commit()
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=dana.id).one().kind == "finished"
    data = _feed(authenticated_client)
    assert _titles(data) == [("dana", "finished", "Interstellar")]

    movie.watched = False
    db_session.commit()
    assert _feed(authenticated_client)["items"] == []

    movie.review = "Loved it"
    db_session.commit()
    assert _titles(_feed(authenticated_client)) == [("dana", "reviewed", "Interstellar")]

    # Saving the same rating again is not news.
    movie.rating = 8.5
    db_session.commit()
    assert db_session.query(models.FriendFeedEvent).count() == 2


def test_my_own_library_changes_are_not_in_my_feed(authenticated_client, db_session):
    me = _me(db_session)
    _friend(db_session, me)
    mine = add_movie(db_session, me)
    db_session.commit()
    mine.watched = True
    db_session.commit()
    assert _feed(authenticated_client)["items"] == []


def test_burst_of_plain_adds_collapses_into_one_card(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    for number in range(6):
        add_movie(db_session, dana, title=f"Import {number}", year=2000 + number)
    add_movie(db_session, dana, title="Rated One", year=1999, rating=7.0)
    db_session.commit()
    data = _feed(authenticated_client)
    kinds = [item["type"] for item in data["items"]]
    assert sorted(kinds) == ["burst", "title"]
    burst = next(item for item in data["items"] if item["type"] == "burst")
    assert burst["count"] == 6 and len(burst["titles"]) == 6 and burst["friend"]["username"] == "dana"


def test_sharing_off_hides_my_updates_and_back_on_only_shows_new_ones(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    add_movie(db_session, me, title="Before")
    db_session.commit()

    _as(authenticated_client, dana)
    assert _titles(_feed(authenticated_client)) == [("testuser", "added", "Before")]

    _as(authenticated_client, me)
    off = authenticated_client.post("/api/friend-feed/sharing", json={"sharing": False})
    assert off.status_code == 200 and off.json() == {"sharing": False}
    assert _feed(authenticated_client)["sharing"] is False
    _as(authenticated_client, dana)
    assert _feed(authenticated_client)["items"] == []

    _as(authenticated_client, me)
    setting = db_session.query(models.FriendFeedSetting).filter_by(user_id=me.id).one()
    authenticated_client.post("/api/friend-feed/sharing", json={"sharing": True})
    db_session.refresh(setting)
    add_movie(db_session, me, title="After", added_at=setting.changed_at)
    db_session.commit()
    _as(authenticated_client, dana)
    assert _titles(_feed(authenticated_client)) == [("testuser", "added", "After")]


def test_cheer_notifies_once_and_counts(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, dana, watched=True)
    db_session.commit()
    body = {"friend_id": dana.id, "category": "movies", "item_id": movie.id}

    first = authenticated_client.post("/api/friend-feed/cheer", json=body)
    assert first.status_code == 200, first.text
    assert first.json() == {"cheered": True, "cheers": 1, "created": True}
    again = authenticated_client.post("/api/friend-feed/cheer", json=body)
    assert again.json() == {"cheered": True, "cheers": 1, "created": False}
    note = db_session.query(models.Notification).filter_by(user_id=dana.id, type="friend_feed_cheer").one()
    assert note.message == "testuser cheered you for finishing Interstellar." and note.link == "/#friends-feed"
    item = _feed(authenticated_client)["items"][0]
    assert item["cheers"] == 1 and item["cheered"] is True


def test_cheer_and_save_refuse_strangers_and_private_categories(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    stranger = member(db_session, "stranger")
    theirs = add_movie(db_session, stranger)
    dana.books_private = True
    book = models.Book(user_id=dana.id, title="Dune", author="Frank Herbert")
    db_session.add(book)
    db_session.commit()
    for path in ("/api/friend-feed/cheer", "/api/friend-feed/save"):
        assert authenticated_client.post(path, json={"friend_id": stranger.id, "category": "movies",
                                                     "item_id": theirs.id}).status_code == 404
        assert authenticated_client.post(path, json={"friend_id": dana.id, "category": "books",
                                                     "item_id": book.id}).status_code == 404
        # The item has to belong to the friend named.
        assert authenticated_client.post(path, json={"friend_id": dana.id, "category": "movies",
                                                     "item_id": theirs.id}).status_code == 404
    assert db_session.query(models.Notification).count() == 0


def test_save_copies_public_facts_only_and_can_queue(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, dana, rating=9.5, watched=True, review="Private thoughts",
                      poster_url="https://img.example.com/i.jpg")
    db_session.commit()
    saved = authenticated_client.post("/api/friend-feed/save", json={
        "friend_id": dana.id, "category": "movies", "item_id": movie.id, "next_up": True})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] is True and saved.json()["queued"] is True
    copy = db_session.query(models.Movie).filter_by(user_id=me.id).one()
    assert (copy.title, copy.director, copy.year, copy.poster_url) == (
        "Interstellar", "Christopher Nolan", 2014, "https://img.example.com/i.jpg")
    assert copy.rating is None and copy.review is None and copy.watched is False
    assert db_session.query(models.NextUpItem).filter_by(user_id=me.id, item_id=copy.id).count() == 1
    assert _feed(authenticated_client)["items"][0]["in_library"] is True

    twice = authenticated_client.post("/api/friend-feed/save", json={
        "friend_id": dana.id, "category": "movies", "item_id": movie.id})
    assert twice.json()["created"] is False
    assert db_session.query(models.Movie).filter_by(user_id=me.id).count() == 1
    # Dana's own entry is untouched.
    db_session.refresh(movie)
    assert movie.rating == 9.5 and movie.review == "Private thoughts" and movie.watched is True


def test_pages_with_a_cursor(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    now = datetime.utcnow()
    for number in range(5):
        add_movie(db_session, dana, title=f"Movie {number}", year=2000 + number, rating=6.0,
                  added_at=now - timedelta(days=number, minutes=1))
    db_session.commit()
    first = _feed(authenticated_client, limit=3)
    assert [item["title"] for item in first["items"]] == ["Movie 0", "Movie 1", "Movie 2"]
    assert first["next_before"]
    second = _feed(authenticated_client, limit=3, before=first["next_before"])
    assert [item["title"] for item in second["items"]] == ["Movie 3", "Movie 4"]
    assert second["next_before"] is None
    assert authenticated_client.get("/api/friend-feed", params={"before": "nope"}).status_code == 422


def test_spoiler_flag_travels_with_the_review(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, dana, review="He was the ghost all along")
    db_session.add(models.ReviewSpoiler(category="movie", item_id=movie.id, user_id=dana.id))
    db_session.commit()
    assert _feed(authenticated_client)["items"][0]["spoiler"] is True


def test_events_for_ignores_unknown_old_values():
    movie = models.Movie(title="X", watched=True, user_id=1)
    assert friend_feed.events_for(movie) is None  # not persisted yet


def test_ticking_watched_through_the_library_api_reaches_friends(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = add_movie(db_session, me, added_at=datetime.utcnow() - timedelta(days=90))
    db_session.commit()
    updated = authenticated_client.put(f"/movies/{movie.id}", json={"watched": True, "rating": 8})
    assert updated.status_code == 200, updated.text
    _as(authenticated_client, dana)
    data = _feed(authenticated_client)
    assert _titles(data) == [("testuser", "finished", "Interstellar")]
    assert data["items"][0]["rating"] == 8.0
