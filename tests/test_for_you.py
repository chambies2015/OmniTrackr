"""Starter picks, "Coming up for you", the weekly email, and editor collections."""
import asyncio
import time
from datetime import date, datetime, timedelta

import pytest

from app import auth, digest, editorial_collections, for_you, models
from app import release_radar as radar
from tests.conftest import TestingSessionLocal

TODAY = date(2026, 9, 29)


def member(db, username, verified=True):
    user = models.User(username=username, email=f"{username}@example.com", is_verified=verified,
                       hashed_password=auth.get_password_hash("password123"))
    db.add(user)
    db.flush()
    return user


def me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def seed_cache(items_by_category):
    for category, items in items_by_category.items():
        window = radar.current_window(category, TODAY)
        for item in items:
            item["window"] = window.slug
        radar.CACHE.entries[window.cache_key] = {"items": items, "fetched_at": time.time(), "error": None}


def radar_item(category, key, title, day, popularity=10.0):
    return radar.make_item(category=category, key=key, title=title, release_date=day.isoformat(),
                           source_url=None, image="https://img.example/x.jpg", popularity=popularity,
                           save={"title": title, "year": day.year})


@pytest.fixture
def pinned_today(monkeypatch):
    monkeypatch.setattr(radar, "today_utc", lambda: TODAY)
    return TODAY


# ---------------------------------------------------------------- matching rules

@pytest.mark.parametrize("mine,theirs,expected", [
    ("Jujutsu Kaisen", "Jujutsu Kaisen Season 3", True),
    ("The Last of Us", "Last of Us", True),
    ("Dune", "Dune: Part Three", True),
    ("Stranger Things", "Stranger Things", True),
    ("It", "It Ends With Us", False),          # too short to match safely
    ("Heat", "Heatwave", False),               # word boundary required
    ("One Piece", "One Punch Man", False),
])
def test_titles_match_new_seasons_and_sequels(mine, theirs, expected):
    assert for_you._matches(mine, theirs) is expected


# ---------------------------------------------------------------- starter picks

def test_popular_picks_need_two_members_and_skip_what_you_own(authenticated_client, db_session, pinned_today):
    a, b = member(db_session, "pa"), member(db_session, "pb")
    db_session.add_all([
        models.Movie(user_id=a.id, title="Arrival", director="Denis Villeneuve", year=2016,
                     poster_url="https://img.example/arrival.jpg", rating=9.5, review="My private thoughts"),
        models.Movie(user_id=b.id, title="arrival", director="", year=2016),
        models.Movie(user_id=a.id, title="Only One Member", director="X", year=2000),
        models.Book(user_id=a.id, title="Dune", author="Frank Herbert", year=1965),
        models.Book(user_id=b.id, title="Dune", author="Frank Herbert", year=1965),
        models.Book(user_id=me(db_session).id, title="Dune", author="Frank Herbert", year=1965),
    ])
    db_session.commit()
    data = authenticated_client.get("/api/for-you/starter-picks").json()
    titles = [(pick["category"], pick["title"]) for pick in data["popular"]]
    assert ("movies", "Arrival") in titles
    assert all(title != "Only One Member" for _, title in titles)
    assert ("books", "Dune") not in titles  # already in this member's library
    arrival = next(pick for pick in data["popular"] if pick["title"] == "Arrival")
    assert arrival["members"] == 2 and arrival["image"] == "https://img.example/arrival.jpg"
    assert data["library_total"] == 1 and data["goal"] == 5


def test_adding_a_pick_copies_only_public_details(authenticated_client, db_session):
    a, b = member(db_session, "pa"), member(db_session, "pb")
    db_session.add_all([
        models.Movie(user_id=a.id, title="Arrival", director="Denis Villeneuve", year=2016,
                     poster_url="https://img.example/arrival.jpg", rating=9.5, review="Private", watched=True),
        models.Movie(user_id=b.id, title="Arrival", director="Denis Villeneuve", year=2016, watched=True),
    ])
    db_session.commit()
    response = authenticated_client.post("/api/for-you/starter-picks/add", json={"category": "movies", "title": "Arrival"})
    assert response.status_code == 200 and response.json()["state"] == "created"
    mine = db_session.query(models.Movie).filter_by(user_id=me(db_session).id).one()
    assert (mine.title, mine.director, mine.year, mine.poster_url) == ("Arrival", "Denis Villeneuve", 2016, "https://img.example/arrival.jpg")
    assert mine.rating is None and mine.review is None and mine.watched is False and mine.review_public is False
    again = authenticated_client.post("/api/for-you/starter-picks/add", json={"category": "movies", "title": "arrival "})
    assert again.json()["state"] == "existing"
    assert db_session.query(models.Movie).filter_by(user_id=me(db_session).id).count() == 1


