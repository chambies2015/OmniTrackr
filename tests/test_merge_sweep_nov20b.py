"""Nov 20 2026 afternoon sweep of #257 to #261, mostly Find people (#258)."""
from sqlalchemy import event

from app import models, people_to_follow, public_profiles
from tests.conftest import engine
from tests.test_find_people import LONG_REVIEW, card_for, member, movies, people, public, suggest

LIBRARY = [("Dune", 2021), ("Arrival", 2016), ("Secret Film", 2001), ("Filler A", 1999), ("Filler B", 1998)]


class Queries:
    def __init__(self):
        self.seen = []

    def __enter__(self):
        event.listen(engine, "before_cursor_execute", self.record)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "before_cursor_execute", self.record)

    def record(self, conn, cursor, statement, params, context, executemany):
        self.seen.append(statement)


def _probe(client, db, me, target):
    """Whether ``target`` shows up with and without "Secret Film" in the viewer's own library."""
    with_title = "target" in people(suggest(client, me), "taste")
    db.query(models.Movie).filter_by(user_id=me.id, title="Secret Film").delete()
    db.commit()
    people_to_follow.clear_cache()
    without_title = "target" in people(suggest(client, me), "taste")
    return with_title, without_title


def test_a_hidden_title_cannot_be_tested_for_by_adding_it_to_your_own_library(client, db_session):
    me = member(db_session, "me")
    movies(db_session, me, LIBRARY, rating=9)
    target = member(db_session, "target")
    movies(db_session, target, LIBRARY[:2], rating=9)            # favorites: on the profile
    movies(db_session, target, [("Secret Film", 2001)], rating=7)  # in the library, shown nowhere
    public(db_session, target)
    # Before the fix the third, hidden title made the match, so the card came and went with it.
    assert _probe(client, db_session, me, target) == (False, False)


def test_hidden_titles_never_feed_the_match_or_the_card(client, db_session):
    me = member(db_session, "me")
    movies(db_session, me, LIBRARY, rating=9)
    target = member(db_session, "target")
    movies(db_session, target, [("Dune", 2021), ("Arrival", 2016), ("Filler A", 1999)], rating=9)
    movies(db_session, target, [("Secret Film", 2001), ("Filler B", 1998)], rating=6)
    public(db_session, target)
    card = card_for(suggest(client, me), "target")
    assert card and card["source"] == "taste"
    assert "more in common" not in card["reason"] and "compare_url" not in card
    assert {title["title"] for title in card["titles"]} <= {"Dune", "Arrival", "Filler A"}
    # A score built from shown titles only: the same card whether or not the hidden ones are there.
    db_session.query(models.Movie).filter_by(user_id=target.id, rating=6).delete()
    db_session.commit()
    people_to_follow.clear_cache()
    from app import picked_for_you
    picked_for_you.clear_cache()
    assert card_for(suggest(client, me), "target") == card


def test_the_compare_link_still_lets_the_whole_overlap_count(client, db_session):
    me = member(db_session, "me")
    movies(db_session, me, LIBRARY, rating=9)
    target = member(db_session, "target")
    movies(db_session, target, LIBRARY[:2], rating=9)
    movies(db_session, target, [("Secret Film", 2001)], rating=7)
    # Their compare tastes page already shows signed-in members every title in common.
    public(db_session, target, show_taste_match=True)
    card = card_for(suggest(client, me), "target")
    assert card and card["compare_url"] == "/u/target/match"
    assert card["reason"].endswith("1 more in common")


def _shelves_profile(db):
    user = member(db, "shelves")
    movies(db, user, [("Dune", 2021), ("Arrival", 2016)], rating=9)
    movies(db, user, [("Her", 2013)], rating=5)
    db.add(models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", rating=10, read=True,
                       review=LONG_REVIEW, review_public=True))
    db.add(models.Book(user_id=user.id, title="Short Note", author="A", rating=6, read=True,
                       review="Too short to show.", review_public=True))
    db.add(models.Anime(user_id=user.id, title="Mushishi", year=2005, rating=7, watched=True,
                        review=LONG_REVIEW, review_public=False))
    db.add(models.VideoGame(user_id=user.id, title="Outer Wilds", rating=10, played=True))
    db.commit()
    public(db, user)
    return user


def test_skipping_empty_shelves_reads_the_same_profile(db_session):
    user = _shelves_profile(db_session)
    favorites, reviews = people_to_follow._shelves_with(db_session, user.id)
    assert favorites == {"movies", "books", "video-games"}
    assert reviews == {"books"}
    assert public_profiles._favorites(db_session, user, categories=favorites) == public_profiles._favorites(db_session, user)
    assert public_profiles._reviews(db_session, user, categories=reviews) == public_profiles._reviews(db_session, user)
    assert [r["title"] for r in public_profiles._reviews(db_session, user)] == ["Piranesi"]


def test_reading_a_profile_for_find_people_takes_a_handful_of_queries(db_session):
    user = _shelves_profile(db_session)
    profile = db_session.query(models.PublicProfile).filter_by(user_id=user.id).one()
    with Queries() as queries:
        shown = people_to_follow._build_shown(db_session, user, profile)
    assert {facts["title"] for facts in shown.values()} == {"Dune", "Arrival", "Piranesi", "Outer Wilds"}
    # Pins, one shelf check, three favorite shelves, one review shelf + its moderation and spoiler rows.
    # Reading all nine shelves for favorites and reviews took 25.
    assert len(queries.seen) <= 9, queries.seen


def test_a_profile_with_both_sections_off_skips_the_shelf_check(db_session):
    user = _shelves_profile(db_session)
    profile = db_session.query(models.PublicProfile).filter_by(user_id=user.id).one()
    profile.show_favorites = False
    profile.show_reviews = False
    db_session.commit()
    with Queries() as queries:
        assert people_to_follow._build_shown(db_session, user, profile) == {}
    assert not any("AS shelf" in statement for statement in queries.seen)
