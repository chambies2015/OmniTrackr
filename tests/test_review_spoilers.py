"""Members can mark a review as containing spoilers (Oct 20 2026)."""
import json
import re

from app import landing_proof, models, review_spoilers, review_spotlight
from tests.test_title_pages import LONG_REVIEW, add_movie, member

PAGE = "/titles/movie/interstellar-2014"
API = "/api/titles/movie/interstellar-2014"
SPOILER_TEXT = LONG_REVIEW + " The twist is that the ghost was Cooper all along."


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def flag(db, movie):
    db.add(models.ReviewSpoiler(category="movie", item_id=movie.id, user_id=movie.user_id))
    db.commit()


def json_ld(html):
    return [json.loads(block) for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S)]


def test_writer_marks_spoilers_from_the_title_page(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    assert 'id="titleReviewSpoilers" name="spoilers" type="checkbox"' in authenticated_client.get(PAGE).text
    response = authenticated_client.put(f"{API}/review", json={"review": SPOILER_TEXT, "public": True, "spoilers": True})
    assert response.status_code == 200
    mine = db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).one()
    assert db_session.query(models.ReviewSpoiler).filter_by(category="movie", item_id=mine.id, user_id=mine.user_id).count() == 1
    assert authenticated_client.get(f"{API}/my-review").json()["spoilers"] is True

    # Leaving the field out keeps the flag; sending false clears it.
    authenticated_client.put(f"{API}/review", json={"review": SPOILER_TEXT + " Edited.", "expected_review": SPOILER_TEXT})
    assert authenticated_client.get(f"{API}/my-review").json()["spoilers"] is True
    authenticated_client.put(f"{API}/review", json={"review": SPOILER_TEXT, "expected_review": SPOILER_TEXT + " Edited.",
                                                    "spoilers": False})
    assert authenticated_client.get(f"{API}/my-review").json()["spoilers"] is False
    assert db_session.query(models.ReviewSpoiler).count() == 0


def test_title_page_folds_spoiler_reviews_and_keeps_them_out_of_snippets(client, db_session):
    movie = add_movie(db_session, member(db_session, "a"), review=SPOILER_TEXT, review_public=True)
    add_movie(db_session, member(db_session, "b"), review=LONG_REVIEW + " No twists here.", review_public=True)
    flag(db_session, movie)
    html = client.get(PAGE).text
    section = html[html.index('id="community-title"'):]
    assert '<details class="review-spoiler">' in section
    folded = section[section.index('<details class="review-spoiler">'):]
    assert folded.index("Interstellar works") < folded.index("</details>")
    bodies = [review["reviewBody"] for block in json_ld(html) for review in block.get("review", [])]
    assert bodies and not any("ghost was Cooper" in body for body in bodies)


def test_review_page_folds_the_text_and_hides_it_from_meta(client, db_session):
    movie = add_movie(db_session, member(db_session, "a"), review=SPOILER_TEXT, review_public=True)
    flag(db_session, movie)
    html = client.get(f"/reviews/{movie.id}?category=movie").text
    assert '<details class="review-spoiler">' in html and "ghost was Cooper" in html
    description = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    assert "This review contains spoilers." in description and "Interstellar works" not in description
    assert all("reviewBody" not in block for block in json_ld(html) if block.get("@type") == "Review")


def test_listing_and_api_carry_the_flag(client, db_session):
    movie = add_movie(db_session, member(db_session, "a"), review=SPOILER_TEXT, review_public=True)
    flag(db_session, movie)
    assert '<details class="review-spoiler">' in client.get("/reviews").text
    feed = client.get("/api/public/review-feed").json()["reviews"]
    assert feed[0]["spoilers"] is True
    assert client.get(f"/api/public/reviews/{movie.id}?category=movie").json()["spoilers"] is True


def test_unflagged_reviews_render_as_before(client, db_session):
    movie = add_movie(db_session, member(db_session, "a"), review=LONG_REVIEW, review_public=True)
    db_session.commit()
    assert "review-spoiler" not in client.get(PAGE).text.split('id="community-title"')[1].split("</section>")[0]
    assert '<details class="review-spoiler">' not in client.get(f"/reviews/{movie.id}?category=movie").text
    assert client.get("/api/public/review-feed").json()["reviews"][0]["spoilers"] is False


def test_a_flag_left_by_another_member_is_ignored(db_session):
    a, b = member(db_session, "a"), member(db_session, "b")
    movie = add_movie(db_session, a, review=SPOILER_TEXT, review_public=True)
    db_session.add(models.ReviewSpoiler(category="movie", item_id=movie.id, user_id=b.id))
    db_session.commit()
    review = {"category": "movie", "id": movie.id, "user_id": a.id}
    assert review_spoilers.attach(db_session, [review])[0]["spoilers"] is False


def test_teasers_skip_spoiler_reviews():
    spoiler = {"category": "movie", "id": 1, "user_id": 1, "title": "Arrival", "search_ready": True, "spoilers": True,
               "review": LONG_REVIEW}
    clean = dict(spoiler, id=2, user_id=2, spoilers=False)
    assert landing_proof.pick_reviews([spoiler, clean]) == [clean]
    assert review_spotlight.choose([spoiler], {("movie", 1): 5}) is None


def test_finish_modal_review_can_be_marked(authenticated_client, test_movie_data, db_session):
    movie = authenticated_client.post("/movies/", json={**test_movie_data, "review": None}).json()
    moment = authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": movie["id"]}).json()
    response = authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                         json={"review": SPOILER_TEXT, "public": True, "spoilers": True})
    assert response.status_code == 200
    assert db_session.query(models.ReviewSpoiler).filter_by(category="movie", item_id=movie["id"]).count() == 1


def test_profile_folds_spoiler_reviews(client, db_session):
    user = member(db_session, "spoilerfan")
    movie = add_movie(db_session, user, review=SPOILER_TEXT, review_public=True)
    flag(db_session, movie)
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    html = client.get("/u/spoilerfan").text
    assert '<details class="review-spoiler">' in html and "Interstellar works" in html
