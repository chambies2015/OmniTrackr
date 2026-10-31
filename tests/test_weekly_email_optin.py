"""Weekly email opt-in (Oct 30): the sign-up box, the member preview page and where each switch came from."""
from datetime import date, datetime, timedelta

import pytest

from app import digest, models
from app.site_traffic import RECORDER


@pytest.fixture
def recorder(monkeypatch):
    """Turn the in-memory counters on (they're off in the test suite) and start empty."""
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(recorder, key):
    return sum(count for (_day, kind, name), count in recorder._pending.items() if kind == "email" and name == key)


def register(client, weekly=None, username="newfan", email="newfan@example.com"):
    payload = {"email": email, "username": username, "password": "tea on the porch"}
    if weekly is not None:
        payload["weekly_email"] = weekly
    return client.post("/auth/register", json=payload)


# ---------------------------------------------------------------- the sign-up box

def test_ticking_the_box_turns_the_weekly_email_on(client, db_session, recorder):
    response = register(client, weekly=True)
    assert response.status_code == 201
    row = db_session.query(models.EmailDigestSubscription).filter_by(user_id=response.json()["id"]).first()
    assert row is not None and len(row.token) > 20
    assert counted(recorder, "weekly_on_signup") == 1


def test_the_box_is_off_unless_ticked(client, db_session, recorder):
    assert register(client).status_code == 201
    assert register(client, weekly=False, username="otherfan", email="other@example.com").status_code == 201
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    assert counted(recorder, "weekly_on_signup") == 0


def test_the_sender_skips_members_who_have_not_verified_yet(client, db_session):
    """Ticking the box records the choice; the first email waits for a verified address."""
    import asyncio
    response = register(client, weekly=True)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append(to)

    class KeepOpen:
        def __init__(self, db):
            self._db = db

        def __getattr__(self, name):
            return getattr(self._db, name)

        def close(self):
            pass

    stats = asyncio.run(digest.send_due_digests(lambda: KeepOpen(db_session), sender=sender))
    assert sent == [] and stats["skipped"] == 1
    assert db_session.query(models.EmailDigestSubscription).filter_by(user_id=response.json()["id"]).first() is not None


def test_sign_up_form_has_the_box_and_sends_it(client):
    page = client.get("/").text
    assert 'id="registerWeekly"' in page
    assert "Email me once a week when something I track has a new episode or release" in page
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / "app" / "static" / "auth.js").read_text(encoding="utf-8")
    assert "registerWeekly" in script and "payload.weekly_email = true" in script


# ---------------------------------------------------------------- where each switch came from

def test_each_prompt_counts_its_own_opt_ins_and_opt_outs(authenticated_client, db_session, recorder):
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "account"}).status_code == 200
    assert counted(recorder, "weekly_on_account") == 1
    # Already on: turning it on again from another place is not a second opt-in.
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "dashboard"}).status_code == 200
    assert counted(recorder, "weekly_on_dashboard") == 0
    assert authenticated_client.put("/api/for-you/email", json={"enabled": False, "source": "dashboard"}).status_code == 200
    assert counted(recorder, "weekly_off_dashboard") == 1
    # No source given (older pages): the switch still works, nothing is counted.
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True}).status_code == 200
    assert sum(count for (_d, kind, _k), count in recorder._pending.items() if kind == "email") == 2


def test_only_known_places_are_accepted(authenticated_client):
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "<script>"}).status_code == 422
    # The email link's own place can't be claimed by a page.
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "email_link"}).status_code == 422


def test_unsubscribing_from_an_email_link_is_counted(authenticated_client, db_session, recorder):
    authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "account"})
    token = db_session.query(models.EmailDigestSubscription).first().token
    assert authenticated_client.post(f"/email/unsubscribe?token={token}").status_code == 200
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    assert counted(recorder, "weekly_off_email_link") == 1


def test_counters_never_store_who_switched(recorder):
    digest.record_switch(True, "start")
    digest.record_switch(False, "account")
    digest.record_switch(True, "not-a-place")
    keys = sorted(key for (_d, kind, key) in recorder._pending if kind == "email")
    assert keys == ["weekly_off_account", "weekly_on_start"]


