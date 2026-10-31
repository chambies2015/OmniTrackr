"""Your year so far (November): dashboard card, weekly email section, one push, December hand-off."""
from datetime import date, datetime

import pytest

from app import digest, models, web_push, year_in_review, year_so_far
from app.site_traffic import RECORDER
from tests.test_push_nudges import recording
from tests.test_push_settings import _device, fresh_key  # noqa: F401  (fixture)
from tests.test_year_in_review import _finish, _user

YEAR = datetime.utcnow().year
NOV = date(YEAR, 11, 15)
CHROME = "Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0 Safari/537.36"


@pytest.fixture(autouse=True)
def _forget_quiet_members():
    year_so_far._quiet_until.clear()
    yield
    year_so_far._quiet_until.clear()


def _seed(client):
    _finish(client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016}, "watched")
    _finish(client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020, "genre": "Fantasy"}, "read")
    _finish(client, "/books/", {"title": "The Hobbit", "author": "J. R. R. Tolkien", "year": 1937, "genre": "Fantasy"}, "read")


def test_only_november_is_previewed_and_december_belongs_to_the_recap():
    assert year_so_far.active_year(date(2026, 11, 1)) == 2026
    assert year_so_far.active_year(date(2026, 11, 30)) == 2026
    assert year_so_far.active_year(date(2026, 10, 31)) is None
    assert year_so_far.active_year(date(2026, 12, 1)) is None
    # The two never overlap: November is the preview, December and January are the recap.
    for month in range(1, 13):
        day = date(2026, month, 10)
        assert not (year_so_far.active_year(day) and year_in_review.season_year(day))


def test_summary_counts_the_year_like_year_in_review(authenticated_client, db_session):
    user = _user(db_session)
    assert year_so_far.summary(db_session, user, NOV) is None, "nothing finished: no card"
    _seed(authenticated_client)
    data = year_so_far.summary(db_session, user, NOV)
    assert data["year"] == YEAR and data["finished"] == 3
    assert data["finished"] == year_in_review.build(db_session, user, YEAR)["finished_total"]
    assert data["genre"] == "Fantasy"
    assert data["top_shelf"] == {"category": "books", "noun": "books", "finished": 2}
    assert data["hours"] and data["hours"] > 0
    assert data["days_left"] == 47
    assert data["url"] == f"/year-in-review/{YEAR}?from=card"
    assert data["hint"] == "47 days left. Anything you finish by December 31 goes in your recap."
    assert year_so_far.summary(db_session, user, date(YEAR, 12, 2)) is None


def test_hint_prefers_the_closest_goal_then_next_up(authenticated_client, db_session):
    user = _user(db_session)
    _seed(authenticated_client)
    queued = authenticated_client.post("/movies/", json={"title": "Heat", "director": "M. Mann", "year": 1995, "watched": False}).json()
    db_session.add(models.NextUpItem(user_id=user.id, category="movies", item_id=queued["id"], position=0))
    db_session.commit()
    assert year_so_far.summary(db_session, user, NOV)["hint"] == \
        "Next in your queue is Heat. Finish it by December 31 and it makes your recap."
    db_session.add_all([models.YearlyGoal(user_id=user.id, year=YEAR, category="books", target=5),
                        models.YearlyGoal(user_id=user.id, year=YEAR, category="all", target=20)])
    db_session.commit()
    assert year_so_far.summary(db_session, user, NOV)["hint"] == "3 books to go and you reach your goal of 5."


def test_dashboard_api(authenticated_client, db_session, monkeypatch):
    _seed(authenticated_client)
    monkeypatch.setattr(year_so_far, "_today", lambda: date(YEAR, 10, 31))
    assert authenticated_client.get("/api/year-in-review-so-far").json() == {"year": None}
    monkeypatch.setattr(year_so_far, "_today", lambda: NOV)
    response = authenticated_client.get("/api/year-in-review-so-far")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["finished"] == 3


def test_dashboard_api_needs_sign_in(client):
    assert client.get("/api/year-in-review-so-far").status_code == 401


