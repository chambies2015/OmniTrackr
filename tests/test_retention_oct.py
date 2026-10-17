"""Retention round (Oct 3): "What's new" email, installable app, out-now in the return deck, lighter dashboard."""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import announcements, auth, models


def member(db, name, verified=True, active=True, email=None):
    user = models.User(username=name, email=email or f"{name}@example.com", hashed_password="x",
                       is_verified=verified, is_active=active)
    db.add(user)
    db.flush()
    return user


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


@pytest.fixture
def owner(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    user = member(db_session, "boss")
    db_session.commit()
    return user


@pytest.fixture
def mail_on(monkeypatch):
    monkeypatch.setattr(announcements, "mail_configured", lambda: True)


class _KeepOpen:
    """The test session, with close() ignored so the fixture can keep using it."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def factory(db):
    return lambda: _KeepOpen(db)


def run_send(db, sent, now=None):
    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html, unsubscribe_url))
    return asyncio.run(announcements.send_due(factory(db), now=now or datetime.utcnow(), sender=sender))


# ---------------------------------------------------------------- campaign rules

def test_nothing_is_sent_until_the_owner_starts(db_session):
    member(db_session, "a")
    db_session.commit()
    sent = []
    run_send(db_session, sent)
    assert sent == [] and announcements.campaign(db_session).status == "draft"


def test_only_verified_active_members_once(db_session):
    member(db_session, "ok1")
    member(db_session, "ok2")
    member(db_session, "unverified", verified=False)
    member(db_session, "gone", active=False)
    from app.editorial_collections import EDITOR_USERNAME
    member(db_session, EDITOR_USERNAME)
    db_session.commit()
    announcements.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent)
    assert sorted(to for to, *_ in sent) == ["ok1@example.com", "ok2@example.com"]
    run_send(db_session, sent, now=datetime.utcnow() + timedelta(days=2))
    assert len(sent) == 2  # nobody twice
    run_send(db_session, sent, now=datetime.utcnow() + timedelta(days=3))
    assert announcements.campaign(db_session).status == "done"


def test_daily_budget_leaves_room_for_account_emails(db_session, monkeypatch):
    for i in range(50):
        member(db_session, f"m{i}")
    db_session.commit()
    announcements.set_status(db_session, "sending")
    now = datetime.utcnow()
    sent = []
    for hour in range(10):  # ten hourly checks in one day
        run_send(db_session, sent, now=now + timedelta(hours=hour))
    assert len(sent) == announcements.daily_limit() == 30


def test_weekly_emails_count_against_the_shared_cap(db_session, monkeypatch):
    for i in range(20):
        member(db_session, f"m{i}")
    digest_user = member(db_session, "digester")
    db_session.commit()
    now = datetime.utcnow()
    for i in range(75):  # pretend 75 weekly emails went out today
        sub = models.EmailDigestSubscription(user_id=digest_user.id if i == 0 else member(db_session, f"d{i}").id,
                                             token=f"t{i}", last_sent_at=now - timedelta(hours=1))
        db_session.add(sub)
    db_session.commit()
    announcements.set_status(db_session, "sending")
    assert announcements.allowance(db_session, now) == 5  # 80 shared - 75
    sent = []
    run_send(db_session, sent, now=now)
    assert len(sent) == 5


def test_pause_stops_sending(db_session):
    member(db_session, "a")
    db_session.commit()
    announcements.set_status(db_session, "sending")
    announcements.set_status(db_session, "paused")
    sent = []
    run_send(db_session, sent)
    assert sent == []


def test_failed_sends_are_recorded_and_not_retried(db_session):
    member(db_session, "bad")
    db_session.commit()
    announcements.set_status(db_session, "sending")

    async def boom(*args):
        raise RuntimeError("mailbox full")

    stats = asyncio.run(announcements.send_due(factory(db_session), sender=boom))
    assert stats["failed"] == 1
    assert announcements.status(db_session)["failed"] == 1 and announcements.status(db_session)["remaining"] == 0


# ---------------------------------------------------------------- content

def test_email_content_is_personal_safe_and_has_unsubscribe():
    subject, html, text = announcements.build_email(
        "<b>neo</b>", 12,
        [{"title": "Severance", "label": "TV", "date": "2026-10-09", "url": "/release-radar/tv#item-1", "reason": "In your library: Severance"}],
        "https://omnitrackr.xyz/email/updates/unsubscribe?token=abc")
    assert subject == "What's new on OmniTrackr: Severance is coming up"
    assert "<b>neo</b>" not in html and "&lt;b&gt;neo&lt;/b&gt;" in html
    assert "12 titles waiting" in html and "Severance" in html
    assert "Unsubscribe from product updates" in html and "utm_source=email" in html
    assert "/release-radar/tv?utm_source=email&amp;utm_campaign=whats-new#item-1" in html
    assert "Unsubscribe from product updates: https://omnitrackr.xyz/email/updates/unsubscribe?token=abc" in text


def test_empty_libraries_get_a_nudge_not_a_count():
    _subject, html, _text = announcements.build_email("neo", 0, [], "https://x/unsub")
    assert "still empty" in html and "Quick start" in html


# ---------------------------------------------------------------- unsubscribe

def test_unsubscribe_link_confirms_then_opts_out(client, db_session):
    user = member(db_session, "leaver")
    db_session.commit()
    token = announcements.unsubscribe_token(user.id)
    page = client.get(f"/email/updates/unsubscribe?token={token}")
    assert page.status_code == 200 and "Stop product update emails?" in page.text
    assert announcements.opted_out(db_session, user.id) is False  # a GET (link scanner) changes nothing
    done = client.post(f"/email/updates/unsubscribe?token={token}")
    assert done.status_code == 200 and announcements.opted_out(db_session, user.id)
    assert "already unsubscribed" in client.get(f"/email/updates/unsubscribe?token={token}").text
    announcements.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent)
    assert sent == []


def test_forged_unsubscribe_tokens_do_nothing(client, db_session):
    user = member(db_session, "victim")
    db_session.commit()
    forged = announcements.unsubscribe_token(user.id)[:-2] + "xx"
    assert "This link isn" in client.get(f"/email/updates/unsubscribe?token={forged}").text
    client.post(f"/email/updates/unsubscribe?token={forged}")
    assert announcements.opted_out(db_session, user.id) is False


# ---------------------------------------------------------------- owner controls

def test_owner_controls_are_owner_only(client, db_session, owner):
    other = member(db_session, "someone")
    db_session.commit()
    assert client.post("/api/site-stats/announcement", json={"action": "start"}, headers=headers_for(other)).status_code == 403
    assert client.get("/site-stats/announcement-preview", headers=headers_for(other)).status_code == 403
    assert client.post("/api/site-stats/announcement", json={"action": "start"}).status_code == 401


def test_owner_can_preview_start_and_pause(client, db_session, owner):
    preview = client.get("/site-stats/announcement-preview", headers=headers_for(owner))
    assert preview.status_code == 200 and "Preview only" in preview.text
    assert "default-src 'none'" in preview.headers["content-security-policy"]
    started = client.post("/api/site-stats/announcement", json={"action": "start"}, headers=headers_for(owner)).json()
    assert started["status"] == "sending"
    paused = client.post("/api/site-stats/announcement", json={"action": "pause"}, headers=headers_for(owner)).json()
    assert paused["status"] == "paused"
    bad = client.post("/api/site-stats/announcement", json={"action": "delete"}, headers=headers_for(owner))
    assert bad.status_code == 422
    overview = client.get("/api/site-stats/overview", headers=headers_for(owner)).json()
    assert overview["announcement"]["status"] == "paused"


def test_test_send_goes_only_to_the_owner(client, db_session, owner, mail_on, monkeypatch):
    member(db_session, "bystander")
    db_session.commit()
    sent = []

    async def fake_send(to, subject, html, unsubscribe_url):
        sent.append((to, subject))

    monkeypatch.setattr(announcements, "_send", fake_send)
    monkeypatch.setattr(announcements.send_test, "__defaults__", (None, fake_send))
    response = client.post("/api/site-stats/announcement", json={"action": "test"}, headers=headers_for(owner))
    assert response.status_code == 200, response.text
    assert sent == [("boss@example.com", "[Test] What's new on OmniTrackr")]
    assert announcements.status(db_session)["sent"] == 0  # a test doesn't use up the owner's real copy


# ---------------------------------------------------------------- installable app

def test_manifest_and_worker(client):
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200 and manifest.headers["content-type"].startswith("application/manifest+json")
    data = json.loads(manifest.text)
    assert data["display"] == "standalone" and data["start_url"].startswith("/")
    assert {icon["sizes"] for icon in data["icons"]} >= {"192x192", "512x512"}
    assert any(icon.get("purpose") == "maskable" for icon in data["icons"])
    for icon in data["icons"]:
        assert client.get(icon["src"]).status_code == 200
    worker = client.get("/sw.js")
    assert worker.status_code == 200 and worker.headers["cache-control"] == "no-cache"
    assert worker.headers["service-worker-allowed"] == "/"
    offline = client.get("/offline")
    assert offline.status_code == 200 and "offline" in offline.text.lower()


def test_worker_never_caches_pages_or_api():
    source = Path("app/static/sw.js").read_text(encoding="utf-8")
    assert "request.mode === 'navigate'" in source and "pageWithOfflineFallback" in source
    assert "url.pathname.startsWith('/static/') && url.searchParams.has('v')" in source
    assert "/api/" not in source.split("self.addEventListener('fetch'")[1].replace("/api/ calls", "")


def test_pages_link_the_manifest(client, authenticated_client):
    assert 'rel="manifest"' in client.get("/").text


# ---------------------------------------------------------------- dashboard shell

def test_dashboard_shell_keeps_sign_in_but_drops_marketing():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    for required in ('id="landingPage"', 'id="loginForm"', 'id="registerForm"', 'id="resetPasswordForm"',
                     'id="screenshotModal"', 'id="installAppBtn"', 'id="returnDeckReleased"', 'rel="manifest"'):
        assert required in html, required
    for removed in ('class="landing-hero"', 'class="landing-features"', 'class="landing-faq"', 'class="landing-footer"'):
        assert removed not in html, removed


# ---------------------------------------------------------------- return deck

def test_released_while_away_lists_recent_library_matches(db_session, monkeypatch):
    from app.routers import statistics
    from app import for_you, release_radar
    user = member(db_session, "returner")
    db_session.commit()
    today = release_radar.today_utc()
    monkeypatch.setattr(for_you, "radar_pool", lambda *args, **kwargs: [{"x": 1}])
    monkeypatch.setattr(for_you, "coming_up", lambda db, uid, today=None, pool=None: {"matches": [
        {"title": "Out Show", "label": "TV", "date": (today - timedelta(days=2)).isoformat(), "url": "/release-radar/tv#a", "reason": "In your library: Out Show"},
        {"title": "Future Show", "label": "TV", "date": (today + timedelta(days=5)).isoformat(), "url": "/release-radar/tv#b"},
    ]})

    class Req:
        class app:
            class state:
                external_api_client = None

    items = statistics._released_while_away(Req, db_session, user.id, 10)
    assert [item["title"] for item in items] == ["Out Show"]
    monkeypatch.setattr(for_you, "radar_pool", lambda *args, **kwargs: [])
    assert statistics._released_while_away(Req, db_session, user.id, 10) == []
