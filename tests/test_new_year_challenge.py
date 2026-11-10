"""The New Year challenge: opening dates, pledges over yearly goals, suggestions, sharing and the guide page."""
from datetime import date, datetime

import pytest

from app import goals, models, new_year_challenge as nyc, year_in_review
from app.routers import new_year_challenge as nyc_router

DECEMBER = date(2026, 12, 5)
NOVEMBER = date(2026, 11, 10)
CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


@pytest.fixture
def december(monkeypatch):
    monkeypatch.delenv("NEW_YEAR_CHALLENGE_OPENS", raising=False)
    monkeypatch.setattr(nyc, "_today", lambda: DECEMBER)
    # Goal validation and pace use the real clock; pin them to the same day.
    monkeypatch.setattr(goals, "allowed_years", lambda today=None: [2026, 2027])
    return DECEMBER


@pytest.fixture
def counts(monkeypatch):
    """2026 finishes, fixed so the tests don't depend on when they run."""
    fixed = {key: 0 for key in year_in_review.CATEGORIES}
    fixed.update({"books": 9, "movies": 20, "music": 1})

    def fake(db, user_id, year):
        return dict(fixed) if year == 2026 else {key: 0 for key in year_in_review.CATEGORIES}
    monkeypatch.setattr(year_in_review, "finished_counts", fake)
    return fixed


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _other(db_session, name, **flags):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, **flags)
    db_session.add(user)
    db_session.flush()
    return user


# ---------------------------------------------------------------- dates

def test_opening_window(monkeypatch):
    monkeypatch.delenv("NEW_YEAR_CHALLENGE_OPENS", raising=False)
    assert nyc.opens(2027) == date(2026, 12, 1)
    assert not nyc.is_open(2027, NOVEMBER) and not nyc.is_public(2027, NOVEMBER)
    assert nyc.is_open(2027, date(2026, 12, 1)) and nyc.is_open(2027, date(2027, 12, 31))
    assert not nyc.is_open(2027, date(2028, 1, 1)) and nyc.is_public(2027, date(2028, 1, 1))
    assert not nyc.is_open(2031, date(2030, 12, 5))  # no written edition
    assert nyc.current_year(NOVEMBER) is None
    assert nyc.current_year(DECEMBER) == 2027 and nyc.current_year(date(2027, 6, 1)) == 2027
    # The dashboard card runs from December 1 to January 31.
    assert nyc.card_year(NOVEMBER) is None
    assert nyc.card_year(DECEMBER) == 2027 and nyc.card_year(date(2027, 1, 31)) == 2027
    assert nyc.card_year(date(2027, 2, 1)) is None
    assert nyc.days_until_start(2027, DECEMBER) == 27 and nyc.days_until_start(2027, date(2027, 3, 1)) == 0


def test_opening_day_can_move_without_a_code_change(monkeypatch):
    monkeypatch.setenv("NEW_YEAR_CHALLENGE_OPENS", "2026-11-20")
    assert nyc.opens(2027) == date(2026, 11, 20)
    assert nyc.is_open(2027, date(2026, 11, 21)) and nyc.card_year(date(2026, 11, 21)) == 2027
    monkeypatch.setenv("NEW_YEAR_CHALLENGE_OPENS", "not-a-date")
    assert nyc.opens(2027) == date(2026, 12, 1)
    monkeypatch.setenv("NEW_YEAR_CHALLENGE_OPENS", "2020-01-01")  # too far off: ignored
    assert nyc.opens(2027) == date(2026, 12, 1)


def test_hours():
    assert nyc.weekly_hours({}) == 0 and nyc.hours_label(0) == ""
    assert nyc.weekly_hours({"books": 52}) == 8.0
    assert nyc.hours_label(nyc.weekly_hours({"books": 52})) == "about 8 hours a week"
    assert nyc.hours_label(nyc.weekly_hours({"movies": 12})) == "about 25 minutes a week"
    assert nyc.hours_label(1.0) == "about 1 hour a week" and nyc.hours_label(2.3) == "about 2.5 hours a week"
    # The any-kind goal has no length of its own.
    assert nyc.weekly_hours({"all": 100}) == 0


# ---------------------------------------------------------------- before opening

