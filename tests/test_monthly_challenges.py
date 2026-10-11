"""Monthly challenges: opt-in progress from the month's finishes, completion, sharing and the public guides."""
from datetime import date, datetime, timedelta

import pytest

from app import challenges, models


TEST_CHALLENGE = {
    "name": "Test the strange",
    "tagline": "A test challenge.",
    "published": "2026-10-10",
    "edition": "october-2026",
    "intro": ["Intro paragraph."],
    "steps": [
        {"kind": "edition", "edition": "october-2026", "label": "Finish one October pick", "detail": "d"},
        {"kind": "formats", "count": 2, "label": "Two formats", "detail": "d"},
        {"kind": "reflect", "count": 1, "label": "Rate one", "detail": "d"},
    ],
    "reflection": "Think.",
}


@pytest.fixture
def this_month(monkeypatch):
    """Make the current month's challenge a known, curated one whatever today's date is."""
    month = challenges.month_key()
    monkeypatch.setitem(challenges.CHALLENGES, month, TEST_CHALLENGE)
    return month


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _finish(client, path, payload, done_field):
    item = client.post(path, json=dict(payload, **{done_field: True})).json()
    response = client.post("/completion-moments/", json={"category": path.strip("/"), "item_id": item["id"]})
    assert response.status_code == 200, response.text
    return item


def _moment(db_session, user, category, title, *, item_id=1, rating=None, takeaway=None, when=None):
    db_session.add(models.CompletionMoment(
        user_id=user.id, category=category, item_id=item_id, title=title, rating=rating, takeaway=takeaway,
        completed_at=when or datetime.utcnow(),
    ))
    db_session.commit()


def test_challenge_needs_login(client):
    assert client.get("/api/challenge").status_code == 401
    assert client.post("/api/challenge/join").status_code == 401
    assert client.put("/api/challenge/share").status_code == 401


