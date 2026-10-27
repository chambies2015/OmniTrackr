"""October 21 speed pass: the cheaper paths give the same answers with fewer queries."""
from datetime import datetime

from app import models, public_profiles, title_pages
from app.routers import collections as collections_router, reviews as reviews_router, titles as titles_router
from tests.test_collection_discovery import _collection, _user
from tests.test_optimization_pass_oct17 import GOOD_REVIEW, count_queries
from tests.test_public_profiles import enable, library
from tests.test_title_pages import add_movie, member


# ---------------------------------------------------------------- sitemap: title pages

def test_reviewed_only_groups_hold_just_the_search_ready_rows(db_session):
    a, b, c = member(db_session, "ra"), member(db_session, "rb"), member(db_session, "rc")
    reviewed = add_movie(db_session, a, "Arrival", 2016, review=GOOD_REVIEW, review_public=True)
    add_movie(db_session, b, "Arrival", 2016, rating=8)
    add_movie(db_session, c, "Arrival", 2016, review=GOOD_REVIEW, review_public=False)
    add_movie(db_session, c, "Quiet One", 2001, rating=6)
    db_session.commit()
    groups = title_pages.find_many(db_session, "movie", ["arrival-2016", "quiet-one-2001"], reviewed_only=True)
    assert [item.id for item in groups["arrival-2016"].items] == [reviewed.id]
    assert "quiet-one-2001" not in groups


def test_reviewed_only_never_falls_through_to_a_different_title(db_session):
    # "arrival-2016" names Arrival (2016). An unrelated, reviewed "Arrival 2016" with no year
    # has the same address but is never what that page shows, so it can't make the slug indexable.
    a, b = member(db_session, "fa"), member(db_session, "fb")
    add_movie(db_session, a, "Arrival", 2016, rating=8)
    add_movie(db_session, b, "Arrival 2016", None, review=GOOD_REVIEW, review_public=True)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "arrival-2016").year == 2016
    assert title_pages.find_many(db_session, "movie", ["arrival-2016"], reviewed_only=True) == {}


def test_sitemap_lists_reviewed_titles_only(client, db_session):
    a, b, c = member(db_session, "sa"), member(db_session, "sb"), member(db_session, "sc")
    for user in (a, b, c):
        add_movie(db_session, user, "Heat", 1995, rating=9)
        add_movie(db_session, user, "Ronin", 1998, rating=8)
    # Three short reviews add up to enough member writing to index the page (Oct 27).
    for user in (a, b, c):
        add_movie(db_session, user, "Heat", 1995, review=GOOD_REVIEW, review_public=True)
    db_session.commit()
    paths = titles_router.sitemap_entries(db_session)
    assert "/titles/movie/heat-1995" in paths and "/titles/movie/ronin-1998" not in paths


def test_sitemap_review_checks_skip_page_decorations(db_session):
    a = member(db_session, "da")
    add_movie(db_session, a, "Heat", 1995, review=GOOD_REVIEW, review_public=True)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "heat-1995")
    with count_queries(db_session) as light:
        title_pages.summarize(db_session, group, page_sections=False)
    with count_queries(db_session) as full:
        title_pages.summarize(db_session, group)
    assert not any("review_reactions" in s or "review_spoilers" in s or "supporters" in s for s in light)
    assert any("review_reactions" in s for s in full)


def test_title_review_writers_are_the_only_members_loaded(db_session):
    writer = member(db_session, "writer")
    add_movie(db_session, writer, "Heat", 1995, review=GOOD_REVIEW, review_public=True)
    for index in range(30):
        add_movie(db_session, member(db_session, f"fan{index}"), "Heat", 1995, rating=7)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "heat-1995")
    db_session.expire_all()
    with count_queries(db_session):
        reviews = title_pages._public_reviews(db_session, "movie", group.items)
    assert [review["username"] for review in reviews] == ["writer"]
    loaded = {obj.username for obj in db_session.identity_map.values() if isinstance(obj, models.User)}
    assert loaded == {"writer"}


# ---------------------------------------------------------------- sitemap: profiles

def test_profile_sitemap_matches_the_full_profile_check(db_session):
    writer, plain, curator, hidden = (member(db_session, n) for n in ("writer", "plain", "curator", "hidden"))
    library(db_session, writer)
    db_session.add(models.Movie(user_id=plain.id, title="Heat", director="Michael Mann", year=1995, rating=9))
    library(db_session, hidden)
    for user in (writer, plain, curator):
        enable(db_session, user)
    enable(db_session, hidden, show_reviews=False)
    db_session.commit()
    _collection(db_session, curator, "Quiet evenings", ["Alpha", "Beta", "Gamma"])
    expected = sorted(public_profiles.profile_path(user) for user in (writer, plain, curator, hidden)
                      if public_profiles.build(db_session, user, public_profiles.get_settings(db_session, user.id)).indexable)
    assert sorted(public_profiles.sitemap_paths(db_session)) == expected == ["/u/curator", "/u/writer"]