def test_only_popular_titles_can_be_added_this_way(authenticated_client, db_session):
    a = member(db_session, "pa")
    db_session.add(models.Movie(user_id=a.id, title="Niche", director="Y", year=1999))
    db_session.commit()
    assert authenticated_client.post("/api/for-you/starter-picks/add", json={"category": "movies", "title": "Niche"}).status_code == 404
    assert authenticated_client.post("/api/for-you/starter-picks/add", json={"category": "podcasts", "title": "Niche"}).status_code == 422


def test_editor_account_never_makes_a_title_popular(authenticated_client, db_session):
    editor = models.User(username=editorial_collections.EDITOR_USERNAME, email=editorial_collections.EDITOR_EMAIL,
                         hashed_password="x", is_verified=True)
    a = member(db_session, "pa")
    db_session.add(editor)
    db_session.flush()
    db_session.add_all([
        models.Movie(user_id=editor.id, title="Primer", director="Shane Carruth", year=2004),
        models.Movie(user_id=a.id, title="Primer", director="Shane Carruth", year=2004),
    ])
    db_session.commit()
    picks = authenticated_client.get("/api/for-you/starter-picks").json()["popular"]
    assert all(pick["title"] != "Primer" for pick in picks)


def test_starter_picks_include_upcoming_radar_titles(authenticated_client, db_session, pinned_today):
    seed_cache({"games": [radar_item("games", "g1", "Big Upcoming Game", TODAY + timedelta(days=5), 90)]})
    upcoming = authenticated_client.get("/api/for-you/starter-picks").json()["upcoming"]
    assert upcoming[0]["title"] == "Big Upcoming Game"
    assert upcoming[0]["window"] == radar.current_window("games", TODAY).slug
    assert upcoming[0]["url"].startswith("/release-radar/games#item-")


def test_starter_picks_require_login(client):
    assert client.get("/api/for-you/starter-picks").status_code == 401
    assert client.post("/api/for-you/starter-picks/add", json={"category": "movies", "title": "x"}).status_code == 401


# ---------------------------------------------------------------- coming up for you

def test_coming_up_matches_library_titles(authenticated_client, db_session, pinned_today):
    user = me(db_session)
    db_session.add_all([
        models.Anime(user_id=user.id, title="Jujutsu Kaisen", year=2020),
        models.TVShow(user_id=user.id, title="Severance", year=2022),
    ])
    db_session.commit()
    seed_cache({
        "anime": [radar_item("anime", "a1", "Jujutsu Kaisen Season 3", TODAY + timedelta(days=10))],
        "tv": [radar_item("tv", "t1", "Severance", TODAY + timedelta(days=3)),
               radar_item("tv", "t2", "Unrelated Show", TODAY + timedelta(days=4), popularity=99),
               radar_item("tv", "t3", "Severance", TODAY + timedelta(days=200))],
    })
    data = authenticated_client.get("/api/for-you/coming-up").json()
    assert [card["title"] for card in data["matches"]] == ["Severance", "Jujutsu Kaisen Season 3"]
    assert data["matches"][0]["reason"] == "In your library: Severance"
    assert data["matches"][1]["reason"] == "Because you track Jujutsu Kaisen"
    assert [card["title"] for card in data["popular"]] == ["Unrelated Show"]
    assert data["email"]["enabled"] is False


def test_coming_up_with_no_matches_offers_popular_releases(authenticated_client, db_session, pinned_today):
    db_session.add(models.Movie(user_id=me(db_session).id, title="Heat", director="Michael Mann", year=1995))
    db_session.commit()
    seed_cache({"movies": [radar_item("movies", "m1", "Heatwave", TODAY + timedelta(days=2))]})
    data = authenticated_client.get("/api/for-you/coming-up").json()
    assert data["matches"] == []
    assert data["popular"][0]["title"] == "Heatwave"


# ---------------------------------------------------------------- weekly email preference

