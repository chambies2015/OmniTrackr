"""Badges: tiers counted from the library, recorded once, announced once, shown on public profiles and in the weekly email."""
from datetime import datetime

from app import badges, digest, models


def _user(db_session, name="testuser"):
    return db_session.query(models.User).filter(models.User.username == name).one()


def _books(db_session, user, count, read=True, **extra):
    db_session.add_all([models.Book(user_id=user.id, title=f"Book {index}", author="A. Writer", year=2000 + index,
                                    read=read, **extra) for index in range(count)])
    db_session.commit()


def _notes(db_session, user):
    return db_session.query(models.Notification).filter_by(user_id=user.id, type="badge_earned").all()


def _row(data, key):
    return next(row for row in data["badges"] if row["key"] == key)


def test_badges_need_login(client):
    assert client.get("/api/badges").status_code == 401
    assert client.post("/api/badges/seen").status_code == 401


def test_a_new_member_sees_every_badge_and_the_closest_ones(authenticated_client, db_session):
    response = authenticated_client.get("/api/badges")
    assert response.status_code == 200 and response.headers["Cache-Control"] == "private, no-store"
    data = response.json()
    assert len(data["badges"]) == len(badges.TRACKS) and data["total_levels"] == len(badges.TRACKS) * 3
    assert data["earned_levels"] == 0 and data["celebrate"] == [] and len(data["next"]) == 3
    bookworm = _row(data, "bookworm")
    assert (bookworm["tier"], bookworm["next_target"], bookworm["hint"]) == (0, 5, "Read 5 more books for bronze")
    assert _row(data, "company")["counts"] == "friend"  # "0 of 1 friend"
    assert _notes(db_session, _user(db_session)) == []


def test_earning_a_badge_is_announced_once_and_celebrated_until_dismissed(authenticated_client, db_session):
    user = _user(db_session)
    authenticated_client.get("/api/badges")  # first look: nothing earned yet
    _books(db_session, user, 1, review="A long and thoughtful review of this book.")
    data = authenticated_client.get("/api/badges").json()
    critic = _row(data, "critic")
    assert (critic["tier"], critic["tier_name"], critic["new"]) == (1, "Bronze", True)
    assert data["celebrate"] == ["critic"]
    notes = _notes(db_session, user)
    assert len(notes) == 1 and notes[0].link == "/#badges"
    assert notes[0].message == "New badge: Critic (bronze). See what's next in your trophy case."

    authenticated_client.get("/api/badges")
    assert len(_notes(db_session, user)) == 1  # no repeat

    assert authenticated_client.post("/api/badges/seen").json() == {"seen": 1}
    data = authenticated_client.get("/api/badges").json()
    assert data["celebrate"] == [] and _row(data, "critic")["new"] is False


def test_a_member_with_history_gets_one_summary_on_first_look(authenticated_client, db_session):
    user = _user(db_session)
    _books(db_session, user, 6, rating=8.0, review="Worth reading again some day, truly.")
    data = authenticated_client.get("/api/badges").json()
    earned = {row["key"]: row["tier"] for row in data["badges"] if row["tier"]}
    assert earned == {"collector": 1, "bookworm": 1, "critic": 1}
    notes = _notes(db_session, user)
    assert len(notes) == 1 and notes[0].message.startswith("Badges are here: you've already earned 3")


def test_tiers_go_up_and_never_down(authenticated_client, db_session):
    user = _user(db_session)
    _books(db_session, user, 5)
    assert _row(authenticated_client.get("/api/badges").json(), "bookworm")["tier"] == 1
    _books(db_session, user, 20)
    data = authenticated_client.get("/api/badges").json()
    assert _row(data, "bookworm")["tier"] == 2 and "bookworm" in data["celebrate"]
    assert _notes(db_session, user)[-1].message.startswith("New badge: Bookworm (silver).")

    db_session.query(models.Book).filter(models.Book.user_id == user.id).delete()
    db_session.commit()
    bookworm = _row(authenticated_client.get("/api/badges").json(), "bookworm")
    assert (bookworm["tier"], bookworm["count"], bookworm["next_target"]) == (2, 0, 100)
    assert db_session.query(models.UserBadge).filter_by(user_id=user.id, badge="bookworm").one().tier == 2


def test_unfinished_titles_count_for_the_collector_only(authenticated_client, db_session):
    user = _user(db_session)
    _books(db_session, user, 5, read=False)
    data = authenticated_client.get("/api/badges").json()
    assert _row(data, "collector")["tier"] == 1 and _row(data, "bookworm")["count"] == 0
    assert _row(data, "explorer")["count"] == 1


def test_badges_belong_to_one_member(authenticated_client, db_session):
    other = models.User(username="badgeother", email="badgeother@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    _books(db_session, other, 30)
    db_session.add(models.UserBadge(user_id=other.id, badge="bookworm", tier=2))
    db_session.commit()
    data = authenticated_client.get("/api/badges").json()
    assert data["earned_levels"] == 0


def test_tier_maths_and_closest_order():
    track = badges.BY_KEY["bookworm"]
    assert [badges.tier_for(track, n) for n in (0, 4, 5, 24, 25, 100, 500)] == [0, 0, 1, 1, 2, 3, 3]
    rows = [badges.badge_row(badges.BY_KEY[key], count) for key, count in
            [("bookworm", 4), ("cinephile", 1), ("critic", 0), ("explorer", 6), ("rater", 9)]]
    assert [row["key"] for row in badges.closest(rows)] == ["rater", "bookworm", "cinephile"]
    gold = badges.badge_row(badges.BY_KEY["explorer"], 6)
    assert (gold["tier_name"], gold["next_target"], gold["hint"]) == ("Gold", None, "Top tier reached")


def test_public_profile_shows_earned_badges_but_not_private_shelves(client, db_session):
    user = models.User(username="medalist", email="medalist@example.com", hashed_password="x", is_verified=True,
                       books_private=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.add_all([models.UserBadge(user_id=user.id, badge="bookworm", tier=3),
                        models.UserBadge(user_id=user.id, badge="critic", tier=2)])
    db_session.commit()
    html = client.get("/u/medalist").text
    assert 'id="profile-badges"' in html and "Critic" in html and "Silver · 10+ reviews written" in html
    assert "Bookworm" not in html
    assert "/static/badges.css" in html

    user.statistics_private = True
    db_session.commit()
    assert 'id="profile-badges"' not in client.get("/u/medalist").text


def test_weekly_email_names_the_next_badge(authenticated_client, db_session):
    user = _user(db_session)
    assert badges.digest_line(db_session, user) is None  # nothing started
    _books(db_session, user, 4)
    db_session.add(models.Movie(user_id=user.id, title="Unwatched", director="D", year=2020, watched=False))
    db_session.commit()
    line = badges.digest_line(db_session, user)
    assert line["name"] == "Bookworm" and line["action"] == "Read 1 more book"
    report = {"matches": [], "popular": [{"title": "Big Film", "label": "Movie", "date": "2026-11-01", "reason": "", "url": "/release-radar"}]}
    _, html, text = digest.build_digest("reader", report, "u", badge=line)
    assert "Your next badge" in html and "Read 1 more book to earn Bookworm bronze (4 of 5 so far)." in text
    assert digest.build_digest("reader", {"matches": [], "popular": []}, "u", badge=line) is None


def test_badge_notifications_have_a_push_title():
    from app import web_push
    assert web_push.TITLES["badge_earned"] == "New badge"
