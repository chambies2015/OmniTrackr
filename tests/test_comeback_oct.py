"""Bring members back (Oct 16): visit days, the Welcome Back Deck for open sessions, and the come-back email."""
import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import announcements, auth, comeback, digest, models, return_prompt, visits

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 12, 0)


def member(db, name, *, away_days=45, verified=True, active=True, seen_days_ago=None):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x",
                       is_verified=verified, is_active=active,
                       created_at=NOW - timedelta(days=200),
                       last_login_at=NOW - timedelta(days=away_days) if away_days is not None else None)
    if seen_days_ago is not None:
        user.last_seen_on = (NOW - timedelta(days=seen_days_ago)).date()
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
    return asyncio.run(comeback.send_due(lambda: _KeepOpen(db), now=now, sender=sender))


def recipients(sent):
    return sorted(to.split("@")[0] for to, *_ in sent)


@pytest.fixture
def owner(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    user = member(db_session, "boss", away_days=0)
    db_session.commit()
    return user


# ---------------------------------------------------------------- visit days

def test_first_visit_of_the_day_is_counted_once(client, db_session):
    user = member(db_session, "regular", away_days=10)
    user.last_seen_on = visits.today_utc() - timedelta(days=1)
    user.visit_days = 0
    db_session.commit()
    first = client.post("/account/visit", headers=headers_for(user))
    assert first.status_code == 200
    assert first.json()["return_prompt"]["eligible"] is False  # one day away is not a return
    assert first.headers["cache-control"] == "private, no-store"
    client.post("/account/visit", headers=headers_for(user))
    db_session.refresh(user)
    assert user.visit_days == 1 and user.last_seen_on == visits.today_utc()


def test_open_session_after_days_away_offers_the_welcome_back_deck(client, db_session):
    user = member(db_session, "drifter", away_days=40)
    user.last_seen_on = visits.today_utc() - timedelta(days=12)
    user.visit_days = 4
    db_session.commit()
    prompt = client.post("/account/visit", headers=headers_for(user)).json()["return_prompt"]
    assert prompt["eligible"] is True and prompt["days_away"] == 12
    assert return_prompt.return_prompt_days_away(prompt["engagement_token"], user.id) == 12
    again = client.post("/account/visit", headers=headers_for(user)).json()["return_prompt"]
    assert again["eligible"] is False  # only the first visit of the day
    db_session.refresh(user)
    assert user.visit_days == 5


def test_no_deck_before_a_visit_day_is_known(client, db_session):
    user = member(db_session, "legacy", away_days=60)  # existing rows start with no visit day
    db_session.commit()
    assert client.post("/account/visit", headers=headers_for(user)).json()["return_prompt"]["eligible"] is False


def test_visit_needs_a_session(client):
    assert client.post("/account/visit").status_code == 401


def test_login_counts_as_a_visit_and_uses_the_latest_visit_for_days_away(client, db_session, test_user_data):
    assert client.post("/auth/register", json=test_user_data).status_code == 201
    user = db_session.query(models.User).filter_by(username="testuser").one()
    user.is_verified = True
    user.last_login_at = datetime.utcnow() - timedelta(days=29)
    user.last_seen_on = visits.today_utc() - timedelta(days=1)  # used the open session yesterday
    db_session.commit()
    login = client.post("/auth/login", data={"username": "testuser", "password": test_user_data["password"]})
    assert login.status_code == 200
    assert login.json()["return_prompt"]["eligible"] is False  # not "29 days away"
    db_session.refresh(user)
    assert user.last_seen_on == visits.today_utc() and user.visit_days == 1


def test_dashboard_records_the_visit_before_the_deck():
    home = (ROOT / "app/static/dashboard/home.js").read_text(encoding="utf-8")
    boot = home[home.index("async function bootstrapReturnDeck()"):]
    assert boot.index("await recordVisitDay()") < boot.index("refreshReturnDeck()")
    assert "`${API_BASE}/account/visit`" in home and "!getReturnPromptContext()" in home


def test_migration_adds_the_columns_without_touching_rows():
    source = (ROOT / "app/migrations.py").read_text(encoding="utf-8")
    assert "ALTER TABLE users ADD COLUMN last_seen_on DATE" in source
    assert "ALTER TABLE users ADD COLUMN visit_days INTEGER DEFAULT 0" in source


# ---------------------------------------------------------------- site stats

def test_active_members_and_returns_count_visits(client, db_session, owner):
    sessioner = member(db_session, "sessioner", away_days=50)
    sessioner.last_seen_on = visits.today_utc()
    sessioner.visit_days = 3
    sessioner.login_count = 1
    for index in range(5):
        db_session.add(models.Movie(title=f"Film {index}", director="D", year=2000, user_id=sessioner.id))
    db_session.commit()
    data = client.get("/api/site-stats/overview", headers=headers_for(owner)).json()
    assert data["members"]["active_7_days"] >= 1
    stages = {stage["key"]: stage["count"] for stage in data["insights"]["activation"]}
    assert stages["returned"] == 1
    assert data["comeback"]["status"] == "draft"


# ---------------------------------------------------------------- come-back email rules

def test_nothing_is_sent_until_the_owner_starts(db_session):
    member(db_session, "away")
    db_session.commit()
    sent = []
    run_send(db_session, sent)
    assert sent == []
    comeback.set_status(db_session, "sending")
    run_send(db_session, sent)
    assert recipients(sent) == ["away"]


def test_only_members_away_30_days_who_can_be_emailed(db_session):
    member(db_session, "away")
    member(db_session, "recent", away_days=5)
    member(db_session, "session_user", away_days=90, seen_days_ago=3)  # logs in rarely, visits often
    member(db_session, "unverified", verified=False)
    member(db_session, "closed", active=False)
    opted = member(db_session, "opted")
    weekly = member(db_session, "weekly")
    db_session.add(models.EmailOptOut(user_id=opted.id))
    digest.subscribe(db_session, weekly.id)
    newbie = member(db_session, "newbie", away_days=None)
    newbie.created_at = NOW - timedelta(days=10)
    db_session.commit()
    comeback.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent)
    assert recipients(sent) == ["away"]