def test_closed_before_december(client, authenticated_client, monkeypatch):
    monkeypatch.delenv("NEW_YEAR_CHALLENGE_OPENS", raising=False)
    monkeypatch.setattr(nyc, "_today", lambda: NOVEMBER)
    assert authenticated_client.get("/new-year-challenge/2027").status_code == 404
    assert authenticated_client.get("/new-year-challenge", follow_redirects=False).status_code == 404
    assert authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 5}}).status_code == 404
    assert authenticated_client.get("/api/new-year-challenge").json() == {"show": False}
    assert "/new-year-challenge" not in authenticated_client.get("/sitemap.xml").text
    assert "new-year-challenge" not in authenticated_client.get("/llms.txt").text
    assert "The 2027 challenge" not in authenticated_client.get("/challenges").text


def test_admins_can_preview_before_opening(authenticated_client, db_session, monkeypatch):
    monkeypatch.delenv("NEW_YEAR_CHALLENGE_OPENS", raising=False)
    monkeypatch.setattr(nyc, "_today", lambda: NOVEMBER)
    monkeypatch.setattr(nyc_router, "is_site_admin", lambda user: user is not None and user.username == "testuser")
    page = authenticated_client.get("/new-year-challenge/2027")
    assert page.status_code == 200
    assert "noindex" in page.headers.get("X-Robots-Tag", "")
    assert authenticated_client.get("/new-year-challenge", follow_redirects=False).headers["location"] == "/new-year-challenge/2027"


def test_unknown_year_is_404(client, december):
    assert client.get("/new-year-challenge/2031").status_code == 404
    assert client.get("/new-year-challenge/abc").status_code == 422


# ---------------------------------------------------------------- pledges

def test_api_needs_login(client, december):
    assert client.get("/api/new-year-challenge").status_code == 401
    assert client.get("/api/new-year-challenge/2027").status_code == 401
    assert client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 5}}).status_code == 401


def test_pledge_saves_yearly_goals_and_leaving_keeps_them(authenticated_client, db_session, december, counts):
    empty = authenticated_client.get("/api/new-year-challenge/2027")
    assert empty.status_code == 200 and empty.headers["Cache-Control"] == "private, no-store"
    body = empty.json()
    assert body["open"] and not body["pledged"] and not body["started"] and body["days_until_start"] == 27
    assert body["goals"] == []

    made = authenticated_client.put("/api/new-year-challenge/2027/pledge",
                                    json={"goals": {"books": 12, "movies": 40, "music": None}})
    assert made.status_code == 200, made.text
    data = made.json()
    assert data["pledged"] and [goal["category"] for goal in data["goals"]] == ["movies", "books"]
    assert data["weekly_hours"] == round((12 * 8 + 40 * 115 / 60) / 52, 1)
    assert data["goals"][0]["pace"]["status"] == "not_started"
    # The numbers are ordinary yearly goals.
    user = _user(db_session)
    rows = {row.category: row.target for row in db_session.query(models.YearlyGoal).filter_by(user_id=user.id, year=2027)}
    assert rows == {"books": 12, "movies": 40}
    assert authenticated_client.get("/api/goals?year=2027").json()["goals"][0]["category"] == "movies"

    # Leaving out a category leaves it alone; null removes it.
    authenticated_client.put("/api/goals/2027/anime", json={"target": 4})
    updated = authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"movies": None, "books": 15}}).json()
    assert {goal["category"]: goal["target"] for goal in updated["goals"]} == {"anime": 4, "books": 15}
    assert db_session.query(models.YearPledge).filter_by(user_id=user.id, year=2027).count() == 1

    card = authenticated_client.get("/api/new-year-challenge").json()
    assert card["show"] and card["pledged"] and card["goals"] == 2 and card["page"] == "/new-year-challenge/2027"

    assert authenticated_client.delete("/api/new-year-challenge/2027/pledge").json()["pledged"] is False
    assert authenticated_client.delete("/api/new-year-challenge/2027/pledge").status_code == 404
    assert db_session.query(models.YearlyGoal).filter_by(user_id=user.id, year=2027).count() == 2


@pytest.mark.parametrize("payload", [
    {"goals": {}},
    {"goals": {"comics": 3}},
    {"goals": {"books": 0}},
    {"goals": {"books": 1001}},
    {"goals": {"books": -2}},
    {"goals": {"books": None}},
])
def test_pledge_validation(authenticated_client, db_session, december, payload):
    response = authenticated_client.put("/api/new-year-challenge/2027/pledge", json=payload)
    assert response.status_code == 422
    assert db_session.query(models.YearPledge).count() == 0


def test_cannot_empty_a_pledge(authenticated_client, december):
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 3}})
    response = authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": None}})
    assert response.status_code == 422 and response.json()["detail"] == "Pick at least one goal."