def test_join_complete_celebrate_share_and_leave(authenticated_client, db_session, this_month):
    # A finish from before joining still counts.
    _finish(authenticated_client, "/movies/", {"title": "A Ghost Story", "director": "D. Lowery", "year": 2017, "rating": 8}, "watched")
    first = authenticated_client.get("/api/challenge")
    assert first.status_code == 200 and first.headers["Cache-Control"] == "private, no-store"
    data = first.json()
    assert data["joined"] is False and data["name"] == "Test the strange" and data["month"] == this_month
    assert data["url"] == f"/challenges/{challenges.slug_for(this_month)}"
    assert data["edition_url"] == "/discover/monthly/october-2026"
    assert [step["done"] for step in data["steps"]] == [True, False, True]
    assert data["done_steps"] == 2 and data["complete"] is False and data["completion"] is None

    joined = authenticated_client.post("/api/challenge/join").json()
    assert joined["joined"] is True and joined["completion"] is None
    assert authenticated_client.post("/api/challenge/join").json()["joined"] is True  # idempotent

    _finish(authenticated_client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020}, "read")
    done = authenticated_client.get("/api/challenge").json()
    assert done["complete"] is True and done["completion"]["celebrate"] is True and done["completion"]["shared"] is False
    user = _user(db_session)
    notes = db_session.query(models.Notification).filter_by(user_id=user.id, type="challenge_complete").all()
    assert len(notes) == 1 and notes[0].link == "/#challenge" and "Test the strange" in notes[0].message
    authenticated_client.get("/api/challenge")
    assert db_session.query(models.Notification).filter_by(user_id=user.id, type="challenge_complete").count() == 1

    assert authenticated_client.post("/api/challenge/seen").json()["celebrate"] is False

    shared = authenticated_client.put("/api/challenge/share").json()
    assert shared["shared"] is True and shared["url"].startswith(challenges.SITE_URL + "/challenge/")
    path = shared["url"][len(challenges.SITE_URL):]
    page = authenticated_client.get(path)
    assert page.status_code == 200 and page.headers["X-Robots-Tag"] == "noindex, follow"
    assert "testuser completed the" in page.text and "Two formats" in page.text
    assert "Piranesi" not in page.text and "A Ghost Story" not in page.text  # never the member's titles
    card = authenticated_client.get(path + "/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"

    assert authenticated_client.delete("/api/challenge/share").json()["shared"] is False
    assert authenticated_client.get(path).status_code == 404

    left = authenticated_client.delete("/api/challenge/join").json()
    assert left["joined"] is False and left["completion"] is None
    assert authenticated_client.delete("/api/challenge/join").status_code == 404


def test_completion_actions_need_a_completed_challenge(authenticated_client, this_month):
    assert authenticated_client.post("/api/challenge/seen").status_code == 404
    assert authenticated_client.put("/api/challenge/share").status_code == 404
    authenticated_client.post("/api/challenge/join")
    assert authenticated_client.put("/api/challenge/share").status_code == 404


def test_not_joined_members_get_no_completion_or_notification(authenticated_client, db_session, this_month):
    user = _user(db_session)
    _moment(db_session, user, "tv-shows", "Midnight Mass", rating=7)
    _moment(db_session, user, "books", "Dune", item_id=2)
    data = authenticated_client.get("/api/challenge").json()
    assert data["complete"] is True and data["completion"] is None
    assert db_session.query(models.Notification).filter_by(type="challenge_complete").count() == 0


def test_step_kinds(db_session, this_month, monkeypatch):
    user = models.User(username="stepper", email="stepper@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    old = models.Movie(user_id=user.id, title="Alien", year=1979, watched=True)
    new = models.Movie(user_id=user.id, title="Arrival", year=2016, watched=True)
    db_session.add_all([old, new])
    db_session.commit()
    _moment(db_session, user, "movies", "Arrival", item_id=new.id)
    # Logged twice (journal and moment) but counts once.
    db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=new.id, title="Arrival",
                                        action="completed", occurred_at=datetime.utcnow()))
    # Last month's finish never counts.
    start, _ = challenges.month_bounds(this_month)
    _moment(db_session, user, "books", "Old Book", item_id=99, rating=5, when=start - timedelta(days=1))
    db_session.commit()

    custom = dict(TEST_CHALLENGE, steps=[
        {"kind": "total", "count": 2, "label": "Two", "detail": "d"},
        {"kind": "before", "year": 2000, "label": "Old", "detail": "d"},
        {"kind": "category", "category": "movies", "count": 1, "label": "Movie", "detail": "d"},
        {"kind": "reflect", "count": 1, "label": "Note", "detail": "d"},
    ])
    monkeypatch.setitem(challenges.CHALLENGES, this_month, custom)
    steps = challenges.progress(db_session, user.id, this_month)
    assert [(step["count"], step["done"]) for step in steps] == [(1, False), (0, False), (1, True), (0, False)]

    db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=old.id, title="Alien",
                                        action="completed", note="Still terrifying.", occurred_at=datetime.utcnow()))
    db_session.commit()
    steps = challenges.progress(db_session, user.id, this_month)
    assert [(step["count"], step["done"]) for step in steps] == [(2, True), (1, True), (1, True), (1, True)]


