"""Nov 27 2026 sweep of #345 (the signed-in home in three groups) and #346 (2026's big ones on Fill in your year
and the emailed page that saves them without signing in)."""
import inspect
import re
from datetime import datetime, timedelta
from pathlib import Path

from app import friend_feed, models, trending, year_catchup
from app.main import YEAR_FILL_LIMITS
from app.routers import year_fill as year_fill_router
from tests.test_year_catchup import GTA, PITT, SPIDER, frozen, member  # noqa: F401  (frozen is an autouse fixture)

ROOT = Path(__file__).resolve().parents[1]


def befriend(db, one, two):
    low, high = sorted((one.id, two.id))
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.commit()


def feed_cards(db, viewer):
    cards, _friends = friend_feed.collect(db, viewer.id, now=datetime.utcnow() + timedelta(minutes=1))
    return [(card.kind, card.item.title) for card in cards if isinstance(card, friend_feed.Entry)]


# ---------------------------------------------------------------- #346 the big ones

def test_a_big_one_dated_to_an_earlier_month_is_not_a_finished_card_today(db_session):
    user = member(db_session)
    friend = member(db_session, "friend")
    befriend(db_session, user, friend)

    year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    # Saved today, watched in August: friends see the add (as a film they've watched), not a finish from today.
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=user.id).count() == 0
    assert feed_cards(db_session, friend) == [("added", "Spider-Man: Brand New Day")]
    movie = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert movie.watched is True
    assert friend_feed.QUIET_KEY not in db_session.info

    # This month is a normal tick, so it is news.
    year_catchup.answer(db_session, user, 2026, GTA, "month", 12)
    events = db_session.query(models.FriendFeedEvent).filter_by(user_id=user.id).all()
    assert [(event.category, event.kind) for event in events] == [("video-games", "finished")]
    assert friend_feed.QUIET_KEY not in db_session.info


def test_a_refused_month_leaves_the_feed_switch_off(db_session):
    user = member(db_session)
    db_session.commit()
    try:
        year_catchup.answer(db_session, user, 2026, SPIDER, "month", 2)  # before it came out
    except ValueError:
        pass
    assert friend_feed.QUIET_KEY not in db_session.info
    assert db_session.query(models.Movie).count() == 0


def test_backdated_big_ones_are_not_trending_adds(db_session):
    users = [member(db_session, f"m{index}") for index in range(3)]
    db_session.commit()
    for user in users:
        year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)   # watched in August, saved now
        year_catchup.answer(db_session, user, 2026, GTA, "month", 12)     # played this month
        year_catchup.answer(db_session, user, 2026, PITT, "want")         # wants to watch it
    signals = trending.scan(db_session, datetime.utcnow() + timedelta(minutes=1))
    added = {signal["title"] for signal in signals if signal["signal"] == "added"}
    assert "Spider-Man: Brand New Day" not in added
    assert {"Grand Theft Auto VI", "The Pitt"} <= added
    # The August finish is a "filled-in" journal entry, which trending already leaves out.
    finished = {signal["title"] for signal in signals if signal["signal"] == "finished"}
    assert "Spider-Man: Brand New Day" not in finished and "Grand Theft Auto VI" in finished


def test_taking_an_answer_back_keeps_a_title_the_member_has_rated_or_reviewed(db_session):
    user = member(db_session)
    db_session.commit()
    year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    year_catchup.answer(db_session, user, 2026, PITT, "want")
    movie = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    show = db_session.query(models.TVShow).filter_by(user_id=user.id).one()
    movie.rating = 8.5
    show.review = "Best hospital show in years."
    db_session.commit()
    # Within the day, but the member has made both their own: the answers go, the titles stay.
    assert year_catchup.undo(db_session, user, 2026, SPIDER)
    assert year_catchup.undo(db_session, user, 2026, PITT)
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 1
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).count() == 1
    assert db_session.query(models.YearCatchupAnswer).count() == 0
    # An untouched one still leaves again.
    year_catchup.answer(db_session, user, 2026, GTA, "want")
    assert year_catchup.undo(db_session, user, 2026, GTA)
    assert db_session.query(models.VideoGame).filter_by(user_id=user.id).count() == 0


def test_the_big_ones_api_is_rate_limited():
    paths = {(getattr(route, "path", None), method) for route in year_fill_router.router.routes
             for method in getattr(route, "methods", None) or ()}
    wanted = {
        ("/api/year-in-review/{year}/big-ones", "POST"): "120/minute",
        ("/api/year-in-review/{year}/big-ones/undo", "POST"): "60/minute",
        ("/api/year-in-review/{year}/big-ones/art/{kind}/{slug}", "GET"): "60/minute",
    }
    for key, limit in wanted.items():
        assert key in paths and YEAR_FILL_LIMITS[key] == limit
    # Every route on the router is limited, the emailed page included.
    assert paths <= set(YEAR_FILL_LIMITS) | {("/year-in-review/{year}/fill", "GET")}
    for endpoint in (year_fill_router.big_answer, year_fill_router.big_undo, year_fill_router.big_art):
        assert "request" in inspect.signature(endpoint).parameters  # slowapi counts against the request


# ---------------------------------------------------------------- #345 the home

def test_whats_new_links_are_readable_in_night_mode():
    css = (ROOT / "app/static/member-look.css").read_text()
    rule = re.search(r"body\.app-shell\.dark-mode \.home-board \.home-news__link \{([^}]*)\}", css)
    assert rule and "#c4b5fd" in rule.group(1)
    index = (ROOT / "app/templates/index.html").read_text()
    assert index.count("/static/member-look.css?v=20261127-sweep-1") == 1
