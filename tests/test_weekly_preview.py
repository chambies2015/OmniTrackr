"""The member's own weekly email shown in place, the one-off copy, and the one-tap yes (Nov 18 2026)."""
import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import digest, models, weekly_preview
from app.site_traffic import RECORDER

ROOT = Path(__file__).resolve().parents[1]

MATCH = {"title": "Dune: Part Three", "label": "Movie", "date": "2026-12-18", "reason": "Because you track Dune",
         "url": "/release-radar/movies#item-dune3", "category": "movies", "image": "https://image.example/dune.jpg"}
POPULAR = {"title": "Big Winter Game", "label": "Game", "date": "2026-11-28", "reason": "",
           "url": "/release-radar/games#item-bwg", "category": "video-games", "image": None}
SHOW = {"title": "Severance", "category": "tv-shows", "url": "https://omnitrackr.xyz/tv/severance-2022",
        "episodes": [{"code": "S2E6", "date": "2026-11-20", "name": "Attila"}]}


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(recorder, kind, key):
    return sum(count for (_day, k, name), count in recorder._pending.items() if k == kind and name == key)


def fake_coming_up(matches, popular=()):
    def coming_up(db, user_id, today=None, pool=None, **kwargs):
        return {"matches": list(matches), "popular": list(popular), "library_total": 3}
    return coming_up


@pytest.fixture
def quiet(monkeypatch):
    """No outside calls and nothing optional: each test adds only what it is about."""
    monkeypatch.setattr("app.for_you.radar_pool", lambda today=None, client=None: [])
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([]))
    monkeypatch.setattr(digest, "episodes_this_week", lambda db, user, today: [])
    monkeypatch.setattr(digest, "friend_activity", lambda db, user_id, now: [])
    monkeypatch.setattr(digest, "memories_line", lambda db, user, today: [])
    monkeypatch.setattr(digest, "following_line", lambda db, user, now: [])


@pytest.fixture
def mail_on(monkeypatch):
    monkeypatch.setattr(digest, "mail_configured", lambda: True)


def member(db_session):
    return db_session.query(models.User).filter_by(username="testuser").first()


# ---------------------------------------------------------------- what the preview lists

def test_preview_needs_a_signed_in_member(client):
    assert client.get("/api/weekly-email/preview").status_code == 401
    assert client.post("/api/weekly-email/copy").status_code == 401


def test_preview_lists_the_members_own_lines(authenticated_client, quiet, mail_on, monkeypatch, recorder):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH], [POPULAR]))
    monkeypatch.setattr(digest, "episodes_this_week", lambda db, user, today: [SHOW])
    response = authenticated_client.get("/api/weekly-email/preview?place=settings")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    data = response.json()
    assert data["personal"] is True and data["subscribed"] is False and data["available"] is True
    assert data["subject"].startswith("Coming up for you: Dune: Part Three")
    first, second = data["items"][:2]
    assert first["heading"] == "From your library" and first["title"] == "Dune: Part Three"
    assert first["detail"] == "Movie · Fri Dec 18" and first["note"] == "Because you track Dune"
    assert first["image"] == "https://image.example/dune.jpg"
    assert second["heading"] == "New episodes this week" and second["detail"].startswith("S2E6")
    # Absolute links from the email become paths on this site.
    assert second["url"] == "/tv/severance-2022"
    # Popular titles only fill in when nothing personal is coming.
    assert all(item["section"] != "popular" for item in data["items"])
    assert data["copy"] == {"can": True, "reason": None}
    assert counted(recorder, "weeklymail", "preview_settings") == 1


def test_preview_without_personal_news_shows_the_round_up(authenticated_client, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([], [POPULAR]))
    data = authenticated_client.get("/api/weekly-email/preview").json()
    assert data["personal"] is False
    assert [item["section"] for item in data["items"]] == ["popular"]
    assert data["subject"].startswith("This month on Release Radar")


def test_preview_with_nothing_at_all(authenticated_client, quiet, mail_on):
    data = authenticated_client.get("/api/weekly-email/preview").json()
    assert data["items"] == [] and data["subject"] is None and data["personal"] is False