def test_profiles_without_writing_are_skipped_without_building_them(db_session):
    for index in range(10):
        user = member(db_session, f"quiet{index}")
        db_session.add(models.Movie(user_id=user.id, title=f"Film {index}", director="x", year=2000, rating=7))
        enable(db_session, user)
    db_session.commit()
    with count_queries(db_session) as statements:
        assert public_profiles.sitemap_paths(db_session) == []
    assert len(statements) <= 8  # The profile list, then one check per library table and collections.


# ---------------------------------------------------------------- profiles, title pages, gallery

def test_showcase_reads_one_query_per_category(db_session):
    user = member(db_session, "pins")
    movies = [models.Movie(user_id=user.id, title=f"Film {i}", director="x", year=2000 + i) for i in range(6)]
    db_session.add_all(movies)
    db_session.flush()
    for position, movie in enumerate(reversed(movies)):
        db_session.add(models.ProfileShowcaseItem(user_id=user.id, category="movies", item_id=movie.id, position=position))
    db_session.commit()
    db_session.refresh(user)
    with count_queries(db_session) as statements:
        shown = public_profiles.showcase_items(db_session, user)
    assert [item["title"] for item in shown] == [f"Film {i}" for i in reversed(range(6))]
    assert len(statements) == 2


def test_title_page_collections_do_not_query_per_title(db_session):
    curator = _user(db_session, "curator")
    collection = _collection(db_session, curator, "Long list", [f"Pick {i}" for i in range(12)])
    first = db_session.query(models.Movie).filter_by(title="Pick 0").one()
    with count_queries(db_session) as statements:
        featured = title_pages._collections_featuring(db_session, "movie", [first])
    assert [entry["url"] for entry in featured] == [f"/collections/public/{collection.id}"]
    assert len(statements) <= 4


def test_gallery_reads_past_the_first_batch(client, db_session, monkeypatch):
    monkeypatch.setattr(collections_router, "GALLERY_BATCH", 2)
    owner = _user(db_session, "owner")
    for index in range(5):
        _collection(db_session, owner, f"Shelf {index}", ["Alpha", "Beta", "Gamma"], helpful=10 - index)
    page = client.get("/collections/explore").text
    positions = [page.index(f">Shelf {index}</a>") for index in range(5)]
    assert positions == sorted(positions)


# ---------------------------------------------------------------- public reviews

def test_review_feed_query_count_does_not_grow_with_reviews(db_session):
    for index in range(25):
        user = member(db_session, f"critic{index}")
        add_movie(db_session, user, f"Film {index}", 2000 + index, review=GOOD_REVIEW + f" Note {index}.", review_public=True)
    db_session.commit()
    with count_queries(db_session) as statements:
        feed = reviews_router._public_review_feed(db_session, None, "", 20, 0)
    assert len(feed["reviews"]) == 20 and feed["has_more"] is True
    assert [review["title"] for review in feed["reviews"]] == [f"Film {index}" for index in range(24, 4, -1)]
    assert {review["username"] for review in feed["reviews"]} == {f"critic{index}" for index in range(5, 25)}
    assert len(statements) <= 10


def test_review_feed_still_hides_suspended_reviews(db_session):
    writer = member(db_session, "suspended")
    movie = add_movie(db_session, writer, "Heat", 1995, review=GOOD_REVIEW, review_public=True)
    db_session.add(models.PublicReviewState(
        user_id=writer.id, category="movie", item_id=movie.id, report_count=3, suspended_at=datetime.utcnow(),
        content_hash=reviews_router._review_content_hash("movie", movie.id, movie.review)))
    db_session.commit()
    assert reviews_router._public_review_feed(db_session, None, "", 20, 0)["reviews"] == []


# ---------------------------------------------------------------- /titles directory

def test_titles_directory_is_reused_between_visits(client, db_session, monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setattr(titles_router, "_titles_index_cache", {"at": 0.0, "page": None})
    for name in ("da", "db", "dc"):
        add_movie(db_session, member(db_session, name), "Heat", 1995, rating=9)
    db_session.commit()
    first = client.get("/titles")
    with count_queries(db_session) as statements:
        second = client.get("/titles")
    assert first.status_code == second.status_code == 200
    assert "Heat" in second.text and statements == []
    assert second.headers["cache-control"] == "public, max-age=900"