def test_email_opt_in_and_out(authenticated_client, db_session):
    assert authenticated_client.get("/api/for-you/email").json()["enabled"] is False
    on = authenticated_client.put("/api/for-you/email", json={"enabled": True})
    assert on.status_code == 200 and on.json()["enabled"] is True
    row = db_session.query(models.EmailDigestSubscription).one()
    assert len(row.token) >= 32
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True}).status_code == 200
    assert db_session.query(models.EmailDigestSubscription).count() == 1
    off = authenticated_client.put("/api/for-you/email", json={"enabled": False})
    assert off.json()["enabled"] is False
    assert db_session.query(models.EmailDigestSubscription).count() == 0


def test_unverified_members_cannot_opt_in(authenticated_client, db_session):
    user = me(db_session)
    user.is_verified = False
    db_session.commit()
    response = authenticated_client.put("/api/for-you/email", json={"enabled": True})
    assert response.status_code in (400, 401, 403)


def test_unsubscribe_link_needs_a_button_press(client, db_session):
    user = member(db_session, "mailme")
    db_session.commit()
    row = digest.subscribe(db_session, user.id)
    page = client.get(f"/email/unsubscribe?token={row.token}")
    assert page.status_code == 200
    assert 'method="post"' in page.text and "Stop the weekly email?" in page.text
    assert "noindex" in page.headers["X-Robots-Tag"]
    assert db_session.query(models.EmailDigestSubscription).count() == 1  # a GET never unsubscribes
    done = client.post(f"/email/unsubscribe?token={row.token}")
    assert done.status_code == 200 and "unsubscribed" in done.text
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    stale = client.get(f"/email/unsubscribe?token={row.token}")
    assert "not subscribed" in stale.text


def test_unsubscribe_rejects_junk_tokens(client):
    assert "not subscribed" in client.get('/email/unsubscribe?token="><script>').text
    assert client.post("/email/unsubscribe?token=nope").status_code == 200


# ---------------------------------------------------------------- sending digests

def _report(matches=1, popular=0):
    card = {"title": "Severance <b>", "label": "TV", "date": "2026-10-02", "url": "/release-radar/tv#item-t1",
            "reason": "In your library: Severance"}
    return {"matches": [card] * matches, "popular": [dict(card, reason="")] * popular}


def test_digest_content_is_escaped_and_has_one_click_unsubscribe():
    subject, html, text = digest.build_digest("dan<script>", _report(), "https://omnitrackr.xyz/email/unsubscribe?token=abc")
    assert subject.startswith("Coming up for you: Severance")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Severance &lt;b&gt;" in html
    assert "unsubscribe?token=abc" in html and "unsubscribe?token=abc" in text
    assert digest.build_digest("dan", _report(0, 0), "u") is None


def run_digests(**kwargs):
    sent = []

    async def fake_sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, unsubscribe_url))

    stats = asyncio.run(digest.send_due_digests(TestingSessionLocal, sender=fake_sender, today=TODAY, **kwargs))
    return stats, sent


def test_digests_go_weekly_and_only_when_there_is_news(db_session, pinned_today, monkeypatch):
    fan = member(db_session, "fan")
    quiet = member(db_session, "quiet")
    unverified = member(db_session, "unverified", verified=False)
    db_session.add(models.TVShow(user_id=fan.id, title="Severance", year=2022))
    db_session.commit()
    for user in (fan, quiet, unverified):
        digest.subscribe(db_session, user.id)
    monkeypatch.setattr(for_you, "upcoming_popular", lambda *a, **k: [])
    seed_cache({"tv": [radar_item("tv", "t1", "Severance", TODAY + timedelta(days=3))]})
    now = datetime(2026, 9, 29, 12)

    stats, sent = run_digests(now=now)
    assert [to for to, _, _ in sent] == ["fan@example.com"]
    assert sent[0][2].startswith("https://") and "/email/unsubscribe?token=" in sent[0][2]
    assert stats == {"sent": 1, "skipped": 2, "failed": 0, "limited": 0}

    assert run_digests(now=now + timedelta(days=3))[1] == []            # not due yet
    assert len(run_digests(now=now + timedelta(days=7))[1]) == 1         # a week later