def test_friends_and_extras_are_named(authenticated_client, quiet, mail_on, monkeypatch):
    friends = [{"username": "maria", "count": 3, "titles": [
        {"title": "Arcane", "label": "TV show", "done": "watched", "rating": 9.0, "path": "/tv/arcane-2021"}]}]
    monkeypatch.setattr(digest, "friend_activity", lambda db, user_id, now: friends)
    monkeypatch.setattr(digest, "next_up_line", lambda db, user_id: {"title": "Dune", "label": "Book", "waiting": 2})
    data = authenticated_client.get("/api/weekly-email/preview").json()
    lines = {item["section"]: item for item in data["items"]}
    assert lines["friends"]["title"] == "maria added Arcane (TV show, watched, 9/10) and 2 more"
    assert lines["friends"]["url"] == "/tv/arcane-2021"
    assert lines["next_up"]["title"] == "Dune" and lines["next_up"]["note"] == "2 more behind it"
    assert data["personal"] is True


def test_preview_caps_the_lines_and_counts_the_rest(authenticated_client, quiet, mail_on, monkeypatch):
    matches = [{**MATCH, "title": f"Film {n}", "url": f"/release-radar/movies#item-f{n}"} for n in range(8)]
    monkeypatch.setattr(digest, "coming_up", fake_coming_up(matches))
    data = authenticated_client.get("/api/weekly-email/preview").json()
    assert len(data["items"]) == weekly_preview.ITEMS_SHOWN
    assert data["more"] == 8 - weekly_preview.ITEMS_SHOWN


def test_unsafe_links_are_dropped(db_session, quiet, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([{**MATCH, "url": "https://elsewhere.example/x"}]))
    user = models.User(username="links", email="links@example.com", hashed_password="x", is_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()
    found = weekly_preview.content(db_session, user, datetime.utcnow(), fresh=True)
    assert found["items"][0]["url"] == ""


def test_preview_for_a_subscriber_offers_no_copy(authenticated_client, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "preview"})
    data = authenticated_client.get("/api/weekly-email/preview").json()
    assert data["subscribed"] is True
    assert data["copy"]["can"] is False and data["copy"]["reason"] == "subscribed"


def test_preview_place_is_checked(authenticated_client, quiet):
    assert authenticated_client.get("/api/weekly-email/preview?place=<b>").status_code == 422


