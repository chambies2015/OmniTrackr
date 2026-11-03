"""For you picks: titles from other members' libraries, ranked for one member."""
from app import auth, models, picked_for_you
from tests.conftest import TestingSessionLocal


def member(db, username, **flags):
    user = models.User(username=username, email=f"{username}@example.com", is_verified=True,
                       hashed_password=auth.get_password_hash("password123"), **flags)
    db.add(user)
    db.flush()
    return user


def movie(db, user, title, year, rating=None, watched=True, poster=None):
    db.add(models.Movie(user_id=user.id, title=title, year=year, rating=rating, watched=watched,
                        poster_url=poster or f"https://img.example/{title.replace(' ', '')}.jpg"))


def book(db, user, title, year, genre, rating=None):
    db.add(models.Book(user_id=user.id, title=title, year=year, genre=genre, rating=rating, read=True))


def me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def neighbours_seed(db, user):
    """Two members who share testuser's taste and both loved Arrival."""
    movie(db, user, "Interstellar", 2014, 9.5)
    movie(db, user, "Dune", 2021, 9)
    for name in ("ana", "ben"):
        other = member(db, name)
        movie(db, other, "Interstellar", 2014, 9)
        movie(db, other, "Dune", 2021, 8.5)
        movie(db, other, "Arrival", 2016, 9.5)
    loner = member(db, "cal")
    movie(db, loner, "Interstellar", 2014, 9)
    movie(db, loner, "Obscure Film", 2001, 10)
    db.commit()


def test_affinity_reads_ratings_against_the_members_own_scale():
    assert picked_for_you.affinity(9, True) == 1.0
    assert picked_for_you.affinity(6, True) == 0
    assert picked_for_you.affinity(2, True) == -1.0
    assert picked_for_you.affinity(None, True) > picked_for_you.affinity(None, False) > 0
    assert picked_for_you.rating_centre([9, 9, 9, 9, 9]) == 7.5
    assert picked_for_you.rating_centre([7]) == 6.0


def test_pick_ids_round_trip():
    assert picked_for_you.pick_id("movie", "arrival", 2016) == "movie/arrival-2016"
    assert picked_for_you.parse_pick_id("movie/arrival-2016") == ("movie", "arrival", 2016)
    assert picked_for_you.parse_pick_id("tv/severance") == ("tv", "severance", None)
    assert picked_for_you.parse_pick_id("movie/blade-runner-2049-2017") == ("movie", "blade-runner-2049", 2017)
    assert picked_for_you.parse_pick_id("movie/" + "a-" * 69 + "a") == ("movie", "a-" * 69 + "a", None)
    assert picked_for_you.parse_pick_id("blog/arrival") is None
    assert picked_for_you.parse_pick_id("movie/../etc") is None


def test_taste_neighbours_suggest_what_they_loved(authenticated_client, db_session):
    neighbours_seed(db_session, me(db_session))
    data = authenticated_client.get("/api/for-you/picks").json()
    assert data["state"] == "ready"
    first = data["picks"][0]
    assert first["title"] == "Arrival" and first["source"] == "taste"
    # Interstellar is tracked more widely (cal has it too), so Dune explains the pick better.
    assert first["reason"] == "Because you rated Dune 9/10"
    assert first["detail"] == "Saved by 2 members with similar taste"
    assert first["url"] == "/titles/movie/arrival-2016"
    titles = [pick["title"] for pick in data["picks"]]
    # One member's favourite never becomes a pick, and owned titles never come back.
    assert "Obscure Film" not in titles
    assert "Interstellar" not in titles and "Dune" not in titles


def test_private_categories_and_the_editors_account_never_feed_picks(authenticated_client, db_session):
    user = me(db_session)
    movie(db_session, user, "Interstellar", 2014, 9.5)
    for name, flags in (("ana", {"movies_private": True}), ("ben", {})):
        other = member(db_session, name, **flags)
        movie(db_session, other, "Interstellar", 2014, 9)
        movie(db_session, other, "Arrival", 2016, 9.5)
    editors = member(db_session, "omnitrackr_editors")
    movie(db_session, editors, "Interstellar", 2014, 9)
    movie(db_session, editors, "Arrival", 2016, 9.5)
    db_session.commit()
    data = authenticated_client.get("/api/for-you/picks").json()
    assert "Arrival" not in [pick["title"] for pick in data["picks"]]