# ---------------------------------------------------------------- Site stats

def test_site_stats_shows_the_weekly_email_by_place(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    today = date.today()
    db_session.add_all([
        models.SiteTrafficDaily(day=today, kind="email", key="weekly_on_signup", count=3),
        models.SiteTrafficDaily(day=today - timedelta(days=2), kind="email", key="weekly_on_account", count=1),
        models.SiteTrafficDaily(day=today, kind="email", key="weekly_off_email_link", count=2),
        models.SiteTrafficDaily(day=today - timedelta(days=60), kind="email", key="weekly_on_signup", count=9),  # outside 30 days
    ])
    user = db_session.query(models.User).first()
    db_session.add(models.EmailDigestSubscription(user_id=user.id, token="statsdigest", last_sent_at=datetime.utcnow() - timedelta(days=2)))
    db_session.commit()
    response = authenticated_client.get("/api/site-stats/overview?days=30")
    assert response.status_code == 200
    email = response.json()["growth"]["weekly_email"]
    assert email["subscribers"] == 1 and email["emailed"] == 1 and email["emailed_7d"] == 1
    assert {row["place"]: row["count"] for row in email["opted_in_by_place"]}["the sign-up form"] == 3
    assert {row["place"]: row["count"] for row in email["opted_in_by_place"]}["Account settings"] == 1
    assert email["opted_out"] == 2
    assert {row["place"]: row["count"] for row in email["opted_out_by_place"]} == {
        "the library home": 0, "Account settings": 0, "a link in an email": 2}


# ---------------------------------------------------------------- the member's preview

def fake_coming_up(matches):
    def coming_up(db, user_id, today=None, pool=None, **kwargs):
        return {"matches": matches, "popular": [], "library_total": 3}
    return coming_up


MATCH = {"title": "Dune: Part Three", "label": "Movie", "date": "2026-12-18", "reason": "You rated Dune: Part Two 9/10",
         "url": "/release-radar", "category": "movies"}


def test_preview_needs_a_signed_in_member(client):
    assert client.get("/email/weekly/preview").status_code == 401


def test_preview_shows_this_weeks_email_without_sending(authenticated_client, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    sent = []
    monkeypatch.setattr(digest, "_send", lambda *args, **kwargs: sent.append(args))
    response = authenticated_client.get("/email/weekly/preview")
    assert response.status_code == 200
    assert "Dune: Part Three" in response.text
    assert "what your weekly email would look like" in response.text
    assert "Nothing has been sent" in response.text
    assert "unsubscribe?token=" not in response.text  # not subscribed: no token exists to leak
    assert response.headers["Cache-Control"] == "no-store"
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert sent == []


def test_preview_for_a_subscriber_says_it_is_the_next_one(authenticated_client, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "account"})
    response = authenticated_client.get("/email/weekly/preview")
    assert response.status_code == 200
    assert "This is your next weekly email" in response.text
    assert "Turn the weekly email off" in response.text


def test_preview_with_an_empty_library_explains_what_fills_it(authenticated_client, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([]))
    response = authenticated_client.get("/email/weekly/preview")
    assert response.status_code == 200
    assert "Nothing to show yet" in response.text
    assert "Save a few titles" in response.text


def test_preview_ignores_the_quiet_week_rule(db_session, monkeypatch):
    """A subscriber who got a round-up last week still sees a preview; only the sender skips them."""
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([]))
    user = models.User(username="quiet", email="quiet@example.com", hashed_password="x", is_verified=True, is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(models.EmailDigestSubscription(user_id=user.id, token="quietweek", last_sent_at=datetime.utcnow() - timedelta(days=7)))
    db_session.commit()
    now = datetime.utcnow()
    assert digest.compose(db_session, user, now, pool=[]) is digest.QUIET_WEEK
    assert digest.compose(db_session, user, now, pool=[], quiet_ok=False) is None  # nothing at all to say: None, never QUIET_WEEK


def test_dashboard_and_settings_link_to_the_preview(authenticated_client):
    page = authenticated_client.get("/").text
    assert page.count('href="/email/weekly/preview"') >= 3  # two dashboard prompts and the settings note
    assert 'id="weeklyEmailMeta"' in page
