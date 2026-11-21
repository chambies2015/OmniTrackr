"""Sweep of the Nov 10 merges: the earlier Nov 10 sweep (#195), the reading layout for
written guides (#196) and the 2027 New Year challenge (#197)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app import goals, guide_layout, models, new_year_challenge as nyc, site_traffic
from app.routers import new_year_challenge as nyc_router
from tests.conftest import engine
from tests.test_new_year_challenge import DECEMBER, _user, december  # noqa: F401 (fixture)
from tests.test_security_sweep_nov06 import _limited

ALL_TEN = {"books": 25, "movies": 51, "video-games": 7, "all": 101, "anime": 3, "music": 10,
           "tv-shows": 5, "manga": 2, "podcasts": 2, "audiobooks": 2}


class _Statements:
    """SQL statements and commits sent to the test database while the block runs."""

    def __enter__(self):
        self.sql, self.commits = [], 0
        event.listen(engine, "before_cursor_execute", self._statement)
        event.listen(engine, "commit", self._commit)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "before_cursor_execute", self._statement)
        event.remove(engine, "commit", self._commit)

    def _statement(self, conn, cursor, statement, *args):
        self.sql.append(" ".join(statement.split()))

    def _commit(self, conn):
        self.commits += 1


# ---------------------------------------------------------------- limits and Site stats

def test_every_challenge_api_route_is_rate_limited():
    """Saving and sharing had limits; the card, the state call, leaving and unsharing had none."""
    checked = 0
    for route in nyc_router.router.routes:
        if not route.path.startswith(("/api/", "/pledge/")):
            continue
        for method in route.methods:
            assert _limited(nyc_router.router, route.path, method), (method, route.path)
            checked += 1
    assert checked == 8


def test_site_stats_never_stores_a_pledge_link():
    """A pledge link is the key to the card, like a recap or goal link, so it is counted under one row."""
    assert site_traffic.clean_path("/pledge/pNU2pjG6vP4Malc-") == "/pledge/(private link)"
    assert site_traffic.clean_path("/pledge/pNU2pjG6vP4Malc-/") == "/pledge/(private link)"
    assert site_traffic.clean_path("/new-year-challenge/2027") == "/new-year-challenge/2027"


# ---------------------------------------------------------------- saving a pledge

def test_a_pledge_is_saved_in_one_transaction(authenticated_client, db_session, december):
    """Ten goals used to be ten commits, each followed by a reload of the member: 41 queries."""
    user = _user(db_session)
    with _Statements() as seen:
        row, created = nyc.pledge(db_session, user, 2027, dict(ALL_TEN))
    assert created and row.user_id == user.id
    assert seen.commits == 1
    # Two reads (the goals and the pledge), then one write per row.
    assert len(seen.sql) <= 2 + len(ALL_TEN) + 1, seen.sql
    saved = {goal.category: goal.target for goal in db_session.query(models.YearlyGoal).filter_by(year=2027)}
    assert saved == ALL_TEN

    with _Statements() as seen:
        row, created = nyc.pledge(db_session, user, 2027, {"books": 30, "movies": None, "music": 10})
    assert not created and seen.commits == 1
    saved = {goal.category: goal.target for goal in db_session.query(models.YearlyGoal).filter_by(year=2027)}
    expected = {**ALL_TEN, "books": 30}
    del expected["movies"]
    assert saved == expected


def test_dropping_a_goal_through_the_form_clears_its_reached_moment(authenticated_client, db_session, december):
    """The same clean-up goals.remove does, so a shared "goal reached" link doesn't outlive the goal."""
    user = _user(db_session)
    nyc.pledge(db_session, user, 2027, {"books": 1, "movies": 3})
    db_session.add(models.GoalAchievement(user_id=user.id, year=2027, category="books", target=1, share_token="tok-books"))
    db_session.commit()
    nyc.pledge(db_session, user, 2027, {"books": None})
    assert db_session.query(models.GoalAchievement).filter_by(user_id=user.id, year=2027).count() == 0
    assert [goal.category for goal in db_session.query(models.YearlyGoal).filter_by(user_id=user.id, year=2027)] == ["movies"]


def test_a_clash_with_another_tab_still_saves_every_goal(authenticated_client, db_session, december, monkeypatch):
    """If another tab creates one of the same rows first, the save falls back to goal-by-goal."""
    user = _user(db_session)
    real_commit, calls = db_session.commit, {"count": 0}

    def commit():
        calls["count"] += 1
        if calls["count"] == 1:
            raise IntegrityError("INSERT INTO yearly_goals", {}, Exception("uq_yearly_goal"))
        return real_commit()
    monkeypatch.setattr(db_session, "commit", commit)
    row, created = nyc.pledge(db_session, user, 2027, {"books": 12, "movies": 40})
    monkeypatch.undo()
    assert created and row is not None
    saved = {goal.category: goal.target for goal in db_session.query(models.YearlyGoal).filter_by(year=2027)}
    assert saved == {"books": 12, "movies": 40}
    assert db_session.query(models.YearPledge).filter_by(user_id=_user(db_session).id, year=2027).count() == 1


