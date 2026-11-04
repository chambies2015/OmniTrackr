"""The "Share your reviews" home card: private reviews a member can put on title pages (Nov 2026)."""
from datetime import datetime, timedelta

from app import models, review_inbox
from app.routers import site_stats
from tests.test_title_pages import ESSAY, LONG_REVIEW, add_movie, member

API = "/api/review-inbox"
SHORT = "Loved it, would watch again."


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _items(client):
    response = client.get(API)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()


def test_lists_only_private_reviews_that_would_show_on_a_title_page(authenticated_client, db_session):
    me = _me(db_session)
    first = add_movie(db_session, me, review=ESSAY)
    add_movie(db_session, me, title="Arrival", year=2016, review=SHORT)  # too short for a title page
    add_movie(db_session, me, title="Heat", year=1995, review=LONG_REVIEW, review_public=True)  # already public
    add_movie(db_session, me, title="Alien", year=1979, review="Visit my site www.example.com " + LONG_REVIEW)  # unsafe
    add_movie(db_session, me, title="Tenet", year=2020)  # no review
    add_movie(db_session, member(db_session, "other"), title="Dune", year=2021, review=LONG_REVIEW)  # someone else's
    db_session.commit()

    data = _items(authenticated_client)
    assert data["total"] == 1
    [item] = data["items"]
    assert item["id"] == first.id and item["category"] == "movie" and item["library_category"] == "movies"
    assert item["path"] == "/titles/movie/interstellar-2014"
    assert item["standalone"] is True and item["first"] is True and item["private_list"] is False
    assert item["version"] == review_inbox.content_hash(ESSAY)
    assert len(item["excerpt"]) <= review_inbox.EXCERPT_CHARS + 1 and item["excerpt"].endswith("…")


def test_first_review_on_the_page_comes_first(authenticated_client, db_session):
    me = _me(db_session)
    add_movie(db_session, me, review=ESSAY)  # Interstellar already has a public review from someone else
    add_movie(db_session, member(db_session, "other"), review=LONG_REVIEW, review_public=True)
    add_movie(db_session, me, title="Arrival", year=2016, review=LONG_REVIEW)
    db_session.commit()

    items = _items(authenticated_client)["items"]
    assert [(item["title"], item["first"]) for item in items] == [("Arrival", True), ("Interstellar", False)]


def test_sharing_makes_the_review_public_on_its_title_page(authenticated_client, db_session):
    me = _me(db_session)
    movie = add_movie(db_session, me, review=LONG_REVIEW)
    db_session.commit()
    [item] = _items(authenticated_client)["items"]

    page = authenticated_client.get("/titles/movie/interstellar-2014").text
    assert "No public reviews yet" in page

    response = authenticated_client.post(f"{API}/share", json={
        "category": "movie", "item_id": movie.id, "version": item["version"], "spoilers": True})
    assert response.status_code == 200
    body = response.json()
    assert body["shared"] is True and body["path"] == "/titles/movie/interstellar-2014"
    assert body["review_url"] == f"/reviews/{movie.id}?category=movie"

    db_session.expire_all()
    assert db_session.get(models.Movie, movie.id).review_public is True
    assert db_session.get(models.Movie, movie.id).review == LONG_REVIEW  # text untouched
    assert db_session.query(models.ReviewSpoiler).filter_by(category="movie", item_id=movie.id).count() == 1
    choice = db_session.query(models.ReviewShareChoice).one()
    assert (choice.user_id, choice.choice) == (me.id, "shared")

    page = authenticated_client.get("/titles/movie/interstellar-2014").text
    assert "Interstellar works because" in page[page.index('id="community-title"'):]
    assert _items(authenticated_client)["total"] == 0


def test_a_review_shared_here_and_made_private_later_is_not_offered_again(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=LONG_REVIEW)
    db_session.commit()
    version = review_inbox.content_hash(LONG_REVIEW)
    authenticated_client.post(f"{API}/share", json={"category": "movie", "item_id": movie.id, "version": version})
    db_session.expire_all()
    db_session.get(models.Movie, movie.id).review_public = False  # turned off in the library editor
    db_session.commit()
    assert _items(authenticated_client)["total"] == 0


def test_reviews_that_were_public_before_are_left_alone(authenticated_client, db_session):
    me = _me(db_session)
    marked = add_movie(db_session, me, review=LONG_REVIEW)
    reported = add_movie(db_session, me, title="Arrival", year=2016, review=LONG_REVIEW)
    db_session.add(models.ReviewReaction(category="movie", item_id=marked.id, visitor_hash="v1"))
    db_session.add(models.PublicReviewState(user_id=me.id, category="movie", item_id=reported.id, content_hash="x"))
    db_session.commit()
    assert _items(authenticated_client)["total"] == 0


def test_keep_private_holds_until_the_review_is_rewritten(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=LONG_REVIEW)
    db_session.commit()
    version = _items(authenticated_client)["items"][0]["version"]
    response = authenticated_client.post(f"{API}/keep", json={"category": "movie", "item_id": movie.id, "version": version})
    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(models.Movie, movie.id).review_public is False
    assert _items(authenticated_client)["total"] == 0

    db_session.get(models.Movie, movie.id).review = LONG_REVIEW + " Rewatched it this week and liked it even more."
    db_session.commit()
    assert _items(authenticated_client)["total"] == 1