def test_spacing_and_stopping_after_two_without_a_visit(db_session):
    user = member(db_session, "ghost", away_days=200)
    db_session.commit()
    comeback.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent, NOW)
    run_send(db_session, sent, NOW + timedelta(days=30))  # too soon
    assert len(sent) == 1
    run_send(db_session, sent, NOW + timedelta(days=61))
    assert len(sent) == 2
    run_send(db_session, sent, NOW + timedelta(days=130))  # two unanswered: stop
    assert len(sent) == 2
    user.last_seen_on = (NOW + timedelta(days=131)).date()  # they came back by themselves
    db_session.commit()
    run_send(db_session, sent, NOW + timedelta(days=170))  # away again for 30+ days
    assert len(sent) == 3


def test_waits_for_the_whats_new_email(db_session):
    fresh = member(db_session, "fresh")
    member(db_session, "other")
    db_session.add(models.EmailCampaignSend(campaign_key=announcements.CAMPAIGN_KEY, user_id=fresh.id,
                                            status="sent", sent_at=NOW - timedelta(days=3)))
    db_session.commit()
    announcements.set_status(db_session, "sending")
    comeback.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent)
    assert sent == []  # paused while "What's new" goes out
    announcements.set_status(db_session, "done")
    run_send(db_session, sent)
    assert recipients(sent) == ["other"]  # "fresh" got What's new three days ago


def test_daily_limit_and_shared_cap(db_session, monkeypatch):
    for index in range(8):
        member(db_session, f"m{index}")
    db_session.commit()
    comeback.set_status(db_session, "sending")
    monkeypatch.setenv("COMEBACK_DAILY_LIMIT", "3")
    sent = []
    run_send(db_session, sent)
    run_send(db_session, sent, NOW + timedelta(hours=1))
    assert len(sent) == 3
    monkeypatch.setenv("COMEBACK_DAILY_LIMIT", "20")
    monkeypatch.setenv("SHARED_DAILY_CAP", "4")
    run_send(db_session, sent, NOW + timedelta(hours=2))
    assert len(sent) == 4


def test_failed_sends_are_recorded_and_not_retried(db_session):
    member(db_session, "bounce")
    db_session.commit()
    comeback.set_status(db_session, "sending")

    async def broken(*args):
        raise RuntimeError("mailbox full")

    stats = asyncio.run(comeback.send_due(lambda: _KeepOpen(db_session), now=NOW, sender=broken))
    assert stats["failed"] == 1
    sent = []
    run_send(db_session, sent, NOW + timedelta(days=1))
    assert sent == []


# ---------------------------------------------------------------- content

