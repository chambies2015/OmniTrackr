"""Sweep of the Nov 18 2026 evening merges: the installed app (#250: install offers, /app, the offline
page, /api/app/event and /api/app/status) and "Draw from your backlog" (#251: the home card, its
one evening email and the calendar event)."""
import asyncio
from datetime import timedelta

from sqlalchemy import event

from app import backlog_draw, models
from app.routers import backlog_draw as backlog_draw_router
from app.routers import pwa as pwa_router
from tests.conftest import engine
from tests.test_backlog_draw import card, headers, member, post, setup, shelf, today  # noqa: F401  (setup: autouse fixture)
from tests.test_security_sweep_nov06 import _limited


def _count_sql(run):
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        result = run()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return result, statements


def _sender(sent):
    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject))
    return sender


def _run(db, now, sent):
    return asyncio.run(backlog_draw.send_due(lambda: db, now=now, sender=_sender(sent)))


# ---------------------------------------------------------------- rate limits

def test_app_status_is_rate_limited():
    """pwa.js asks once a day per browser; it reads the database for signed-in members and had no limit."""
    assert _limited(pwa_router.router, "/api/app/status", "GET")
    assert _limited(pwa_router.router, "/api/app/event", "POST")
    assert _limited(pwa_router.router, "/share", "GET")


def test_every_backlog_draw_route_is_rate_limited():
    for route in backlog_draw_router.router.routes:
        for method in route.methods:
            assert _limited(backlog_draw_router.router, route.path, method), (method, route.path)


def test_app_status_answers_guests_and_members(client, db_session):
    assert client.get("/api/app/status").json() == {"platforms": []}
    user = member(db_session, "appy")
    client.post("/api/app/event", json={"event": "opened", "platform": "ios"}, headers=headers(user))
    found = client.get("/api/app/status", headers=headers(user))
    assert found.json() == {"platforms": ["ios"]} and found.headers["Cache-Control"] == "private, no-store"


# ---------------------------------------------------------------- the evening email

def test_another_night_after_an_email_gets_its_own_email(client, db_session, monkeypatch):
    """The claim was keyed by the kept card, so after "Didn't get to it" and a new night the second email
    hit the unique claim, was retried every 15 minutes for three hours and never went out."""
    monkeypatch.setattr(db_session, "close", lambda: None)
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    first_night = today() + timedelta(days=1)
    post(client, user, "plan", {"night": first_night.isoformat(), "email": True, "tz": 0})
    draw = backlog_draw.active(db_session, user.id)
    sent = []
    assert _run(db_session, draw.remind_at + timedelta(minutes=5), sent)["sent"] == 1
    # Didn't get to it: pick another night on the same kept card and ask again.
    assert post(client, user, "answer", {"action": "later"}).status_code == 200
    second_night = today() + timedelta(days=3)
    planned = post(client, user, "plan", {"night": second_night.isoformat(), "email": True, "tz": 0})
    assert planned.status_code == 200 and planned.json()["card"]["reminder"]["status"] == "set"
    db_session.refresh(draw)
    result = _run(db_session, draw.remind_at + timedelta(minutes=5), sent)
    assert result["sent"] == 1 and len(sent) == 2
    db_session.refresh(draw)
    assert draw.reminder_status == "sent"
    keys = {row.campaign_key for row in db_session.query(models.EmailCampaignSend).filter_by(user_id=user.id)}
    assert keys == {backlog_draw.send_key(first_night), backlog_draw.send_key(second_night)}


def test_one_evening_email_per_member_per_night(client, db_session, monkeypatch):
    """Keep a card, get the email, keep another card for the same night and ask again: refused, so one
    member can't spend the evening email's daily limit (30 for everyone) on themselves."""
    monkeypatch.setattr(db_session, "close", lambda: None)
    user = member(db_session)
    dune, piranesi = shelf(db_session, user)[:2]
    night = today() + timedelta(days=1)
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": 0})
    draw = backlog_draw.active(db_session, user.id)
    sent = []
    _run(db_session, draw.remind_at + timedelta(minutes=1), sent)
    assert len(sent) == 1
    post(client, user, "pick", {"category": "books", "item_id": piranesi.id})
    again = post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": -60})
    assert again.status_code == 422 and "already emailed" in again.json()["detail"]
    # The night itself (and the calendar) still work without the email.
    plain = post(client, user, "plan", {"night": night.isoformat(), "email": False, "tz": 0})
    assert plain.status_code == 200 and plain.json()["card"]["night"] == night.isoformat()


def test_a_claim_clash_is_dropped_once_not_retried_all_evening(client, db_session, monkeypatch):
    monkeypatch.setattr(db_session, "close", lambda: None)
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    night = today() + timedelta(days=1)
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": 0})
    draw = backlog_draw.active(db_session, user.id)
    # Claimed already (an email for that night went out from an earlier card).
    db_session.add(models.EmailCampaignSend(campaign_key=backlog_draw.send_key(night), user_id=user.id,
                                            status="sent", sent_at=draw.remind_at - timedelta(days=2)))
    db_session.commit()
    sent = []
    result = _run(db_session, draw.remind_at + timedelta(minutes=5), sent)
    assert not sent and result["dropped"] == 1
    db_session.refresh(draw)
    assert draw.reminder_status == "dropped"
    assert _run(db_session, draw.remind_at + timedelta(minutes=20), sent) == {"sent": 0, "failed": 0, "dropped": 0,
                                                                               "limited": False}


def test_each_run_sends_at_most_its_share(client, db_session, monkeypatch):
    """PER_RUN_LIMIT was folded into the allowance, which counts this run's sends too, so it never bound a run."""
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(backlog_draw, "PER_RUN_LIMIT", 1)
    night = today() + timedelta(days=1)
    remind = None
    for name in ("ada", "bix"):
        user = member(db_session, name)
        dune = shelf(db_session, user)[0]
        post(client, user, "pick", {"category": "movies", "item_id": dune.id})
        post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": 0})
        remind = backlog_draw.active(db_session, user.id).remind_at
    sent = []
    first = _run(db_session, remind + timedelta(minutes=5), sent)
    assert first["sent"] == 1 and first["limited"] is True
    second = _run(db_session, remind + timedelta(minutes=20), sent)
    assert second["sent"] == 1 and len(sent) == 2


# ---------------------------------------------------------------- speed

def test_hidden_card_skips_counting_the_backlog(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    response, statements = _count_sql(lambda: client.get(f"/api/backlog-draw?today={today()}&hidden=1",
                                                         headers=headers(user)))
    assert response.json() == {"card": None}
    assert len(statements) <= 3, statements  # sign-in and the kept-card check, no backlog reads
    assert card(client, user)["state"] == "deal"  # unhidden browsers still get the deal
    # A kept card still shows where the deal card is hidden.
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    kept = client.get(f"/api/backlog-draw?today={today()}&hidden=1", headers=headers(user)).json()["card"]
    assert kept["state"] == "planned" and kept["pick"]["title"] == "Dune"


def test_dealing_reads_the_backlog_once(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    response, statements = _count_sql(lambda: post(client, user, "deal", {"deal": 0}))
    assert response.status_code == 200 and len(response.json()["cards"]) == 3 and response.json()["total"] == 4
    assert len(statements) <= 20, len(statements)  # was 29: the backlog was counted a second time