def test_daily_limit_protects_the_free_mail_plan(db_session, pinned_today, monkeypatch):
    monkeypatch.setenv("DIGEST_DAILY_LIMIT", "2")
    seed_cache({"tv": [radar_item("tv", "t1", "Severance", TODAY + timedelta(days=3))]})
    for index in range(4):
        user = member(db_session, f"fan{index}")
        db_session.add(models.TVShow(user_id=user.id, title="Severance", year=2022))
        db_session.commit()
        digest.subscribe(db_session, user.id)
    stats, sent = run_digests(now=datetime(2026, 9, 29, 12))
    assert len(sent) == 2 and stats["limited"] == 2
    stats, sent = run_digests(now=datetime(2026, 9, 29, 18))
    assert sent == []                                     # still inside the same 24 hours
    stats, sent = run_digests(now=datetime(2026, 9, 30, 13))
    assert len(sent) == 2                                 # the rest go the next day


def test_a_failed_send_does_not_stop_the_others(db_session, pinned_today):
    seed_cache({"tv": [radar_item("tv", "t1", "Severance", TODAY + timedelta(days=3))]})
    for name in ("broken", "fine"):
        user = member(db_session, name)
        db_session.add(models.TVShow(user_id=user.id, title="Severance", year=2022))
        db_session.commit()
        digest.subscribe(db_session, user.id)
    delivered = []

    async def flaky(to, subject, html, url):
        if to.startswith("broken"):
            raise RuntimeError("smtp down")
        delivered.append(to)

    stats = asyncio.run(digest.send_due_digests(TestingSessionLocal, sender=flaky, today=TODAY, now=datetime(2026, 9, 29)))
    assert delivered == ["fine@example.com"] and stats["failed"] == 1


def test_background_emails_are_off_in_tests(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    assert digest.enabled_for_process() is False
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("DIGEST_EMAILS", "off")
    assert digest.enabled_for_process() is False


# ---------------------------------------------------------------- editor collections

def test_editor_collections_publish_listed_and_idempotent(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    status = authenticated_client.get("/api/site-stats/overview").json()["editor_collections"]
    assert status["published"] == 0 and status["available"] == len(editorial_collections.COLLECTIONS)

    first = authenticated_client.post("/api/site-stats/editor-collections")
    assert first.status_code == 200
    created = first.json()["created"]
    assert len(created) == len(editorial_collections.COLLECTIONS)
    assert all(item["listed"] for item in created)

    second = authenticated_client.post("/api/site-stats/editor-collections").json()
    assert second["created"] == [] and len(second["skipped"]) == len(created)
    editor = db_session.query(models.User).filter_by(username=editorial_collections.EDITOR_USERNAME).one()
    assert db_session.query(models.Collection).filter_by(user_id=editor.id, is_public=True).count() == len(created)

    gallery = authenticated_client.get("/collections/explore")
    assert gallery.status_code == 200
    assert "Anime Gateways: Where to Start" in gallery.text
    # Nobody can sign in as the editors account.
    login = authenticated_client.post("/auth/login", data={"username": editor.username, "password": ""})
    assert login.status_code in (401, 422)


def test_editor_collections_are_admin_only(authenticated_client, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "someone-else")
    assert authenticated_client.post("/api/site-stats/editor-collections").status_code == 403


def test_editor_username_taken_by_a_member_is_never_used(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    member_row = models.User(username=editorial_collections.EDITOR_USERNAME, email="squatter@example.com", hashed_password="keep")
    db_session.add(member_row)
    db_session.commit()
    response = authenticated_client.post("/api/site-stats/editor-collections")
    assert response.status_code == 409
    db_session.refresh(member_row)
    assert member_row.hashed_password == "keep"
    assert db_session.query(models.Collection).count() == 0


def test_every_editor_collection_passes_the_public_quality_bar():
    from app.collection_quality import evaluate_public_collection
    for spec in editorial_collections.COLLECTIONS:
        quality = evaluate_public_collection(spec["name"], spec["description"], len(spec["items"]),
                                             [item[4] for item in spec["items"]])
        assert quality.discover_ready, spec["name"]
        assert all(len(item[4]) >= 40 for item in spec["items"]), spec["name"]


def test_artwork_lookup_is_best_effort(monkeypatch):
    class Boom:
        async def get(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setenv("OMDB_API_KEY", "k")
    assert asyncio.run(editorial_collections._artwork(Boom(), "movies", "Arrival", 2016, None)) is None
    assert asyncio.run(editorial_collections._artwork(None, "books", "Dune", 1965, "Frank Herbert")) is None