def test_edition_step_matches_title_and_format(db_session, this_month):
    user = models.User(username="editioner", email="editioner@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.commit()
    _moment(db_session, user, "books", "a ghost story")  # Right title, wrong format.
    assert challenges.progress(db_session, user.id, this_month)[0]["done"] is False
    _moment(db_session, user, "music", "  GHOSTEEN ", item_id=5)
    assert challenges.progress(db_session, user.id, this_month)[0]["done"] is True


def test_challenges_belong_to_one_member(authenticated_client, db_session, this_month):
    other = models.User(username="challengeother", email="co@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    db_session.add(models.MonthlyChallengeEntry(user_id=other.id, month=this_month))
    _moment(db_session, other, "movies", "A Ghost Story", rating=9)
    db_session.commit()
    data = authenticated_client.get("/api/challenge").json()
    assert data["joined"] is False and data["done_steps"] == 0


def test_shared_page_hides_inactive_owner(client, db_session, this_month):
    owner = models.User(username="gone", email="gone@example.com", hashed_password="x", is_verified=True)
    db_session.add(owner)
    db_session.flush()
    db_session.add(models.MonthlyChallengeEntry(user_id=owner.id, month=this_month, completed_at=datetime.utcnow(),
                                                share_token="tok123"))
    db_session.commit()
    assert client.get("/challenge/tok123").status_code == 200
    owner.is_active = False
    db_session.commit()
    assert client.get("/challenge/tok123").status_code == 404
    assert client.get("/challenge/tok123/card.png").status_code == 404
    assert client.get("/challenge/" + "x" * 40).status_code == 404


# ---------------------------------------------------------------- public guides

@pytest.fixture
def october(monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2026-10")


def test_public_guide_is_indexable_and_substantial(client, october):
    response = client.get("/challenges/october-2026")
    assert response.status_code == 200
    html = response.text
    assert "index, follow" in html and "X-Robots-Tag" not in response.headers
    assert '<link rel="canonical" href="https://omnitrackr.xyz/challenges/october-2026">' in html
    assert "Stay with the strange" in html and '"@type": "Article"' in html
    assert "Finish one pick from the October edition" in html
    assert 'href="/discover/monthly/october-2026"' in html and "The Haunting of Hill House" in html
    assert 'id="take-challenge"' in html and "landing-auth" in html
    # Enough original writing to stand on its own for readers and reviewers.
    challenge = challenges.CHALLENGES["2026-10"]
    words = sum(len(text.split()) for text in challenge["intro"] + [step["detail"] for step in challenge["steps"]])
    assert words >= 300


def test_future_and_unknown_guides_are_not_published(client, october):
    assert client.get("/challenges/november-2026").status_code == 404
    assert client.get("/challenges/october-1999").status_code == 404
    assert client.get("/challenges/smarch-2026").status_code == 404
    assert client.get("/challenges/2026-10").status_code == 404


def test_past_guides_stay_up_without_a_join_button(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2026-11")
    html = client.get("/challenges/october-2026").text
    assert "This challenge has ended" in html and 'id="take-challenge"' not in html
    index = client.get("/challenges").text
    assert 'href="/challenges/november-2026"' in index and 'href="/challenges/october-2026"' in index


def test_index_and_discover_promote_the_current_challenge(client, october):
    index = client.get("/challenges")
    assert index.status_code == 200 and "index, follow" in index.text
    assert 'href="/challenges/october-2026"' in index.text and "november-2026" not in index.text
    assert 'href="/challenges/october-2026"' in client.get("/discover").text


def test_public_counts_appear_only_from_three_members(client, db_session, october):
    for index in range(3):
        user = models.User(username=f"c{index}", email=f"c{index}@example.com", hashed_password="x", is_verified=True)
        db_session.add(user)
        db_session.flush()
        db_session.add(models.MonthlyChallengeEntry(user_id=user.id, month="2026-10",
                                                    completed_at=datetime.utcnow() if index == 0 else None))
        db_session.commit()
        html = client.get("/challenges/october-2026").text
        assert ("3 members have taken this challenge." in html) is (index == 2)
    assert challenges.public_counts(db_session, "2026-10") == {"joined": 3, "completed": None}


def test_sitemap_lists_started_guides(client, october):
    xml = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/challenges</loc>" in xml
    assert "/challenges/october-2026</loc>" in xml and "/challenges/november-2026" not in xml


# ---------------------------------------------------------------- helpers

def test_month_helpers():
    assert challenges.month_key(date(2026, 3, 9)) == "2026-03"
    assert challenges.slug_for("2026-10") == "october-2026"
    assert challenges.month_for_slug("october-2026") == "2026-10"
    assert challenges.month_for_slug("Oct-2026") is None and challenges.month_for_slug("") is None
    assert challenges.month_bounds("2026-12") == (datetime(2026, 12, 1), datetime(2027, 1, 1))
    assert challenges.days_left("2026-10", date(2026, 10, 31)) == 1
    assert challenges.days_left("2026-10", date(2026, 10, 1)) == 31
    assert challenges.challenge_for("2031-05") is challenges.FALLBACK
    assert challenges.public_months(date(2026, 10, 1)) == ["2026-10"]
    assert challenges.public_months(date(2026, 9, 30)) == []


def test_every_curated_challenge_is_well_formed():
    kinds = {"total", "formats", "reflect", "edition", "before", "category"}
    for month, challenge in challenges.CHALLENGES.items():
        assert challenges.month_for_slug(challenges.slug_for(month)) == month
        assert challenge["name"] and challenge["tagline"] and challenge["intro"] and challenge["published"]
        assert 1 <= len(challenge["steps"]) <= 4
        for step in challenge["steps"]:
            assert step["kind"] in kinds and step["label"] and len(step["detail"].split()) >= 20
            if step["kind"] == "edition":
                from app.discover_catalog import MONTHLY_EDITIONS
                assert step["edition"] in MONTHLY_EDITIONS
            if step["kind"] == "category":
                assert step["category"] in challenges.FORMAT_NOUNS
