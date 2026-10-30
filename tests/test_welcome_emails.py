"""Welcome emails (Oct 30): three short emails in a new member's first week."""
import asyncio
from datetime import datetime, timedelta

import pytest

from app import announcements, auth, digest, models, welcome_emails

NOW = datetime(2026, 11, 20, 12, 0)
STARTED = NOW - timedelta(days=20)


def member(db, name, *, joined_days_ago=1.2, verified=True, active=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x",
                       is_verified=verified, is_active=active,
                       created_at=NOW - timedelta(days=joined_days_ago))
    db.add(user)
    db.flush()
    return user


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


class _KeepOpen:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def run_send(db, sent, now=NOW):
    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html, unsubscribe_url))
    return asyncio.run(welcome_emails.send_due(lambda: _KeepOpen(db), now=now, sender=sender))


def recipients(sent):
    return sorted(to.split("@")[0] for to, *_ in sent)


def switch_on(db, started=STARTED):
    row = welcome_emails.state(db)
    row.status, row.started_at = "sending", started
    db.commit()


def add_movie(db, user, title="Heat", **fields):
    db.add(models.Movie(user_id=user.id, title=title, director="Michael Mann", year=1995, **fields))
    db.flush()


@pytest.fixture
def owner(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    user = member(db_session, "boss", joined_days_ago=400)
    db_session.commit()
    return user


def test_nothing_is_sent_until_the_owner_starts(db_session):
    member(db_session, "newbie")
    db_session.commit()
    sent = []
    assert run_send(db_session, sent)["sent"] == 0 and sent == []
    assert welcome_emails.status(db_session, NOW)["status"] == "draft"


def test_members_who_joined_before_the_start_never_get_one(db_session):
    member(db_session, "before", joined_days_ago=1.2)
    db_session.commit()
    switch_on(db_session, started=NOW - timedelta(days=1))
    sent = []
    run_send(db_session, sent)
    assert sent == []


def test_starting_records_the_cutoff_once(db_session):
    welcome_emails.set_status(db_session, "sending")
    first = welcome_emails.state(db_session).started_at
    welcome_emails.set_status(db_session, "paused")
    welcome_emails.set_status(db_session, "sending")
    assert first is not None and welcome_emails.state(db_session).started_at == first


def test_each_step_goes_out_once_in_its_window(db_session):
    fresh = member(db_session, "fresh", joined_days_ago=1.1)
    member(db_session, "today", joined_days_ago=0.5)
    member(db_session, "unverified", verified=False)
    member(db_session, "gone", active=False)
    member(db_session, "quiet")
    db_session.commit()
    announcements.opt_out(db_session, db_session.query(models.User).filter_by(username="quiet").one().id)
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert recipients(sent) == ["fresh"]
    assert "Fill your OmniTrackr library" in sent[0][1]
    assert "/email/updates/unsubscribe?token=" in sent[0][3]
    run_send(db_session, sent, now=NOW + timedelta(hours=3))
    assert len(sent) == 1  # never twice

    def to_fresh():
        return [subject for to, subject, *_ in sent if to == "fresh@example.com"]

    run_send(db_session, sent, now=fresh.created_at + timedelta(days=3, hours=1))
    assert to_fresh()[1:] == ["OmniTrackr is better with a friend"]
    run_send(db_session, sent, now=fresh.created_at + timedelta(days=6, hours=1))
    assert to_fresh()[2:] == ["Want to hear when something on your list comes out?"]
    assert "/email/weekly/subscribe?token=" in sent[-1][2] and "/supporters" in sent[-1][2]
    run_send(db_session, sent, now=fresh.created_at + timedelta(days=7, hours=1))
    assert len(to_fresh()) == 3
    keys = sorted(row.campaign_key for row in db_session.query(models.EmailCampaignSend).filter_by(user_id=fresh.id))
    assert keys == sorted(welcome_emails.STEP_KEYS)


def test_a_missed_window_is_dropped_not_sent_late(db_session):
    late = member(db_session, "late", joined_days_ago=3.5)
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    # Day 1 was missed: only the day 3 email goes, never the stale one.
    assert [subject for _, subject, *_ in sent] == ["OmniTrackr is better with a friend"]
    assert welcome_emails.current_step(late, NOW + timedelta(days=5)) is None


def test_the_friends_step_is_skipped_when_both_are_done(db_session):
    done = member(db_session, "social", joined_days_ago=3.1)
    pal = member(db_session, "pal", joined_days_ago=300)
    db_session.add(models.Friendship(user1_id=pal.id, user2_id=done.id))
    add_movie(db_session, done, review="A long and careful review of a great crime film. " * 3, review_public=True)
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert sent == []
    assert welcome_emails.status(db_session, NOW)["due_now"] == 0


def test_the_friends_step_asks_for_a_review_when_a_friend_is_already_there(db_session):
    me = member(db_session, "half", joined_days_ago=3.1)
    pal = member(db_session, "pal", joined_days_ago=300)
    db_session.add(models.Friendship(user1_id=me.id, user2_id=pal.id))
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert [subject for _, subject, *_ in sent] == ["Write your first OmniTrackr review"]
    assert "invite link" not in sent[0][2]


def test_product_emails_are_spaced_out(db_session):
    user = member(db_session, "busy")
    db_session.add(models.EmailCampaignSend(campaign_key=announcements.CAMPAIGN_KEY, user_id=user.id,
                                            status="sent", sent_at=NOW - timedelta(hours=10)))
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert sent == []

    weekly = member(db_session, "weekly")
    db_session.commit()
    digest.subscribe(db_session, weekly.id)
    digest.subscription_for(db_session, weekly.id).last_sent_at = NOW - timedelta(hours=2)
    db_session.commit()
    run_send(db_session, sent)
    assert sent == []


def test_day_one_and_day_six_follow_the_library_and_weekly_email(db_session):
    stocked = member(db_session, "stocked", joined_days_ago=1.1)
    add_movie(db_session, stocked)
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert sent[0][1] == "A few things to try with your OmniTrackr library"
    assert "1 title so far" in sent[0][2] and "welcome#next-up" in sent[0][2]

    digest.subscribe(db_session, stocked.id)
    step = welcome_emails.step_for(3)
    subject, html, text, _ = welcome_emails.email_for(db_session, stocked, step, NOW.date())
    assert subject == "Three small things to try on OmniTrackr"
    assert "/email/weekly/subscribe" not in html and "3 of 3" in text


def test_member_typed_titles_are_escaped(db_session):
    me = member(db_session, "typed", joined_days_ago=3.1)
    pal = member(db_session, "pal", joined_days_ago=300)
    db_session.add(models.Friendship(user1_id=me.id, user2_id=pal.id))
    db_session.commit()
    subject, html, _text = welcome_emails.build_email(
        welcome_emails.step_for(2), "<b>typed</b>", 1,
        {"friend": True, "public_review": False,
         "review_target": {"title": "<script>x</script>\nBcc: a", "path": "/titles/movie/x"}},
        "https://omnitrackr.xyz/u", None, NOW.date())
    assert "<script>" not in html and "<b>typed</b>" not in html
    assert "\n" not in subject


def test_budget_is_shared(db_session, monkeypatch):
    monkeypatch.setenv("SHARED_DAILY_CAP", "2")
    other = member(db_session, "other", joined_days_ago=300)
    for name in ("a", "b", "c"):
        member(db_session, name)
    db_session.add(models.EmailCampaignSend(campaign_key="comeback-2026-11", user_id=other.id,
                                            status="sent", sent_at=NOW - timedelta(hours=1)))
    db_session.commit()
    switch_on(db_session)
    sent = []
    run_send(db_session, sent)
    assert len(sent) == 1
    assert run_send(db_session, sent)["limited"] is True and len(sent) == 1


def test_controls_are_owner_only(client, db_session, owner):
    other = member(db_session, "someone")
    db_session.commit()
    assert client.post("/api/site-stats/welcome", json={"action": "start"}, headers=headers_for(other)).status_code == 403
    assert client.get("/site-stats/welcome-preview", headers=headers_for(other)).status_code == 403
    assert client.post("/api/site-stats/welcome", json={"action": "start"}).status_code == 401


def test_owner_can_preview_each_step_start_and_pause(client, db_session, owner):
    for step in (1, 2, 3):
        preview = client.get(f"/site-stats/welcome-preview?step={step}", headers=headers_for(owner))
        assert preview.status_code == 200 and "Preview only" in preview.text
        assert f"{step} of 3" in preview.text
        assert "default-src 'none'" in preview.headers["content-security-policy"]
    assert client.get("/site-stats/welcome-preview?step=4", headers=headers_for(owner)).status_code == 422
    started = client.post("/api/site-stats/welcome", json={"action": "start"}, headers=headers_for(owner)).json()
    assert started["status"] == "sending" and started["started_at"]
    paused = client.post("/api/site-stats/welcome", json={"action": "pause"}, headers=headers_for(owner)).json()
    assert paused["status"] == "paused"
    overview = client.get("/api/site-stats/overview", headers=headers_for(owner)).json()
    assert overview["welcome"]["status"] == "paused" and len(overview["welcome"]["steps"]) == 3


def test_test_send_goes_only_to_the_owner(client, db_session, owner, monkeypatch):
    member(db_session, "bystander")
    db_session.commit()
    sent = []

    async def fake_send(to, subject, html, unsubscribe_url):
        sent.append((to, subject))

    monkeypatch.setattr(welcome_emails, "mail_configured", lambda: True)
    monkeypatch.setattr(welcome_emails.send_test, "__defaults__", (fake_send,))
    response = client.post("/api/site-stats/welcome", json={"action": "test"}, headers=headers_for(owner))
    assert response.status_code == 200, response.text
    assert [to for to, _ in sent] == ["boss@example.com"] * 3
    assert [subject[:11] for _, subject in sent] == ["[Test 1/3] ", "[Test 2/3] ", "[Test 3/3] "]
    assert response.json()["sent_30d"] == 0