def test_the_preview_never_sends_or_subscribes(authenticated_client, db_session, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    sent = []
    monkeypatch.setattr(weekly_preview, "_send", lambda *args: sent.append(args))
    monkeypatch.setattr(digest, "_send", lambda *args: sent.append(args))
    for place in ("settings", "for_you", "home_card"):
        assert authenticated_client.get(f"/api/weekly-email/preview?place={place}").status_code == 200
    assert sent == []
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    assert db_session.query(models.EmailCampaignSend).count() == 0


# ---------------------------------------------------------------- the copy

def test_a_copy_is_sent_once_and_never_subscribes(authenticated_client, db_session, quiet, mail_on, monkeypatch, recorder):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    sent = []

    async def fake_send(to, subject, html):
        sent.append((to, subject, html))
    monkeypatch.setattr(weekly_preview, "_send", fake_send)
    response = authenticated_client.post("/api/weekly-email/copy")
    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True
    assert len(sent) == 1
    to, subject, html = sent[0]
    assert to == "test@example.com" and subject.startswith("Coming up for you")
    assert "This is the copy you asked for" in html and "Yes, every week" in html
    assert "/email/weekly/subscribe?token=" in html and "from=copy" in html
    assert "turned on the weekly email" not in html  # it isn't on
    assert db_session.query(models.EmailDigestSubscription).count() == 0
    row = db_session.query(models.EmailCampaignSend).one()
    assert row.campaign_key.startswith(weekly_preview.COPY_PREFIX) and row.status == "sent"
    assert counted(recorder, "weeklymail", "copy_sent") == 1
    # A second press is refused, with a reason the page can show.
    again = authenticated_client.post("/api/weekly-email/copy")
    assert again.status_code == 409 and again.json()["detail"]["reason"] == "recent"
    assert len(sent) == 1
    state = authenticated_client.get("/api/weekly-email/preview").json()["copy"]
    assert state["can"] is False and state["reason"] == "recent" and state["again_at"]


def test_a_copy_can_be_asked_for_again_after_two_weeks(db_session, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    user = models.User(username="again", email="again@example.com", hashed_password="x", is_verified=True, is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(models.EmailCampaignSend(campaign_key="weekly-copy-2026-11-01", user_id=user.id, status="sent",
                                            sent_at=datetime.utcnow() - timedelta(days=15)))
    db_session.commit()
    assert weekly_preview.copy_state(db_session, user)["can"] is True
    sent = []

    async def fake_send(to, subject, html):
        sent.append(to)
    result = asyncio.run(weekly_preview.send_copy(db_session, user, sender=fake_send))
    assert result["sent"] and sent == ["again@example.com"]


def test_copy_refusals(db_session, quiet, monkeypatch):
    user = models.User(username="nomail", email="nomail@example.com", hashed_password="x", is_verified=False, is_active=True)
    db_session.add(user)
    db_session.commit()
    monkeypatch.setattr(digest, "mail_configured", lambda: False)
    assert weekly_preview.copy_state(db_session, user)["reason"] == "off"
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    assert weekly_preview.copy_state(db_session, user)["reason"] == "verify"
    user.is_verified = True
    db_session.commit()
    with pytest.raises(weekly_preview.CopyRefused) as refused:
        asyncio.run(weekly_preview.send_copy(db_session, user, sender=lambda *a: None))
    assert refused.value.reason == "empty"  # nothing at all to put in it
    assert db_session.query(models.EmailCampaignSend).count() == 0


def test_copy_respects_the_shared_daily_budget(db_session, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    monkeypatch.setenv("SHARED_DAILY_CAP", "1")
    other = models.User(username="other", email="other@example.com", hashed_password="x", is_verified=True, is_active=True)
    user = models.User(username="budget", email="budget@example.com", hashed_password="x", is_verified=True, is_active=True)
    db_session.add_all([other, user])
    db_session.flush()
    db_session.add(models.EmailCampaignSend(campaign_key="week-one-2026-11-18", user_id=other.id, status="sent",
                                            sent_at=datetime.utcnow()))
    db_session.commit()
    with pytest.raises(weekly_preview.CopyRefused) as refused:
        asyncio.run(weekly_preview.send_copy(db_session, user, sender=lambda *a: None))
    assert refused.value.reason == "busy"
    assert db_session.query(models.EmailCampaignSend).filter_by(user_id=user.id).count() == 0


def test_a_failed_copy_is_marked_and_can_be_retried(db_session, quiet, mail_on, monkeypatch, recorder):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    user = models.User(username="bounce", email="bounce@example.com", hashed_password="x", is_verified=True, is_active=True)
    db_session.add(user)
    db_session.commit()

    async def broken(to, subject, html):
        raise RuntimeError("smtp down")
    with pytest.raises(weekly_preview.CopyRefused) as refused:
        asyncio.run(weekly_preview.send_copy(db_session, user, sender=broken))
    assert refused.value.reason == "failed"
    assert db_session.query(models.EmailCampaignSend).count() == 0  # nothing arrived, so it doesn't block a retry
    assert weekly_preview.copy_state(db_session, user)["can"] is True
    assert counted(recorder, "weeklymail", "copy_failed") == 1


# ---------------------------------------------------------------- yes from the copy or the preview page

def test_yes_in_the_copy_counts_as_its_own_place(authenticated_client, db_session, recorder):
    user = member(db_session)
    link = weekly_preview.copy_link(user.id)
    path = link[link.index("/email/weekly/subscribe"):]
    page = authenticated_client.get(path)
    assert page.status_code == 200 and "from=copy" in page.text  # the confirm button keeps the place
    assert db_session.query(models.EmailDigestSubscription).count() == 0  # opening the link changes nothing
    assert authenticated_client.post(path).status_code == 200
    assert db_session.query(models.EmailDigestSubscription).filter_by(user_id=user.id).count() == 1
    assert counted(recorder, "email", "weekly_on_copy_email") == 1


def test_unknown_link_places_count_as_an_email_link(authenticated_client, db_session, recorder):
    user = member(db_session)
    authenticated_client.post(f"/email/weekly/subscribe?token={digest.subscribe_link_token(user.id)}&from=zzz")
    assert counted(recorder, "email", "weekly_on_email_link") == 1


def test_preview_page_has_a_yes_button(authenticated_client, quiet, mail_on, monkeypatch, recorder):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    page = authenticated_client.get("/email/weekly/preview").text
    assert "Yes, email me this every week" in page
    assert 'method="post"' in page and "from=preview" in page
    assert counted(recorder, "weeklymail", "preview_page") == 1


def test_preview_page_has_no_yes_button_once_subscribed(authenticated_client, quiet, mail_on, monkeypatch):
    monkeypatch.setattr(digest, "coming_up", fake_coming_up([MATCH]))
    authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "account"})
    assert "Yes, email me this every week" not in authenticated_client.get("/email/weekly/preview").text


def test_the_preview_opt_in_counts_as_preview(authenticated_client, recorder):
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "preview"}).status_code == 200
    assert counted(recorder, "email", "weekly_on_preview") == 1
    # The copy email's place can only come from its signed link.
    assert authenticated_client.put("/api/for-you/email", json={"enabled": True, "source": "copy_email"}).status_code == 422


