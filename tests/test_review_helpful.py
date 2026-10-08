"""Review "Helpful" marks, writer notifications and Review of the week (Oct 7)."""
from datetime import datetime, timedelta

import pytest

from app import auth, digest, landing_proof, models, review_spotlight
from app.routers import reviews as reviews_router
from tests.test_review_discovery import STANDALONE

LONG = STANDALONE + " " + " ".join(["Another careful sentence about pacing, tone and who might enjoy it most."] * 14)


def member(db, name, active=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_active=active, is_verified=True)
    db.add(user)
    db.flush()
    return user


def review(db, user, title="Arrival", text=STANDALONE, public=True):
    item = models.Movie(user_id=user.id, title=title, review=text, review_public=public, rating=9)
    db.add(item)
    db.flush()
    return item


def mark(client, item, category="movie"):
    return client.post(f"/api/public/reviews/{category}/{item.id}/helpful")


def notes(db, user):
    return db.query(models.Notification).filter_by(user_id=user.id, type="review_helpful").order_by(models.Notification.id).all()


# ---------------------------------------------------------------- marking

def test_one_mark_per_browser_and_the_writer_hears_about_the_first(client, db_session):
    writer = member(db_session, "writer")
    item = review(db_session, writer)
    db_session.commit()
    first = mark(client, item)
    assert first.status_code == 200 and first.json()["count"] == 1
    assert first.json()["label"] == "1 person found this helpful"
    assert first.headers["cache-control"] == "no-store"
    assert mark(client, item).json()["count"] == 1          # same browser again: no double count
    messages = [n.message for n in notes(db_session, writer)]
    assert messages == ['Someone found your review of "Arrival" helpful. Thanks for writing it!']


def test_writers_are_notified_only_at_milestones(client, db_session):
    writer = member(db_session, "writer")
    item = review(db_session, writer)
    db_session.commit()
    for _ in range(4):
        client.cookies.clear()                                # four different browsers
        mark(client, item)
    assert [n.message.split(" ", 2)[:2] for n in notes(db_session, writer)] == [["Someone", "found"], ["3", "people"]]


def test_no_ip_or_user_is_stored(client, db_session):
    item = review(db_session, member(db_session, "writer"))
    db_session.commit()
    mark(client, item)
    row = db_session.query(models.ReviewReaction).one()
    assert set(c.name for c in models.ReviewReaction.__table__.columns) == {"id", "category", "item_id", "visitor_hash", "created_at"}
    assert len(row.visitor_hash) == 64


def test_private_short_hidden_and_unknown_reviews_cannot_be_marked(client, db_session):
    writer = member(db_session, "writer")
    private = review(db_session, writer, title="Private", public=False)
    short = review(db_session, writer, title="Short", text="Too short.")
    gone_writer = member(db_session, "gone", active=False)
    gone = review(db_session, gone_writer, title="Gone")
    db_session.commit()
    for item in (private, short, gone):
        assert mark(client, item).status_code == 404
    assert client.post("/api/public/reviews/movie/99999/helpful").status_code == 404
    assert client.post("/api/public/reviews/podcast/1/helpful").status_code == 400
    assert db_session.query(models.ReviewReaction).count() == 0


def test_suspended_reviews_cannot_be_marked(client, db_session):
    writer = member(db_session, "writer")
    item = review(db_session, writer)
    db_session.add(models.PublicReviewState(user_id=writer.id, category="movie", item_id=item.id, report_count=3,
                                            content_hash=reviews_router._review_content_hash("movie", item.id, item.review),
                                            suspended_at=datetime.utcnow()))
    db_session.commit()
    assert mark(client, item).status_code == 404


def test_writers_cannot_mark_their_own_review(client, db_session):
    writer = member(db_session, "writer")
    item = review(db_session, writer)
    db_session.commit()
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(writer))
    response = mark(client, item)
    assert response.status_code == 403
    assert db_session.query(models.ReviewReaction).count() == 0


def test_review_page_shows_the_button_and_count(client, db_session):
    item = review(db_session, member(db_session, "writer"))
    db_session.commit()
    html = client.get(f"/reviews/{item.id}?category=movie").text
    assert "data-review-helpful" in html and "Be the first to mark this helpful" in html
    mark(client, item)
    assert "1 person found this helpful" in client.get(f"/reviews/{item.id}?category=movie").text


def test_counts_are_grouped_per_review(client, db_session):
    a, b = review(db_session, member(db_session, "ann")), review(db_session, member(db_session, "ben"), title="Dune")
    db_session.commit()
    mark(client, a)
    client.cookies.clear()
    mark(client, a)
    mark(client, b)
    assert reviews_router.review_helpful_counts(db_session, [("movie", a.id), ("movie", b.id)]) == {
        ("movie", a.id): 2, ("movie", b.id): 1}
    assert reviews_router.review_helpful_counts(db_session, []) == {}


# ---------------------------------------------------------------- review of the week

def row(i, user, words=40, ready=True):
    return {"id": i, "category": "movie", "title": f"T{i}", "user_id": user, "search_ready": ready, "review": "word " * words}


def test_spotlight_prefers_most_marked_this_week():
    reviews = [row(3, 1), row(2, 2, words=200), row(1, 3)]
    assert review_spotlight.choose(reviews, {("movie", 1): 2, ("movie", 3): 1})["id"] == 1


def test_spotlight_falls_back_to_newest_thorough_review():
    reviews = [row(3, 1, words=40), row(2, 2, words=200), row(1, 3, words=300)]
    assert review_spotlight.choose(reviews, {})["id"] == 2
    assert review_spotlight.choose([row(5, 1, words=40)], {})["id"] == 5
    assert review_spotlight.choose([row(5, 1, ready=False)], {}) is None


def test_spotlight_ignores_marks_older_than_a_week(client, db_session):
    old = review(db_session, member(db_session, "old"), title="Old Favorite", text=LONG)
    new = review(db_session, member(db_session, "new"), title="Fresh", text=STANDALONE)
    db_session.commit()
    db_session.add(models.ReviewReaction(category="movie", item_id=new.id, visitor_hash="a" * 64))
    db_session.add(models.ReviewReaction(category="movie", item_id=old.id, visitor_hash="b" * 64,
                                         created_at=datetime.utcnow() - timedelta(days=10)))
    db_session.commit()
    assert review_spotlight.build(db_session)["title"] == "Fresh"


def test_homepage_badges_the_review_of_the_week(client, db_session, monkeypatch):
    review(db_session, member(db_session, "ann"), title="Arrival", text=LONG)
    review(db_session, member(db_session, "ben"), title="Dune")
    db_session.commit()
    landing_proof.clear_cache()
    monkeypatch.setattr(landing_proof, "homepage_section", lambda: landing_proof.build(db_session))
    html = client.get("/").text
    assert html.count("Review of the week") == 1
    first_card = html.split('<li class="lp-voice')[1]
    assert "Review of the week" in first_card and "Arrival" in first_card


def test_weekly_email_includes_the_spotlight_but_it_never_forces_a_send():
    spotlight = {"id": 4, "category": "movie", "title": "Arrival <i>", "username": "ann", "review": "word " * 120}
    report = {"matches": [{"title": "Severance", "label": "TV", "date": None, "url": "/x", "reason": "In your library"}], "popular": []}
    subject, html, text = digest.build_digest("dan", report, "https://x/unsub", spotlight)
    assert "Review of the week" in html and "Arrival &lt;i&gt;" in html and "/reviews/4?category=movie" in html
    assert "Review of the week" in text and "…" in html
    assert digest.build_digest("dan", {"matches": [], "popular": []}, "u", spotlight) is None
