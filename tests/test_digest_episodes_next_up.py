"""Weekly email: new episodes this week, the Next Up nudge, and the Emails settings (Oct 28)."""
import json
from datetime import date, datetime, timedelta

from app import announcements, digest, episode_calendar, for_you, models
from tests.test_digest_friend_activity import run
from tests.test_episode_calendar import tvmaze_episode, tvmaze_show
from tests.test_for_you import TODAY, member, pinned_today  # noqa: F401  (fixture)

NOW = datetime(2026, 9, 29, 12)


def cache_schedule(db, title, year, episodes):
    data = episode_calendar.tvmaze_episodes(tvmaze_show(name=title), episodes, TODAY)
    db.add(models.TitleMetadata(key=episode_calendar.airing_key("tv-shows", title, year), status="ok",
                                data=json.dumps(data), fetched_at=datetime.utcnow()))
    db.flush()


def test_week_ahead_groups_episodes_by_show_and_skips_finished_shows(db_session):
    me = member(db_session, "me")
    db_session.add_all([
        models.TVShow(user_id=me.id, title="Severance", year=2022),
        models.TVShow(user_id=me.id, title="Done Show", year=2020, watched=True),
    ])
    cache_schedule(db_session, "Severance", 2022, [
        tvmaze_episode(2, 5, TODAY + timedelta(days=1), name="Trojan's Horse"),
        tvmaze_episode(2, 6, TODAY + timedelta(days=6)),
        tvmaze_episode(2, 7, TODAY + timedelta(days=8)),
        tvmaze_episode(2, 4, TODAY - timedelta(days=2)),
    ])
    cache_schedule(db_session, "Done Show", 2020, [tvmaze_episode(1, 1, TODAY + timedelta(days=2))])
    db_session.commit()

    shows = episode_calendar.week_ahead(db_session, me, TODAY)
    assert [show["title"] for show in shows] == ["Severance"]
    assert [e["code"] for e in shows[0]["episodes"]] == ["S2E5", "S2E6"]
    assert shows[0]["url"].endswith("/tv/severance-2022")

    html, text = digest._episodes_section(shows)
    assert "- Severance: S2E5, “Trojan's Horse”, on Wed Sep 30 and 1 more this week" in text
    assert "Trojan&#x27;s Horse" in html


def test_episodes_alone_make_an_email_with_their_own_subject():
    shows = [{"title": "Severance", "category": "tv-shows", "url": "https://x/tv/severance-2022",
              "episodes": [{"code": "S2E5", "date": "2026-09-30", "name": ""}]},
             {"title": "Frieren", "category": "anime", "url": "https://x/anime/frieren",
              "episodes": [{"code": "episode 12", "date": "2026-10-01", "name": ""}]}]
    subject, html, text = digest.build_digest("me", {"matches": [], "popular": []}, "https://x/unsub", episodes=shows)
    assert subject == "New this week: Severance S2E5 and 1 more show"
    assert "here is what airs this week" in html and "New episodes this week" in html
    assert "- Frieren: Episode 12 on Thu Oct 1" in text


def test_next_up_line_skips_finished_and_deleted_titles(db_session):
    me = member(db_session, "me")
    done = models.Movie(user_id=me.id, title="Seen It", year=2001, watched=True)
    first = models.Book(user_id=me.id, title="Piranesi", author="S. Clarke", year=2020)
    second = models.VideoGame(user_id=me.id, title="Hades")
    db_session.add_all([done, first, second])
    db_session.flush()
    db_session.add_all([
        models.NextUpItem(user_id=me.id, category="movies", item_id=done.id, position=0),
        models.NextUpItem(user_id=me.id, category="tv-shows", item_id=99999, position=1),
        models.NextUpItem(user_id=me.id, category="books", item_id=first.id, position=2),
        models.NextUpItem(user_id=me.id, category="video-games", item_id=second.id, position=3),
    ])
    db_session.commit()
    line = digest.next_up_line(db_session, me.id)
    assert line == {"title": "Piranesi", "label": "Book", "waiting": 1}
    _html, text = digest._next_up_section(line, "https://x")
    assert text[0] == ("Next in your queue: Piranesi (Book) is at the top. "
                       "1 more title waits behind it. https://x/#next-up")
    assert digest.next_up_line(db_session, member(db_session, "empty").id) is None


def test_next_up_never_forces_a_send(db_session):
    nudge = {"title": "Piranesi", "label": "Book", "waiting": 0}
    assert digest.build_digest("me", {"matches": [], "popular": []}, "https://x/unsub", next_up=nudge) is None


def test_a_quiet_week_with_new_episodes_still_sends(db_session, pinned_today, monkeypatch):  # noqa: F811
    monkeypatch.setattr(for_you, "upcoming_popular", lambda *a, **k: [])
    me, quiet = member(db_session, "me"), member(db_session, "quiet")
    db_session.add(models.TVShow(user_id=me.id, title="Severance", year=2022))
    cache_schedule(db_session, "Severance", 2022, [tvmaze_episode(2, 5, TODAY + timedelta(days=2))])
    for user in (me, quiet):
        digest.subscribe(db_session, user.id)
        # Both got a round-up last week, so only real news sends this week.
        digest.subscription_for(db_session, user.id).last_sent_at = NOW - timedelta(days=8)
    db_session.commit()
    sent = run(now=NOW)
    assert [to for to, _s, _h in sent] == ["me@example.com"]
    assert sent[0][1] == "New this week: Severance S2E5"


def test_digest_members_due_soon_get_their_shows_refreshed(db_session):
    due, later = member(db_session, "due"), member(db_session, "later")
    digest.subscribe(db_session, due.id)
    digest.subscribe(db_session, later.id)
    digest.subscription_for(db_session, later.id).last_checked_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    assert episode_calendar._subscribers(db_session) == [due.id]


def test_emails_settings_toggle_both_kinds(authenticated_client, db_session):
    state = authenticated_client.get("/api/for-you/email").json()
    assert state["enabled"] is False and state["updates"] is True  # weekly stays off until asked for

    state = authenticated_client.put("/api/for-you/email", json={"updates": False}).json()
    assert state == {**state, "enabled": False, "updates": False}
    user = db_session.query(models.User).filter_by(username="testuser").one()
    assert announcements.opted_out(db_session, user.id)

    state = authenticated_client.put("/api/for-you/email", json={"enabled": True}).json()
    assert state["enabled"] is True and state["updates"] is False

    state = authenticated_client.put("/api/for-you/email", json={"updates": True}).json()
    assert state["enabled"] is True and state["updates"] is True
    assert not announcements.opted_out(db_session, user.id)

    state = authenticated_client.put("/api/for-you/email", json={"enabled": False}).json()
    assert state["enabled"] is False and digest.subscription_for(db_session, user.id) is None