def test_genres_suggest_titles_in_formats_without_neighbours(authenticated_client, db_session):
    user = me(db_session)
    book(db_session, user, "The Hobbit", 1937, "Fantasy, Adventure", 9)
    for name in ("ana", "ben"):
        other = member(db_session, name)
        book(db_session, other, "Mistborn", 2006, "Fantasy, Adventure")
        book(db_session, other, "Gone Girl", 2012, "Thriller, Mystery")
    db_session.commit()
    data = authenticated_client.get("/api/for-you/picks").json()
    by_title = {pick["title"]: pick for pick in data["picks"]}
    assert by_title["Mistborn"]["source"] == "genre"
    assert by_title["Mistborn"]["reason"] == "Shares Fantasy and Adventure with The Hobbit"
    titles = list(by_title)
    assert titles.index("Mistborn") < titles.index("Gone Girl") if "Gone Girl" in titles else True


def test_new_members_get_the_most_tracked_titles(authenticated_client, db_session):
    for name in ("ana", "ben", "cal"):
        movie(db_session, member(db_session, name), "Arrival", 2016, 8)
    db_session.commit()
    data = authenticated_client.get("/api/for-you/picks").json()
    assert data["state"] == "empty"
    assert data["picks"][0]["title"] == "Arrival"
    assert data["picks"][0]["source"] == "popular"
    assert data["picks"][0]["average"] == 8.0 and data["picks"][0]["detail"] == "Tracked by 3 members"


def test_not_for_me_hides_a_pick_until_restored(authenticated_client, db_session):
    neighbours_seed(db_session, me(db_session))
    assert authenticated_client.post("/api/for-you/picks/dismiss", json={"id": "movie/arrival-2016"}).status_code == 200
    assert authenticated_client.post("/api/for-you/picks/dismiss", json={"id": "movie/arrival-2016"}).status_code == 200
    assert db_session.query(models.ForYouDismissal).count() == 1
    titles = [pick["title"] for pick in authenticated_client.get("/api/for-you/picks").json()["picks"]]
    assert "Arrival" not in titles
    authenticated_client.post("/api/for-you/picks/restore", json={"id": "movie/arrival-2016"})
    titles = [pick["title"] for pick in authenticated_client.get("/api/for-you/picks").json()["picks"]]
    assert "Arrival" in titles
    assert authenticated_client.post("/api/for-you/picks/dismiss", json={"id": "nope"}).status_code == 400


def test_saving_a_pick_copies_public_details_only(authenticated_client, db_session):
    neighbours_seed(db_session, me(db_session))
    db_session.query(models.Movie).filter_by(title="Arrival").update({"director": "Denis Villeneuve"})
    db_session.commit()
    response = authenticated_client.post("/api/for-you/picks/add", json={"id": "movie/arrival-2016"})
    assert response.json()["state"] == "created"
    saved = db_session.query(models.Movie).filter_by(user_id=me(db_session).id, title="Arrival").one()
    assert saved.director == "Denis Villeneuve" and saved.year == 2016
    assert saved.rating is None and saved.watched is False and saved.review is None
    again = authenticated_client.post("/api/for-you/picks/add", json={"id": "movie/arrival-2016"})
    assert again.json()["state"] == "existing"
    titles = [pick["title"] for pick in authenticated_client.get("/api/for-you/picks").json()["picks"]]
    assert "Arrival" not in titles
    missing = authenticated_client.post("/api/for-you/picks/add", json={"id": "movie/obscure-film-2001"})
    assert missing.status_code == 404


def test_picks_need_sign_in(client):
    assert client.get("/api/for-you/picks").status_code == 401


def test_rows_group_picks_by_the_title_behind_them(db_session):
    user = member(db_session, "me")
    movie(db_session, user, "Interstellar", 2014, 10)
    for name in ("ana", "ben", "cal"):
        other = member(db_session, name)
        movie(db_session, other, "Interstellar", 2014, 9)
        for title, year in (("Arrival", 2016), ("Contact", 1997), ("Gravity", 2013)):
            movie(db_session, other, title, year, 9)
    db_session.commit()
    data = picked_for_you.picks_for(db_session, user.id)
    assert data["rows"][0]["title"] == "Interstellar"
    assert len(data["rows"][0]["picks"]) == 3