def test_undo_takes_back_a_share_or_a_keep(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=LONG_REVIEW)
    db_session.commit()
    version = review_inbox.content_hash(LONG_REVIEW)
    ref = {"category": "movie", "item_id": movie.id}
    authenticated_client.post(f"{API}/share", json={**ref, "version": version})
    response = authenticated_client.post(f"{API}/undo", json=ref)
    assert response.status_code == 200 and response.json() == {"undone": True, "public": False}
    db_session.expire_all()
    assert db_session.get(models.Movie, movie.id).review_public is False
    assert db_session.query(models.ReviewShareChoice).count() == 0
    assert _items(authenticated_client)["total"] == 1

    authenticated_client.post(f"{API}/keep", json={**ref, "version": version})
    assert authenticated_client.post(f"{API}/undo", json=ref).json()["undone"] is True
    assert _items(authenticated_client)["total"] == 1
    assert authenticated_client.post(f"{API}/undo", json=ref).status_code == 404


def test_a_review_edited_elsewhere_is_not_shared_blind(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=LONG_REVIEW)
    db_session.commit()
    stale = review_inbox.content_hash(LONG_REVIEW)
    db_session.get(models.Movie, movie.id).review = LONG_REVIEW + " Added a spoiler about the ending."
    db_session.commit()
    response = authenticated_client.post(f"{API}/share", json={"category": "movie", "item_id": movie.id, "version": stale})
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(models.Movie, movie.id).review_public is False


def test_members_cannot_share_someone_elses_review(authenticated_client, db_session):
    theirs = add_movie(db_session, member(db_session, "other"), review=LONG_REVIEW)
    db_session.commit()
    payload = {"category": "movie", "item_id": theirs.id, "version": review_inbox.content_hash(LONG_REVIEW)}
    assert authenticated_client.post(f"{API}/share", json=payload).status_code == 404
    assert authenticated_client.post(f"{API}/keep", json=payload).status_code == 404
    db_session.expire_all()
    assert db_session.get(models.Movie, theirs.id).review_public is False
    assert db_session.query(models.ReviewShareChoice).count() == 0


def test_too_short_reviews_are_refused(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=SHORT)
    db_session.commit()
    payload = {"category": "movie", "item_id": movie.id, "version": review_inbox.content_hash(SHORT)}
    assert authenticated_client.post(f"{API}/share", json=payload).status_code == 422


def test_bad_input_is_rejected(authenticated_client):
    assert authenticated_client.post(f"{API}/share", json={"category": "nope", "item_id": 1, "version": "a" * 64}).status_code == 422
    assert authenticated_client.post(f"{API}/share", json={"category": "movie", "item_id": 0, "version": "a" * 64}).status_code == 422
    assert authenticated_client.post(f"{API}/share", json={"category": "movie", "item_id": 1, "version": "<b>"}).status_code == 422


def test_signed_out_visitors_get_nothing(client):
    assert client.get(API).status_code == 401
    assert client.post(f"{API}/share", json={"category": "movie", "item_id": 1, "version": "a" * 64}).status_code in (401, 403)


def test_private_list_is_flagged_and_not_linked_before_sharing(authenticated_client, db_session):
    me = _me(db_session)
    me.movies_private = True
    add_movie(db_session, me, review=LONG_REVIEW)
    db_session.commit()
    [item] = _items(authenticated_client)["items"]
    assert item["private_list"] is True


def test_other_formats_are_listed_too(authenticated_client, db_session):
    me = _me(db_session)
    db_session.add(models.Book(user_id=me.id, title="Piranesi", author="Susanna Clarke", year=2020, review=LONG_REVIEW.replace("Interstellar", "Piranesi")))
    db_session.add(models.Anime(user_id=me.id, title="Frieren", year=2023, review=LONG_REVIEW.replace("Interstellar", "Frieren")))
    db_session.commit()
    items = _items(authenticated_client)["items"]
    assert {(item["category"], item["path"]) for item in items} == {
        ("book", "/titles/book/piranesi-2020"), ("anime", "/titles/anime/frieren-2023")}


def test_deleting_the_library_entry_clears_its_answer(authenticated_client, db_session):
    movie = add_movie(db_session, _me(db_session), review=LONG_REVIEW)
    db_session.commit()
    authenticated_client.post(f"{API}/keep", json={"category": "movie", "item_id": movie.id,
                                                   "version": review_inbox.content_hash(LONG_REVIEW)})
    assert authenticated_client.delete(f"/movies/{movie.id}").status_code in (200, 204)
    assert db_session.query(models.ReviewShareChoice).count() == 0


def test_site_stats_counts_answers_and_waiting_reviews(db_session):
    a, b, c = member(db_session, "a"), member(db_session, "b"), member(db_session, "c")
    shared = add_movie(db_session, a, review=LONG_REVIEW, review_public=True)
    kept = add_movie(db_session, b, review=LONG_REVIEW)
    add_movie(db_session, c, review=LONG_REVIEW)  # waiting
    add_movie(db_session, c, title="Arrival", year=2016, review=SHORT)  # too short to count
    old = datetime.utcnow() - timedelta(days=60)
    db_session.add_all([
        models.ReviewShareChoice(user_id=a.id, category="movie", item_id=shared.id, choice="shared", content_hash="x"),
        models.ReviewShareChoice(user_id=b.id, category="movie", item_id=kept.id, choice="kept", content_hash="x", created_at=old),
    ])
    db_session.commit()
    assert review_inbox.stats(db_session, 30) == {"shared": 1, "kept": 0, "sharers": 1, "waiting": 1, "waiting_members": 1}
    assert site_stats._review_inbox(db_session, 30, datetime.utcnow())["waiting"] == 1


def test_dashboard_has_the_card_and_script(authenticated_client):
    html = authenticated_client.get("/").text
    assert 'id="reviewInbox"' in html and 'id="reviewInboxList"' in html
    assert "/static/review-inbox.js?v=" in html and "/static/review-inbox.css?v=" in html