# ---------------------------------------------------------------- the real email is unchanged

def test_the_regular_email_keeps_its_footer(db_session, quiet):
    built = digest.build_digest("sam", {"matches": [MATCH], "popular": []}, "https://x.example/unsub")
    assert "You get this because you turned on the weekly email" in built[1]
    assert "This is the copy you asked for" not in built[1]


# ---------------------------------------------------------------- Site stats and the page

def test_site_stats_lists_previews_and_copies(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    today = date.today()
    db_session.add_all([
        models.SiteTrafficDaily(day=today, kind="weeklymail", key="preview_settings", count=4),
        models.SiteTrafficDaily(day=today, kind="weeklymail", key="preview_home_card", count=2),
        models.SiteTrafficDaily(day=today, kind="weeklymail", key="copy_sent", count=1),
    ])
    db_session.commit()
    email = authenticated_client.get("/api/site-stats/overview?days=30").json()["growth"]["weekly_email"]
    previews = {row["place"]: row["count"] for row in email["preview"]["previews"]}
    assert previews["Settings"] == 4 and previews["the home screen card"] == 2
    assert email["preview"]["copies_sent"] == 1
    assert {row["place"]: row["count"] for row in email["opted_in_by_place"]}["the copy they sent themselves"] == 0


def test_dashboard_has_the_preview_hosts(authenticated_client):
    page = authenticated_client.get("/").text
    assert page.count('data-weekly-preview="for_you"') == 2
    assert 'data-weekly-preview="settings"' in page
    assert 'id="stayPostedPeek"' in page and 'data-weekly-preview="home_card"' in page
    from app import dashboard_assets
    assert "/static/weekly-preview.js?v=" in page
    assert any(href.startswith("/static/weekly-preview.css?v=") for href in dashboard_assets.page_stylesheets(page))


def test_preview_script_never_writes_html():
    script = (ROOT / "app" / "static" / "weekly-preview.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    assert "source: 'preview'" in script and "/api/weekly-email/copy" in script


def test_the_monthly_challenge_is_not_called_the_new_year_challenge(authenticated_client, quiet, mail_on, monkeypatch):
    line = {"joined": False, "name": "Close the year kindly", "tagline": "Finish a few things.", "month_name": "December",
            "days_left": 20, "total_steps": 3}
    monkeypatch.setattr(digest, "challenge_line", lambda db, user_id, today: line)
    also = authenticated_client.get("/api/weekly-email/preview").json()["also"]
    assert "this month's challenge" in also and not any("New Year" in entry for entry in also)
