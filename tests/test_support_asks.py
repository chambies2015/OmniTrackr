"""Support notes on the dashboard, the /supporters page additions, the weekly email line and their Site stats counters."""
import json
from datetime import date, datetime, timedelta

import pytest

from app import auth, digest, models, support_asks, supporters
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
TOKEN = "kofi-test-token"


@pytest.fixture(autouse=True)
def counters(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setenv("KOFI_VERIFICATION_TOKEN", TOKEN)
    monkeypatch.delenv("KOFI_MONTHLY_GOAL", raising=False)
    monkeypatch.delenv("KOFI_MONTHLY_COSTS", raising=False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "support" and name == key)


def member(db, name="maya", days_old=200, visit_days=40, titles=0):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=days_old),
                       visit_days=visit_days)
    db.add(user)
    db.flush()
    for i in range(titles):
        db.add(models.Movie(title=f"Film {i}", director="X", year=2001, watched=True, user_id=user.id))
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def reach_goal(db, user, days_ago=1, target=24):
    row = models.GoalAchievement(user_id=user.id, year=2026, category="movies", target=target,
                                 reached_at=datetime.utcnow() - timedelta(days=days_ago))
    db.add(row)
    db.commit()
    return row


def ask(client, user):
    response = client.get("/api/support-ask", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()


# ---------------------------------------------------------------- who sees a note, and when

def test_nobody_is_asked_in_their_first_three_weeks(client, db_session):
    user = member(db_session, days_old=10, titles=120)
    reach_goal(db_session, user)
    assert ask(client, user)["ask"] is None


def test_members_who_rarely_visit_are_not_asked(client, db_session):
    user = member(db_session, visit_days=2, titles=120)
    assert ask(client, user)["ask"] is None


def test_a_reached_goal_brings_a_note_and_looking_does_not_use_it_up(client, db_session):
    user = member(db_session, titles=30)
    reach_goal(db_session, user)
    note = ask(client, user)["ask"]
    assert note["moment"] == "goal" and note["key"].startswith("goal:")
    assert note["title"] == "24 movies in 2026. Nicely done."
    assert "free" in note["body"] and note["kofi_url"].startswith("https://ko-fi.com/")
    assert support_asks.get_row(db_session, user.id) is None  # nothing stored until it's on screen
    assert counted("ask_shown_goal") == 0


def test_seen_marks_every_reached_moment_so_notes_never_come_in_a_row(client, db_session):
    user = member(db_session, titles=260, visit_days=120)
    reach_goal(db_session, user)
    key = ask(client, user)["ask"]["key"]
    assert client.post("/api/support-ask/seen", headers=headers(user), json={"key": key}).json() == {"shown": True}
    assert client.post("/api/support-ask/seen", headers=headers(user), json={"key": key}).json() == {"shown": True}
    assert counted("ask_shown_goal") == 1
    row = support_asks.get_row(db_session, user.id)
    assert (row.titles_done, row.days_done, row.shown_count) == (250, 100, 1)
    # Still open for the week, with the same words.
    assert ask(client, user)["ask"]["key"] == key
    # After the week it's gone, and the cooldown stops a library or visits note from following it.
    row.shown_at = datetime.utcnow() - timedelta(days=8)
    db_session.commit()
    assert ask(client, user)["ask"] is None


def test_seen_with_a_stale_key_is_ignored(client, db_session):
    user = member(db_session, titles=120)
    assert client.post("/api/support-ask/seen", headers=headers(user), json={"key": "titles:5000"}).json() == {"shown": False}
    assert support_asks.get_row(db_session, user.id) is None


def test_not_now_hides_the_note_for_four_months(client, db_session):
    user = member(db_session, titles=120)
    key = ask(client, user)["ask"]["key"]
    assert key == "titles:100"
    client.post("/api/support-ask/seen", headers=headers(user), json={"key": key})
    result = client.post("/api/support-ask/answer", headers=headers(user), json={"key": key, "answer": "later"}).json()
    assert result == {"saved": True, "asks_off": False}
    assert ask(client, user)["ask"] is None
    row = support_asks.get_row(db_session, user.id)
    assert row.snoozed_until > datetime.utcnow() + timedelta(days=100)
    assert counted("ask_later_titles") == 1


def test_dont_ask_again_stops_notes_until_switched_back_on(client, db_session):
    user = member(db_session, titles=120)
    key = ask(client, user)["ask"]["key"]
    client.post("/api/support-ask/seen", headers=headers(user), json={"key": key})
    result = client.post("/api/support-ask/answer", headers=headers(user), json={"key": key, "answer": "stop"}).json()
    assert result["asks_off"] is True
    row = support_asks.get_row(db_session, user.id)
    row.shown_at = datetime.utcnow() - timedelta(days=400)
    db_session.commit()
    reach_goal(db_session, user)
    assert ask(client, user) == {"ask": None, "asks_off": True}
    assert support_asks.email_note_due(db_session, user, _due_week(user)) is False
    assert client.put("/api/support-ask/settings", headers=headers(user), json={"on": True}).json() == {"asks_off": False}
    assert ask(client, user)["ask"]["moment"] == "goal"
    assert counted("asks_turned_on") == 1


def test_settings_switch_can_turn_notes_off_before_any_note(client, db_session):
    user = member(db_session, titles=120)
    assert client.put("/api/support-ask/settings", headers=headers(user), json={"on": False}).json() == {"asks_off": True}
    assert ask(client, user) == {"ask": None, "asks_off": True}


def test_unknown_answers_are_refused(client, db_session):
    user = member(db_session, titles=120)
    response = client.post("/api/support-ask/answer", headers=headers(user), json={"key": "titles:100", "answer": "maybe"})
    assert response.status_code == 422


def test_active_supporters_never_see_a_note(client, db_session):
    user = member(db_session, titles=600)
    reach_goal(db_session, user)
    db_session.add(models.Supporter(user_id=user.id, since=datetime.utcnow() - timedelta(days=3),
                                    active_until=datetime.utcnow() + timedelta(days=20)))
    db_session.commit()
    assert ask(client, user)["ask"] is None


def test_perks_that_just_ended_get_their_own_note_once(client, db_session):
    user = member(db_session, titles=3)
    ended = datetime.utcnow() - timedelta(days=4)
    db_session.add(models.Supporter(user_id=user.id, since=ended - timedelta(days=30), active_until=ended))
    db_session.commit()
    note = ask(client, user)["ask"]
    assert note["moment"] == "ended" and note["title"].startswith("Your perks ended on ")
    assert "saved" in note["body"] and note["action"] == "Support again"
    client.post("/api/support-ask/seen", headers=headers(user), json={"key": note["key"]})
    row = support_asks.get_row(db_session, user.id)
    row.shown_at = datetime.utcnow() - timedelta(days=70)
    db_session.commit()
    assert ask(client, user)["ask"] is None


def test_an_anniversary_counts_once_and_only_near_the_date(client, db_session):
    user = member(db_session, days_old=370, titles=3, visit_days=10)
    note = ask(client, user)["ask"]
    assert note["moment"] == "years" and note["title"] == "One year on OmniTrackr"
    other = member(db_session, name="late", days_old=365 + 60, titles=3, visit_days=10)
    assert ask(client, other)["ask"] is None


def test_old_goals_do_not_bring_a_note(client, db_session):
    user = member(db_session, titles=3, visit_days=10)
    reach_goal(db_session, user, days_ago=40)
    assert ask(client, user)["ask"] is None


def test_the_note_needs_a_signed_in_member(client):
    assert client.get("/api/support-ask").status_code == 401


# ---------------------------------------------------------------- money words

def test_coffee_line_follows_the_monthly_costs(monkeypatch):
    assert support_asks.coffee_line() == "Every $3 coffee goes straight to the server bill."
    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Web server: 7; Database: 19; Email: 15; Domain: 2")
    assert support_asks.coffee_line() == "A $3 coffee keeps the site up for about 2 days."
    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Server: 2")
    assert support_asks.coffee_line() == "One $3 coffee covers a whole month of hosting."
    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Server: 900")
    assert support_asks.coffee_line() == "A $3 coffee keeps the site up for about 2 hours."


def test_a_nearly_empty_hosting_meter_is_left_off_the_note(db_session, monkeypatch):
    monkeypatch.setenv("KOFI_MONTHLY_GOAL", "40")
    assert support_asks.goal_line(db_session) is None
    db_session.add(models.KofiPayment(message_id="m1", kind="donation", amount="10.00", currency="USD",
                                      received_at=datetime.utcnow()))
    db_session.commit()
    assert support_asks.goal_line(db_session)["percent"] == 25


# ---------------------------------------------------------------- what led to support

def _kofi_payment(message_id, email):
    return {"verification_token": TOKEN, "message_id": message_id, "timestamp": "2026-11-16T12:00:00Z", "type": "Donation",
            "is_public": True, "from_name": "Maya", "message": "", "amount": "3.00", "url": "https://ko-fi.com/x",
            "email": email, "currency": "USD", "is_subscription_payment": False, "is_first_subscription_payment": False,
            "kofi_transaction_id": message_id, "tier_name": None}


def test_a_payment_after_a_ko_fi_press_on_a_note_is_counted_once(client, db_session):
    user = member(db_session, titles=120)
    key = ask(client, user)["ask"]["key"]
    client.post("/api/support-ask/seen", headers=headers(user), json={"key": key})
    client.post("/api/support-ask/answer", headers=headers(user), json={"key": key, "answer": "kofi"})
    assert counted("ask_kofi_titles") == 1
    response = client.post("/api/kofi/webhook", data={"data": json.dumps(_kofi_payment("pay-1", user.email))})
    assert response.status_code == 200
    assert supporters.is_active(supporters.get_supporter(db_session, user.id))
    assert counted("converted_titles") == 1
    client.post("/api/kofi/webhook", data={"data": json.dumps(_kofi_payment("pay-2", user.email))})
    assert counted("converted_titles") == 1


def test_supporters_page_press_by_a_member_is_remembered(client, db_session):
    user = member(db_session)
    response = client.post("/api/support/event", headers=headers(user), json={"event": "page_kofi", "place": "season_pass"})
    assert response.status_code == 204
    assert counted("page_kofi_season_pass") == 1
    assert support_asks.get_row(db_session, user.id).kofi_from == "page_season_pass"
    client.post("/api/kofi/webhook", data={"data": json.dumps(_kofi_payment("pay-3", user.email))})
    assert counted("converted_page_season_pass") == 1


def test_page_events_only_count_known_names_and_skip_bots(client):
    assert client.post("/api/support/event", headers=CHROME, json={"event": "page_seen", "place": "email"}).status_code == 204
    client.post("/api/support/event", headers=CHROME, json={"event": "page_seen", "place": "evil"})
    client.post("/api/support/event", headers=CHROME, json={"event": "other", "place": "email"})
    client.post("/api/support/event", headers={"User-Agent": "Googlebot/2.1"}, json={"event": "page_seen", "place": "ask"})
    assert counted("page_seen_email") == 1
    assert sum(amount for (_, kind, _), amount in RECORDER._pending.items() if kind == "support") == 1


# ---------------------------------------------------------------- /supporters

def test_supporters_page_leads_with_the_ways_to_support(client, monkeypatch):
    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Web server: 7; Database: 19; Email: 15; Domain: 2")
    html = client.get("/supporters").text
    assert "<!--SUPPORTERS_" not in html
    assert html.index('id="ways-heading"') < html.index('id="money-heading"') < html.index('id="perks-heading"')
    assert 'data-kofi-place="coffee"' in html and 'data-kofi-place="directors_cut"' in html and 'data-kofi-place="sticky"' in html
    assert "A $3 coffee keeps the site up for about 2 days." in html
    assert 'id="built-heading"' in html and 'href="/changelog#' in html and 'id="faq-heading"' in html


def test_recent_work_leaves_out_security_checks():
    entries = support_asks.recent_work()
    assert entries and all("ecurity" not in title for _, _, title in entries)


def test_member_summary_for_the_supporters_page(client, db_session):
    user = member(db_session, titles=12)
    data = client.get("/api/support/me", headers=headers(user)).json()
    assert data["titles"] == 12 and data["days"] == 40 and data["supporter"] is False and data["asks_off"] is False
    assert client.get("/api/support/me").status_code == 401


# ---------------------------------------------------------------- weekly email

def _due_week(user):
    """A Monday in a week when this member's support line is due."""
    day = datetime(2026, 11, 16)
    while support_asks.email_week(day) % support_asks.EMAIL_EVERY_WEEKS != (user.id + 3) % support_asks.EMAIL_EVERY_WEEKS:
        day += timedelta(days=7)
    return day


def test_weekly_email_line_comes_about_every_six_weeks(db_session):
    user = member(db_session)
    due = _due_week(user)
    assert support_asks.email_note_due(db_session, user, due) is True
    assert all(not support_asks.email_note_due(db_session, user, due + timedelta(days=7 * n)) for n in range(1, 6))
    newcomer = member(db_session, name="new", days_old=5)
    assert support_asks.email_note_due(db_session, newcomer, _due_week(newcomer)) is False


def test_weekly_email_line_skips_supporters(db_session):
    user = member(db_session)
    due = _due_week(user)
    db_session.add(models.Supporter(user_id=user.id, since=due - timedelta(days=2), active_until=due + timedelta(days=9)))
    db_session.commit()
    assert support_asks.email_note_due(db_session, user, due) is False


def test_weekly_email_shows_the_line_and_never_sends_for_it_alone():
    report = {"matches": [], "popular": [{"title": "Dune", "label": "Movie", "date": "2026-12-01", "url": "/x"}]}
    subject, html, text = digest.build_digest("maya", report, "https://x/unsub", support=support_asks.email_note())
    assert "/supporters?from=email" in html and "/supporters?from=email" in text
    assert digest.build_digest("maya", {"matches": [], "popular": []}, "u", support=support_asks.email_note()) is None


# ---------------------------------------------------------------- Site stats

def test_site_stats_summary_groups_the_counters(db_session):
    today = date.today()
    for key, amount in (("ask_shown_goal", 4), ("ask_kofi_goal", 2), ("ask_stop_titles", 1), ("page_seen_email", 3),
                        ("page_kofi_hero", 5), ("converted_goal", 1)):
        db_session.add(models.SiteTrafficDaily(day=today, kind="support", key=key, count=amount))
    db_session.commit()
    data = support_asks.stats(db_session, 30, datetime.utcnow())
    goal = next(row for row in data["asks"] if row["moment"] == "Yearly goal reached")
    assert (goal["shown"], goal["kofi"]) == (4, 2)
    assert data["shown"] == 4 and data["stopped"] == 1 and data["converted_total"] == 1
    assert {"place": "Weekly email", "count": 3} in data["page_seen"]
    assert {"place": "Top of the page", "count": 5} in data["page_kofi"]