def test_pledges_belong_to_one_member(authenticated_client, db_session, december):
    other = _other(db_session, "pledgeother")
    db_session.add(models.YearPledge(user_id=other.id, year=2027))
    db_session.add(models.YearlyGoal(user_id=other.id, year=2027, category="books", target=9))
    db_session.commit()
    body = authenticated_client.get("/api/new-year-challenge/2027").json()
    assert body["pledged"] is False and body["goals"] == []


# ---------------------------------------------------------------- suggestions

def test_suggestions_from_last_year(db_session, authenticated_client, counts):
    user = _user(db_session)
    user.created_at = datetime(2026, 7, 1)
    db_session.commit()
    rows = nyc.suggestions(db_session, user, 2027, today=DECEMBER)
    assert rows["year"] == 2026 and rows["partial"] and rows["projected"]
    books = rows["categories"]["books"]
    # 158 days tracked (July 1 to December 5) would make 9 books about 21; the projection stops at double.
    assert books == {"done": 9, "projected": 18, "keep": 18, "more": 23, "stretch": 27}
    assert rows["categories"]["music"]["keep"] == 2 and rows["categories"]["music"]["more"] == 3
    assert rows["categories"]["all"]["done"] == 30
    assert "anime" not in rows["categories"]


def test_new_members_get_counts_without_projection(db_session, authenticated_client, counts):
    user = _user(db_session)
    user.created_at = datetime(2026, 11, 1)
    db_session.commit()
    rows = nyc.suggestions(db_session, user, 2027, today=DECEMBER)
    assert not rows["projected"]
    assert rows["categories"]["books"] == {"done": 9, "projected": 9, "keep": 9, "more": 11, "stretch": 14}


def test_projection_never_more_than_doubles(db_session, authenticated_client, counts):
    user = _user(db_session)
    user.created_at = datetime(2026, 10, 1)
    db_session.commit()
    rows = nyc.suggestions(db_session, user, 2027, today=DECEMBER)
    assert rows["categories"]["movies"]["projected"] == 40


# ---------------------------------------------------------------- sharing

def test_share_card_and_page(authenticated_client, client, db_session, december):
    assert authenticated_client.put("/api/new-year-challenge/2027/share").status_code == 404
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12, "movies": 40, "all": 60}})
    shared = authenticated_client.put("/api/new-year-challenge/2027/share").json()
    assert shared["shared"] and shared["url"].startswith(nyc.SITE_URL + "/pledge/")
    token = shared["url"].rsplit("/", 1)[1]
    again = authenticated_client.put("/api/new-year-challenge/2027/share").json()
    assert again["url"] == shared["url"]

    page = client.get(f"/pledge/{token}", headers=CHROME)
    assert page.status_code == 200 and page.headers["X-Robots-Tag"] == "noindex, follow"
    html = page.text
    assert "testuser&#x27;s 2027 challenge" in html
    assert "Read 12 books" in html and "Watch 40 movies" in html and "Finish 60 titles" in html
    assert "Starts January 1" in html
    card = client.get(f"/pledge/{token}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png" and card.content[:4] == b"\x89PNG"

    # Private shelves drop out of the shared pledge, along with the overall number.
    user = _user(db_session)
    user.books_private = True
    db_session.commit()
    html = client.get(f"/pledge/{token}").text
    assert "Read 12 books" not in html and "Finish 60 titles" not in html and "Watch 40 movies" in html

    user.movies_private = True
    db_session.commit()
    assert client.get(f"/pledge/{token}").status_code == 404
    assert authenticated_client.put("/api/new-year-challenge/2027/share").status_code == 422

    user.books_private = user.movies_private = False
    db_session.commit()
    assert authenticated_client.delete("/api/new-year-challenge/2027/share").json()["shared"] is False
    assert client.get(f"/pledge/{token}").status_code == 404
    assert client.get("/pledge/nope").status_code == 404
    assert client.get("/pledge/" + "x" * 40).status_code == 404


def test_cannot_share_when_every_goal_is_private(authenticated_client, db_session, december):
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}})
    user = _user(db_session)
    user.books_private = True
    db_session.commit()
    response = authenticated_client.put("/api/new-year-challenge/2027/share")
    assert response.status_code == 422