def test_email_is_personal_escaped_and_has_unsubscribe(db_session):
    user = member(db_session, "<b>reader</b>")
    db_session.add(models.Movie(title="Dune <script>", director="D", year=2021, user_id=user.id, watched=False))
    db_session.add(models.Movie(title="Seen It", director="D", year=2020, user_id=user.id, watched=True))
    db_session.commit()
    subject, html, text, unsubscribe_url = comeback.email_for(db_session, user, pool=None, today=NOW.date())
    assert subject == "Dune <script> is still waiting for you on OmniTrackr"
    assert "<script>" not in html and "&lt;b&gt;reader&lt;/b&gt;" in html
    assert "Seen It" not in html  # finished titles aren't "waiting"
    assert "2 titles" in text
    assert "/email/updates/unsubscribe?token=" in unsubscribe_url and unsubscribe_url in html
    assert "/email/weekly/subscribe?token=" in html
    assert "utm_campaign=come-back" in html and "/daily?" in html and "/challenges/november-2026" in html


def test_subject_stays_on_one_line():
    subject, _html, _text = comeback.build_email(
        "x", 1, [{"title": "Evil\r\nBcc: someone@example.com", "label": "Movie"}], [], "u", None, NOW.date())
    assert "\n" not in subject and "\r" not in subject


def test_upcoming_release_leads_the_subject():
    match = {"title": "Arcane", "label": "TV", "date": "2026-11-25", "reason": "In your library: Arcane",
             "url": "/release-radar/tv#item-arcane"}
    subject, html, _text = comeback.build_email("x", 3, [], [match], "u", None, NOW.date())
    assert subject == "Arcane is coming up, and it's on your list"
    assert "/release-radar/tv?utm_source=email&amp;utm_campaign=come-back#item-arcane" in html


def test_empty_library_gets_a_nudge():
    subject, _html, text = comeback.build_email("x", 0, [], [], "u", None, NOW.date())
    assert subject == "Your OmniTrackr library is ready when you are" and "Quick start" in text


# ---------------------------------------------------------------- owner controls

def test_controls_are_owner_only(client, db_session, owner):
    other = member(db_session, "someone")
    db_session.commit()
    assert client.post("/api/site-stats/comeback", json={"action": "start"}, headers=headers_for(other)).status_code == 403
    assert client.get("/site-stats/comeback-preview", headers=headers_for(other)).status_code == 403
    assert client.post("/api/site-stats/comeback", json={"action": "start"}).status_code == 401


def test_owner_can_preview_start_and_pause(client, db_session, owner):
    preview = client.get("/site-stats/comeback-preview", headers=headers_for(owner))
    assert preview.status_code == 200 and "Preview only" in preview.text
    assert "default-src 'none'" in preview.headers["content-security-policy"]
    started = client.post("/api/site-stats/comeback", json={"action": "start"}, headers=headers_for(owner)).json()
    assert started["status"] == "sending"
    paused = client.post("/api/site-stats/comeback", json={"action": "pause"}, headers=headers_for(owner)).json()
    assert paused["status"] == "paused"
    assert client.post("/api/site-stats/comeback", json={"action": "delete"}, headers=headers_for(owner)).status_code == 422


def test_test_send_goes_only_to_the_owner(client, db_session, owner, monkeypatch):
    member(db_session, "bystander")
    db_session.commit()
    sent = []

    async def fake_send(to, subject, html, unsubscribe_url):
        sent.append((to, subject))

    monkeypatch.setattr(comeback, "mail_configured", lambda: True)
    monkeypatch.setattr(comeback.send_test, "__defaults__", (None, fake_send))
    response = client.post("/api/site-stats/comeback", json={"action": "test"}, headers=headers_for(owner))
    assert response.status_code == 200, response.text
    assert [to for to, _ in sent] == ["boss@example.com"] and sent[0][1].startswith("[Test] ")
    assert response.json()["sent_all_time"] == 0


def test_came_back_counts_visits_after_an_email(db_session):
    user = member(db_session, "returner")
    db_session.commit()
    comeback.set_status(db_session, "sending")
    run_send(db_session, [])
    user.last_seen_on = (NOW + timedelta(days=2)).date()
    db_session.commit()
    info = comeback.status(db_session, NOW + timedelta(days=3))
    assert info["sent_30d"] == 1 and info["came_back"] == 1 and info["due_now"] == 0


def test_site_stats_page_has_the_card_and_report_lines():
    page = (ROOT / "app/templates/site_stats.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/site-stats.js").read_text(encoding="utf-8")
    assert 'id="comebackCard"' in page and 'href="/site-stats/comeback-preview"' in page
    assert "Come-back email: ${data.comeback.status}" in script
    assert "What's new email: ${data.announcement.status}" in script
