"""Thin-page audit, October 20 2026 (AdSense "low value content").

A crawl of every public URL found two page types that search engines could index
with very little original writing on them:
- a review's own page when the review is only 35-150 words long, and
- a public profile that has only a short bio and a grid of rated titles.
Both pages still load; they are noindex and stay out of the sitemap.
"""
from datetime import datetime

from app import auth, models

SHORT_REVIEW = (
    "Arrival is patient and strange in the best way. The language scenes are the heart of it, and the "
    "score makes every quiet moment feel heavy. I wanted a little more from the side characters, but the "
    "ending changed how I saw everything before it."
)
SENTENCES = (
    "The film opens on a quiet memory and only later tells you what that memory really is.",
    "Amy Adams plays the linguist with a calm focus that makes every small breakthrough feel earned.",
    "The shells are designed as plain grey stones, which makes them stranger than any glowing ship.",
    "Most of the tension comes from people misreading each other rather than from any alien threat.",
    "Johann Johannsson's score uses voices and low strings so that the sound itself feels foreign.",
    "The military subplot is the weakest part, since those characters exist mostly to raise the stakes.",
    "On a second viewing the editing reads differently, and scenes I took as flashbacks change meaning.",
    "It asks whether you would choose a life knowing exactly how it ends, and it does not answer for you.",
    "Bradford Young shoots the valley in overcast light, so nothing in the frame ever looks triumphant.",
    "Jeremy Renner is fine, though his role is mostly to stand beside her and react to what she finds.",
    "The heptapod writing is beautiful on its own terms, circles of ink that hold a whole sentence at once.",
    "I recommend it to anyone who likes science fiction that is more interested in grief than in battles.",
)
LONG_REVIEW = " ".join(SENTENCES)


def member(db, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime(2025, 3, 4))
    db.add(user)
    db.flush()
    return user


def review(db, user, text, title="Arrival"):
    movie = models.Movie(user_id=user.id, title=title, director="Denis Villeneuve", year=2016, rating=9,
                         watched=True, review=text, review_public=True)
    db.add(movie)
    db.commit()
    return movie


def test_short_review_page_loads_but_is_noindex_and_off_the_sitemap(client, db_session):
    movie = review(db_session, member(db_session, "brief"), SHORT_REVIEW)
    response = client.get(f"/reviews/{movie.id}?category=movie")
    assert response.status_code == 200
    assert response.headers.get("x-robots-tag") == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow">' in response.text
    assert f"/reviews/{movie.id}?category=movie</loc>" not in client.get("/sitemap.xml").text


def test_long_review_page_is_indexed_and_in_the_sitemap(client, db_session):
    movie = review(db_session, member(db_session, "thorough"), LONG_REVIEW)
    response = client.get(f"/reviews/{movie.id}?category=movie")
    assert response.status_code == 200
    assert "x-robots-tag" not in response.headers
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in response.text
    assert f"/reviews/{movie.id}?category=movie</loc>" in client.get("/sitemap.xml").text


def test_short_reviews_still_count_toward_the_review_listing(client, db_session):
    for index, name in enumerate(("one", "two", "three")):
        review(db_session, member(db_session, name), SHORT_REVIEW, title=f"Arrival {index}")
    response = client.get("/reviews")
    assert "x-robots-tag" not in response.headers
    assert "/reviews</loc>" in client.get("/sitemap.xml").text


def test_bio_and_favorites_alone_do_not_make_a_profile_indexable(client, db_session):
    user = member(db_session, "listmaker")
    for index in range(8):
        db_session.add(models.Movie(user_id=user.id, title=f"Favorite {index}", director="x", year=2000 + index,
                                    rating=9, watched=True))
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True, bio="Mostly sci-fi and slow westerns."))
    db_session.commit()
    response = client.get("/u/listmaker")
    assert response.status_code == 200
    assert response.headers.get("x-robots-tag") == "noindex, follow"
    assert "/u/listmaker</loc>" not in client.get("/sitemap.xml").text