def test_card_email_and_push_visits_are_counted(authenticated_client, db_session, monkeypatch):
    _seed(authenticated_client)
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    authenticated_client.headers["User-Agent"] = CHROME

    def counted(event):
        return sum(n for (_, kind, key), n in RECORDER._pending.items() if kind == "funnel" and key == event)
    try:
        for source in ("card", "email", "push", "elsewhere"):
            assert authenticated_client.get(f"/year-in-review/{YEAR}?from={source}").status_code == 200
        assert counted("year_so_far_card_opened") == 1
        assert counted("year_so_far_email_opened") == 1
        assert counted("year_so_far_push_opened") == 1
        assert counted("recap_opened") == 4
    finally:
        RECORDER._pending.clear()


def test_weekly_email_section_in_november_and_recap_in_december(authenticated_client, db_session):
    user = _user(db_session)
    assert digest.recap_line(db_session, user.id, NOV) is None
    _seed(authenticated_client)
    line = digest.recap_line(db_session, user.id, NOV)
    assert line["so_far"] is True and line["finished"] == 3
    html, text = digest._recap_section(line, "https://omnitrackr.xyz")
    assert f"Your {YEAR} so far" in html
    assert "3 titles finished and about" in html and "Top genre: Fantasy." in html
    assert "opens on December 1" in html
    assert f"https://omnitrackr.xyz/year-in-review/{YEAR}?from=email" in html
    if YEAR == 2026:
        assert "Since September: 3 titles finished" in html
    assert text[0].startswith(f"Your {YEAR} so far: ") and "3 titles finished" in text[0]
    december = digest.recap_line(db_session, user.id, date(YEAR, 12, 6))
    assert december == {"year": YEAR, "finished": 3}
    html, _ = digest._recap_section(december, "https://omnitrackr.xyz")
    assert "Play your year" in html and "so far" not in html
    assert digest.recap_line(db_session, user.id, date(YEAR, 10, 20)) is None


def test_push_goes_to_members_with_the_goals_switch_on_once_a_year(authenticated_client, db_session, fresh_key):
    user = _user(db_session)
    _seed(authenticated_client)
    _device(db_session, user)
    now = datetime(YEAR, 11, 20, 15, 0)
    seen, http = recording()
    with http:
        # "Cheers, badges and goals" is off unless the member turned it on.
        assert year_so_far.send_pushes(db_session, http=http, now=now)["sent"] == 0
        web_push.save_settings(db_session, user.id, topics={"milestones": True})
        assert year_so_far.send_pushes(db_session, http=http, now=datetime(YEAR, 11, 10, 15, 0))["sent"] == 0, \
            "not before the 15th"
        assert year_so_far.send_pushes(db_session, http=http, now=datetime(YEAR, 12, 2, 15, 0))["sent"] == 0
        assert year_so_far.send_pushes(db_session, http=http, now=now)["sent"] == 1
        assert year_so_far.send_pushes(db_session, http=http, now=datetime(YEAR, 11, 27, 15, 0))["sent"] == 0
    assert len(seen) == 1
    assert db_session.query(models.PushNudge).filter_by(kind="year_so_far").count() == 1
    assert web_push.TITLES["year_so_far"] == "Your year so far"
    assert web_push.topic_of("year_so_far") == "milestones"


def test_push_message_and_members_with_too_little_to_say(authenticated_client, db_session, fresh_key):
    user = _user(db_session)
    _finish(authenticated_client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016}, "watched")
    _device(db_session, user)
    web_push.save_settings(db_session, user.id, topics={"milestones": True})
    seen, http = recording()
    with http:
        stats = year_so_far.send_pushes(db_session, http=http, now=datetime(YEAR, 11, 20, 15, 0))
    assert stats["nothing_to_say"] == 1 and seen == []
    data = {"year": 2026, "finished": 23, "hours": 61, "genre": "Fantasy",
            "hint": "4 books to go and you reach your goal of 20."}
    assert year_so_far.push_message(data) == \
        "2026 so far: 23 titles finished and about 61 hours. Top genre: Fantasy. 4 books to go and you reach your goal of 20."
    assert len(year_so_far.push_message({**data, "hint": "x" * 400})) == web_push.MAX_BODY_CHARS


def test_push_waits_for_the_members_daytime(authenticated_client, db_session, fresh_key):
    user = _user(db_session)
    _seed(authenticated_client)
    _device(db_session, user)
    web_push.save_settings(db_session, user.id, topics={"milestones": True}, time_zone="America/Chicago")
    seen, http = recording()
    with http:
        stats = year_so_far.send_pushes(db_session, http=http, now=datetime(YEAR, 11, 20, 8, 0))  # 2 am in Chicago
    assert stats["quiet"] == 1 and seen == []