def test_shared_pledge_shows_progress_once_the_year_starts(authenticated_client, client, db_session, monkeypatch):
    monkeypatch.setattr(nyc, "_today", lambda: DECEMBER)
    monkeypatch.setattr(goals, "allowed_years", lambda today=None: [2026, 2027])
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 4}})
    token = authenticated_client.put("/api/new-year-challenge/2027/share").json()["url"].rsplit("/", 1)[1]
    monkeypatch.setattr(nyc, "has_started", lambda year, today=None: True)
    monkeypatch.setattr(year_in_review, "finished_counts",
                        lambda db, user_id, year: {**{key: 0 for key in year_in_review.CATEGORIES}, "books": 1})
    html = client.get(f"/pledge/{token}").text
    assert "1 of 4 books" in html and "width: 25%" in html


# ---------------------------------------------------------------- public numbers

def test_public_counts_need_three_pledges(db_session, december):
    assert nyc.public_counts(db_session, 2027) == {"pledged": 0, "show": False, "categories": [], "titles": 0}
    targets = [12, 20, 30]
    for index, target in enumerate(targets):
        user = _other(db_session, f"pledger{index}")
        db_session.add(models.YearPledge(user_id=user.id, year=2027))
        db_session.add(models.YearlyGoal(user_id=user.id, year=2027, category="books", target=target))
        if index == 0:
            db_session.add(models.YearlyGoal(user_id=user.id, year=2027, category="video-games", target=5))
            db_session.add(models.YearlyGoal(user_id=user.id, year=2027, category="all", target=100))
    # Goals without a pledge are not part of the challenge.
    loner = _other(db_session, "goalonly")
    db_session.add(models.YearlyGoal(user_id=loner.id, year=2027, category="books", target=500))
    db_session.commit()
    counts = nyc.public_counts(db_session, 2027)
    assert counts["show"] and counts["pledged"] == 3 and counts["titles"] == 67
    assert counts["categories"] == [{"key": "books", "members": 3, "median": 20, "noun": "books"}]


# ---------------------------------------------------------------- the guide page

def test_guide_for_guests(client, december):
    page = client.get("/new-year-challenge/2027")
    assert page.status_code == 200
    html = page.text
    assert "index, follow" in html and "X-Robots-Tag" not in page.headers
    assert "The 2027 challenge" in html and "STARTS IN 27 DAYS" in html
    assert 'id="pledgeForm"' in html and 'data-member="0"' in html and 'data-sample="busy"' in html
    assert "Counted as a 320-page book at about 40 pages an hour" in html
    assert "FAQPage" in html and "ad-loader.js" in html
    assert "%2Fnew-year-challenge%2F2027%23pledge" in html
    # The cost table uses the same typical lengths as the hours estimate.
    assert "<td>about 8 hours a week</td>" not in html and "<td>8 hours a week</td>" in html
    assert client.get("/new-year-challenge", follow_redirects=False).headers["location"] == "/new-year-challenge/2027"


def test_guide_for_members_shows_last_year(authenticated_client, db_session, december, counts):
    html = authenticated_client.get("/new-year-challenge/2027").text
    assert 'data-member="1"' in html and "ad-loader.js" not in html
    assert "9 in 2026" in html and 'data-preset="more"' in html and "Make my pledge" in html
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}})
    html = authenticated_client.get("/new-year-challenge/2027").text
    assert "You&#x27;re in with 1 goal" in html and "Update my pledge" in html and 'value="12"' in html


def test_guide_is_linked_once_open(client, december):
    assert "/new-year-challenge/2027" in client.get("/sitemap.xml").text
    assert "/new-year-challenge/2027" in client.get("/llms.txt").text
    assert "Make your pledge" in client.get("/challenges").text


def test_recap_points_at_next_years_challenge(authenticated_client, december):
    html = authenticated_client.get("/year-in-review/2026").text
    assert "Pick what you&#x27;ll finish in 2027" in html and "/new-year-challenge/2027#pledge" in html
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}})
    assert "You&#x27;re in for 2027" in authenticated_client.get("/year-in-review/2026").text


def test_funnel_counts_pledges(authenticated_client, december, monkeypatch):
    from app import funnel
    seen = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: seen.append(event) or True)
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 12}})
    authenticated_client.put("/api/new-year-challenge/2027/pledge", json={"goals": {"books": 14}})
    authenticated_client.put("/api/new-year-challenge/2027/share")
    authenticated_client.put("/api/new-year-challenge/2027/share")
    assert seen.count("pledge_made") == 1 and seen.count("pledge_link_created") == 1
    assert "pledge_signup_clicked" in funnel.CLIENT_EVENTS
