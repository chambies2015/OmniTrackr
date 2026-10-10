"""Writing a review from a public title page, and the prompts that ask for one."""
from app import models
from tests.test_title_pages import LONG_REVIEW, add_movie, member

PAGE = "/titles/movie/interstellar-2014"
API = "/api/titles/movie/interstellar-2014"


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def test_signed_out_visitors_are_asked_to_review_first(client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    html = client.get(PAGE).text
    assert 'id="write-review"' in html and "Be the first to review Interstellar" in html
    assert 'href="#write-review">Write the first review</a>' in html
    assert "/?next=%2Ftitles%2Fmovie%2Finterstellar-2014%23write-review#landing-auth" in html
    assert "data-title-review" not in html  # the form is for members only


def test_pages_with_reviews_ask_for_another(client, db_session):
    add_movie(db_session, member(db_session, "a"), review=LONG_REVIEW, review_public=True)
    db_session.commit()
    html = client.get(PAGE).text
    assert "Add your review of Interstellar" in html and "Be the first" not in html


def test_members_get_the_form(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    html = authenticated_client.get(PAGE).text
    assert 'data-title-review data-title-kind="movie" data-title-slug="interstellar-2014"' in html
    assert 'id="titleReviewText"' in html and 'id="titleReviewPublic" name="public" type="checkbox" checked' in html


def test_review_adds_the_title_and_publishes(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"), poster_url="https://img.example/p.jpg", review="their private notes")
    db_session.commit()
    assert authenticated_client.get(f"{API}/my-review").json() == {"in_library": False, "review": "", "rating": None, "public": True}

    response = authenticated_client.put(f"{API}/review", json={"review": f"  {LONG_REVIEW}  ", "rating": 8.66, "public": True})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "created" and data["public"] and data["listed"] and data["standalone"]
    mine = db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).one()
    assert (mine.review, mine.rating, mine.review_public, mine.poster_url) == (LONG_REVIEW, 8.7, True, "https://img.example/p.jpg")
    assert data["review_url"] == f"/reviews/{mine.id}?category=movie"
    assert authenticated_client.get(f"{API}/my-review").json() == {"in_library": True, "review": LONG_REVIEW, "rating": 8.7, "public": True}

    # The review now shows on the page and makes it indexable.
    authenticated_client.cookies.clear()
    authenticated_client.headers = {}
    html = authenticated_client.get(PAGE).text
    assert "Interstellar works because" in html and "index, follow" in html


def test_editing_keeps_the_existing_entry_and_rating(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    mine = add_movie(db_session, _me(db_session), rating=9, watched=True, review="Loved it.", review_public=False)
    db_session.commit()
    assert authenticated_client.get(f"{API}/my-review").json()["review"] == "Loved it."

    response = authenticated_client.put(f"{API}/review", json={"review": "Loved it. Even better the second time.", "public": False,
                                                                 "expected_review": "Loved it."})
    assert response.status_code == 200 and response.json()["state"] == "existing" and not response.json()["public"]
    db_session.refresh(mine)
    assert (mine.review, mine.rating, mine.watched, mine.review_public) == ("Loved it. Even better the second time.", 9, True, False)
    assert db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).count() == 1


def test_never_overwrites_a_review_it_did_not_load(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    mine = add_movie(db_session, _me(db_session), review="Written in the dashboard.")
    db_session.commit()
    response = authenticated_client.put(f"{API}/review", json={"review": "A different text", "expected_review": ""})
    assert response.status_code == 409
    db_session.refresh(mine)
    assert mine.review == "Written in the dashboard."


def test_validation_and_auth(client, authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    assert authenticated_client.put(f"{API}/review", json={"review": "   "}).status_code == 422
    assert authenticated_client.put(f"{API}/review", json={"review": "Fine", "rating": 11}).status_code == 422
    assert authenticated_client.put("/api/titles/movie/no-such-title-1999/review", json={"review": "Fine"}).status_code == 404
    assert authenticated_client.get("/api/titles/movie/no-such-title-1999/my-review").status_code == 404
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    assert client.put(f"{API}/review", json={"review": "Fine"}).status_code == 401
    assert client.get(f"{API}/my-review").status_code == 401


def test_finish_flow_links_to_the_title_page(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), watched=True)
    db_session.commit()
    moment = authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": movie.id}).json()
    review = "A patient, moving film about family and time. The docking scene alone is worth it."
    result = authenticated_client.post(f"/completion-moments/{moment['id']}/review", json={"review": review, "public": True}).json()
    assert result["listed"] and result["title_url"] == "/titles/movie/interstellar-2014"
    private = add_movie(db_session, _me(db_session), title="Arrival", year=2016, watched=True)
    db_session.commit()
    moment = authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": private.id}).json()
    result = authenticated_client.post(f"/completion-moments/{moment['id']}/review", json={"review": review, "public": False}).json()
    assert result["title_url"] is None
