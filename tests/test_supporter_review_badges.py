"""The Ko-fi supporter badge follows a member onto their public reviews."""
from datetime import datetime, timedelta

from app import models, supporters
from tests.test_title_pages import LONG_REVIEW, add_movie, member

PAGE = "/titles/movie/interstellar-2014"
CHIP = 'class="supporter-chip'


def _support(db, user, *, days=20, accent=None, show_badge=True):
    db.add(models.Supporter(user_id=user.id, since=datetime(2026, 10, 1), active_until=datetime.utcnow() + timedelta(days=days),
                            accent=accent, show_badge=show_badge))


def _reviewers(db):
    fan = member(db, "fan")
    plain = member(db, "plain")
    movie = add_movie(db, fan, review=LONG_REVIEW, review_public=True)
    add_movie(db, plain, review=LONG_REVIEW + " Plain notes.", review_public=True)
    return fan, plain, movie


def test_title_page_marks_supporters_reviews(client, db_session):
    fan, _, _ = _reviewers(db_session)
    _support(db_session, fan, accent="teal")
    db_session.commit()
    html = client.get(PAGE).text
    assert html.count(CHIP) == 1
    assert ('<a class="supporter-chip supporter-chip--teal" href="/supporters" '
            'title="Supporting OmniTrackr on Ko-fi since October 2026"><span aria-hidden="true">♥</span> Supporter</a>') in html


def test_lapsed_or_hidden_badges_stay_off(client, db_session):
    fan, plain, _ = _reviewers(db_session)
    _support(db_session, fan, days=-1)
    _support(db_session, plain, show_badge=False)
    db_session.commit()
    assert CHIP not in client.get(PAGE).text
    assert supporters.public_badges(db_session, [fan.id, plain.id, None]) == {}


def test_review_directory_and_feed_carry_the_badge(client, db_session):
    fan, plain, _ = _reviewers(db_session)
    _support(db_session, fan, accent="nope")  # an unknown accent falls back to the default color
    db_session.commit()
    assert '<a class="supporter-chip" href="/supporters"' in client.get("/reviews").text
    feed = {r["username"]: r["supporter"] for r in client.get("/api/public/review-feed").json()["reviews"]}
    assert feed == {"fan": {"accent": None, "since": "October 2026"}, "plain": None}


def test_review_page_shows_the_badge_in_the_byline(client, db_session):
    fan, _, movie = _reviewers(db_session)
    _support(db_session, fan, accent="rose")
    db_session.commit()
    html = client.get(f"/reviews/{movie.id}?category=movie").text
    assert 'Reviewed by <strong>fan<a class="supporter-chip supporter-chip--rose"' in html


def test_supporters_page_explains_the_review_badge(client):
    assert "beside your name on every public review" in client.get("/supporters").text