def test_an_invalid_number_saves_nothing(authenticated_client, db_session, december):
    response = authenticated_client.put("/api/new-year-challenge/2027/pledge",
                                        json={"goals": {"books": 12, "movies": 5000}})
    assert response.status_code == 422
    assert db_session.query(models.YearlyGoal).count() == 0 and db_session.query(models.YearPledge).count() == 0


def test_sharing_reads_the_privacy_switches_in_one_query(authenticated_client, db_session, december):
    """The signed-in member is loaded with a few columns only. Each of the nine shelf privacy
    switches used to be fetched on its own when the share button checked them."""
    assert authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}}).status_code == 200
    db_session.expunge_all()  # As in a real request: the member row comes from the sign-in lookup.
    with _Statements() as seen:
        shared = authenticated_client.put("/api/new-year-challenge/2027/share")
    assert shared.status_code == 200 and shared.json()["shared"]
    one_column = [sql for sql in seen.sql if sql.startswith("SELECT users.") and "," not in sql.split(" FROM ")[0]]
    assert one_column == []
    assert len(seen.sql) <= 14, seen.sql


def test_sharing_still_respects_a_private_shelf(authenticated_client, db_session, december):
    assert authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}}).status_code == 200
    user = _user(db_session)
    user.books_private = True
    db_session.commit()
    db_session.expunge_all()
    assert authenticated_client.put("/api/new-year-challenge/2027/share").status_code == 422


def test_public_counts_leave_out_other_years_and_deactivated_members(db_session, december):
    """The counts are now one joined query. Same numbers as before: pledged, active members, that year only."""
    members = []
    for index, name in enumerate(("ann", "ben", "cat", "dee", "eve")):
        user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True,
                           is_active=name != "eve")
        db_session.add(user)
        db_session.flush()
        members.append(user)
        if name != "dee":  # dee has a goal but never pledged
            db_session.add(models.YearPledge(user_id=user.id, year=2027))
        db_session.add(models.YearlyGoal(user_id=user.id, year=2027, category="books", target=10 * (index + 1)))
        db_session.add(models.YearlyGoal(user_id=user.id, year=2026, category="books", target=500))
    db_session.commit()
    counts = nyc.public_counts(db_session, 2027)
    assert counts["pledged"] == 3 and counts["show"]
    assert counts["titles"] == 10 + 20 + 30
    assert counts["categories"] == [{"key": "books", "members": 3, "median": 20, "noun": "books"}]


# ---------------------------------------------------------------- dashboard card and page

@pytest.mark.parametrize("opens", ["", "2026-11-01", "2026-06-15", "2027-01-20", "2027-07-01"])
def test_the_home_card_only_ever_shows_from_november_to_january(monkeypatch, opens):
    """new-year-challenge.js skips the card request from February to October, so the
    server must never want to show the card then, wherever the opening day is moved."""
    monkeypatch.setenv("NEW_YEAR_CHALLENGE_OPENS", opens)
    day = date(2026, 1, 1)
    while day <= date(2028, 12, 31):
        if 2 <= day.month <= 10:
            assert nyc.card_year(day) is None, day
        day += timedelta(days=1)


def test_the_cost_table_can_be_scrolled_from_the_keyboard(client, december):
    """On phones the table scrolls sideways inside its wrapper, which had no way to take focus."""
    page = client.get("/new-year-challenge/2027").text
    assert '<div class="nyc-table-wrap" role="region" aria-label="Time each format takes" tabindex="0">' in page


# ---------------------------------------------------------------- reading layout

def test_contents_links_are_not_escaped_twice():
    page = (
        '<html><head></head><body><article class="trail-guide"><header class="hero hero--guide"><h1>Guide</h1>'
        '<nav class="guide-jump" aria-label="On this page"><a href="#q&amp;a">Questions &amp; answers</a></nav></header>'
        '<section id="q&amp;a"><p>Text</p></section></article></body></html>'
    )
    html = guide_layout.add_reading_layout(page)
    rail = html.split('<aside class="guide-rail"', 1)[1]
    assert '<a href="#q&amp;a">Questions &amp; answers</a>' in rail
    assert "&amp;amp;" not in html


def test_reader_script_never_borrows_a_nonce_from_page_text():
    """Only a real script tag's nonce is copied. Escaped text that looks like one is ignored."""
    page = (
        '<html><head><title>&lt;script nonce="evil"&gt;</title></head><body>'
        '<article class="trail-guide"><header class="hero hero--guide"><h1>Guide</h1></header>'
        '<p>&lt;script src="x" nonce="evil"&gt;</p></article></body></html>'
    )
    html = guide_layout.add_reading_layout(page)
    assert f'<script src="/static/guide-reader.js?v={guide_layout.JS_VERSION}" defer></script>' in html
    assert 'nonce="evil" defer' not in html
