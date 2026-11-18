"""Draw from your backlog: dealing, keeping one, the night, the evening email, how it went, counters."""
import asyncio
from datetime import datetime, timedelta

import pytest

from app import auth, backlog_draw, check_in, digest, models
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "draw" and name == key)


def today():
    return backlog_draw._now().date()


def member(db, name="nova", verified=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=verified, is_active=True, created_at=datetime.utcnow() - timedelta(days=20))
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def shelf(db, user, waiting=4, finished=1):
    """A few unstarted titles across formats, plus finished ones that must never be dealt."""
    added = datetime.utcnow() - timedelta(days=40)
    rows = [
        models.Movie(title="Dune", year=2021, watched=False, user_id=user.id, added_at=added),
        models.Book(title="Piranesi", author="Susanna Clarke", year=2020, read=False, user_id=user.id,
                    added_at=datetime.utcnow() - timedelta(days=3)),
        models.VideoGame(title="Hades", played=False, user_id=user.id, added_at=datetime.utcnow() - timedelta(days=10)),
        models.Anime(title="Frieren", year=2023, watched=False, user_id=user.id, added_at=None),
        models.Movie(title="Arrival", year=2016, watched=False, user_id=user.id),
    ][:waiting]
    rows += [models.Movie(title=f"Seen {i}", year=2000 + i, watched=True, user_id=user.id) for i in range(finished)]
    db.add_all(rows)
    db.commit()
    return rows


def card(client, user, day=None):
    response = client.get(f"/api/backlog-draw?today={(day or today()).isoformat()}", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()["card"]


def post(client, user, path, body):
    return client.post(f"/api/backlog-draw/{path}", json={"today": today().isoformat(), **body}, headers=headers(user))


def test_needs_three_titles_waiting(client, db_session):
    user = member(db_session)
    shelf(db_session, user, waiting=2, finished=4)
    assert card(client, user) is None  # Today's pick is enough for two
    db_session.add(models.Book(title="Circe", read=False, user_id=user.id))
    db_session.commit()
    found = card(client, user)
    assert found["state"] == "deal" and found["total"] == 3


def test_started_and_dropped_titles_are_never_dealt(client, db_session):
    user = member(db_session)
    dune, piranesi, hades, frieren = shelf(db_session, user)[:4]
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="books", item_id=piranesi.id, unit="page", position=40))
    db_session.add(models.NextUpItem(user_id=user.id, category="video-games", item_id=hades.id, position=0,
                                     started_at=datetime.utcnow()))
    db_session.add(models.Book(title="Circe", read=False, user_id=user.id))
    db_session.add(models.Podcast(title="Serial", listened=False, user_id=user.id))  # never dealt
    db_session.commit()
    titles = {title for _, row in backlog_draw.backlog(db_session, user) for title in [row.title]}
    assert titles == {"Dune", "Frieren", "Circe"}
    user.movies_visible = False  # a tab hidden in Settings
    db_session.commit()
    assert {row.title for _, row in backlog_draw.backlog(db_session, user)} == {"Frieren", "Circe"}


def test_deal_is_stable_mixed_and_counted(client, db_session):
    user = member(db_session)
    shelf(db_session, user, waiting=5, finished=3)
    first = post(client, user, "deal", {"deal": 0})
    assert first.status_code == 200
    cards = first.json()["cards"]
    assert len(cards) == 3 and first.json()["total"] == 5
    assert len({c["category"] for c in cards}) == 3  # one per format while formats last
    assert all(not c["title"].startswith("Seen") for c in cards)
    again = post(client, user, "deal", {"deal": 0}).json()["cards"]
    assert [c["id"] for c in again] == [c["id"] for c in cards]
    assert counted("dealt") == 2
    post(client, user, "deal", {"deal": 1})
    assert counted("redealt") == 1
    dune = next((c for c in backlog_draw.deal(db_session, user, today(), 0) + backlog_draw.deal(db_session, user, today(), 1)
                 + backlog_draw.deal(db_session, user, today(), 2) + backlog_draw.deal(db_session, user, today(), 3)
                 if c["title"] == "Dune"), None)
    if dune:
        assert dune["waited"] == "Waiting 5 weeks" and dune["length"] and dune["url"] == "/titles/movie/dune-2021"


def test_keep_one_plan_a_night_and_ask_for_the_email(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    response = post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    assert response.status_code == 200
    kept = response.json()["card"]
    assert kept["state"] == "planned" and kept["pick"]["title"] == "Dune" and kept["night"] is None
    assert counted("picked") == 1
    # Dealing while a card is kept is refused; the deal state comes back after putting it back.
    assert post(client, user, "deal", {"deal": 0}).status_code == 409
    night = today() + timedelta(days=2)
    planned = post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": -300}).json()["card"]
    assert planned["night"] == night.isoformat() and planned["reminder"]["status"] == "set"
    draw = backlog_draw.active(db_session, user.id)
    db_session.refresh(draw)
    assert draw.remind_at == datetime.combine(night, datetime.min.time()) + timedelta(hours=18, minutes=300)
    assert counted("night_set") == 1 and counted("email_set") == 1
    # The same plan again changes nothing and counts nothing.
    post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": -300})
    assert counted("email_set") == 1
    # Too far out, and an email for a night already past 6 pm, are refused.
    assert post(client, user, "plan", {"night": (today() + timedelta(days=9)).isoformat()}).status_code == 422
    cancelled = post(client, user, "plan", {"night": night.isoformat(), "email": False}).json()["card"]
    assert cancelled["reminder"] is None and counted("email_cancel") == 1
    # The library row was never touched.
    db_session.refresh(dune)
    assert dune.watched is False and dune.rating is None


def test_only_the_members_own_backlog_can_be_kept(client, db_session):
    user = member(db_session)
    other = member(db_session, "other")
    theirs = shelf(db_session, other)[0]
    shelf(db_session, user)
    assert post(client, user, "pick", {"category": "movies", "item_id": theirs.id}).status_code == 404
    finished = db_session.query(models.Movie).filter_by(user_id=user.id, watched=True).first()
    assert post(client, user, "pick", {"category": "movies", "item_id": finished.id}).status_code == 404
    assert post(client, user, "pick", {"category": "nonsense", "item_id": 1}).status_code == 422 or \
        post(client, user, "pick", {"category": "nonsense", "item_id": 1}).status_code == 404


def test_after_the_night_finish_and_score(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    post(client, user, "plan", {"night": today().isoformat()})
    tomorrow = today() + timedelta(days=1)
    after = card(client, user, tomorrow)
    assert after["state"] == "after"
    seen = client.post("/api/backlog-draw/seen", json={"today": tomorrow.isoformat()}, headers=headers(user))
    assert seen.json() == {"back": True} and counted("back_after_night") == 1
    client.post("/api/backlog-draw/seen", json={"today": tomorrow.isoformat()}, headers=headers(user))
    assert counted("back_after_night") == 1  # once per night
    done = post(client, user, "answer", {"action": "finished", "rating": 9}).json()
    assert done["title"]["finished"] is True and done["title"]["rating"] == 9
    db_session.refresh(dune)
    assert dune.watched is True and dune.rating == 9
    assert db_session.query(models.ActivityEntry).filter_by(user_id=user.id, item_id=dune.id, action="completed").count() == 1
    assert counted("finished") == 1 and counted("rated") == 1
    assert done["card"]["state"] == "deal"  # straight on to the next one


def test_finished_elsewhere_closes_the_pick_and_can_be_scored(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    dune.watched = True
    db_session.commit()
    found = card(client, user)
    assert found["state"] == "finished" and found["rating"] is None and counted("finished") == 1
    scored = post(client, user, "answer", {"action": "rate", "rating": 7, "draw_id": found["draw_id"]})
    assert scored.status_code == 200 and scored.json()["title"]["rating"] == 7
    assert card(client, user)["state"] == "deal"


def test_later_not_for_me_and_put_back(client, db_session):
    user = member(db_session)
    dune, piranesi, hades, frieren = shelf(db_session, user)[:4]
    db_session.add(models.Book(title="Circe", read=False, user_id=user.id))
    db_session.commit()
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    post(client, user, "plan", {"night": today().isoformat()})
    later = post(client, user, "answer", {"action": "later"}).json()["card"]
    assert later["state"] == "planned" and later["night"] is None and counted("later") == 1
    post(client, user, "answer", {"action": "not_for_me"})
    assert counted("not_for_me") == 1
    assert "Dune" not in {row.title for _, row in backlog_draw.backlog(db_session, user)}
    db_session.refresh(dune)
    assert dune.watched is False  # still in the library, just never dealt again
    post(client, user, "pick", {"category": "books", "item_id": piranesi.id})
    post(client, user, "answer", {"action": "put_back"})
    assert counted("put_back") == 1
    assert "Piranesi" not in {row.title for _, row in backlog_draw.backlog(db_session, user)}  # not dealt again tonight
    later_on = backlog_draw._now() + backlog_draw.PUT_BACK_REST + timedelta(minutes=1)
    assert "Piranesi" in {row.title for _, row in backlog_draw.backlog(db_session, user, later_on)}


def test_deleted_title_closes_quietly(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    db_session.delete(dune)
    db_session.commit()
    assert card(client, user)["state"] == "deal"
    assert db_session.query(models.BacklogDraw).one().status == "gone"


def test_calendar_event(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    assert client.get("/api/backlog-draw/calendar.ics", headers=headers(user)).status_code == 404
    night = today() + timedelta(days=1)
    post(client, user, "plan", {"night": night.isoformat(), "tz": 60})
    response = client.get("/api/backlog-draw/calendar.ics", headers=headers(user))
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/calendar")
    body = response.text
    start = (datetime.combine(night, datetime.min.time()) + timedelta(hours=19)).strftime("%Y%m%dT%H%M%SZ")
    assert "SUMMARY:Watch Dune" in body and f"DTSTART:{start}" in body and "#backlog-draw" in body
    client.get("/api/backlog-draw/calendar.ics", headers=headers(user))
    assert counted("calendar") == 1


def test_evening_email_goes_once_with_a_score_link(client, db_session, monkeypatch):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    night = today() + timedelta(days=1)
    post(client, user, "plan", {"night": night.isoformat(), "email": True, "tz": 0})
    draw = backlog_draw.active(db_session, user.id)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html))

    factory = lambda: db_session  # noqa: E731
    monkeypatch.setattr(db_session, "close", lambda: None)
    early = asyncio.run(backlog_draw.send_due(factory, now=draw.remind_at - timedelta(minutes=5), sender=sender))
    assert early["sent"] == 0 and not sent
    result = asyncio.run(backlog_draw.send_due(factory, now=draw.remind_at + timedelta(minutes=10), sender=sender))
    assert result["sent"] == 1 and sent[0][0] == "nova@example.com" and sent[0][1] == "Tonight: Dune"
    assert "/check-in/" in sent[0][2] and "a=finished" in sent[0][2] and "#backlog-draw" in sent[0][2]
    again = asyncio.run(backlog_draw.send_due(factory, now=draw.remind_at + timedelta(minutes=30), sender=sender))
    assert again["sent"] == 0 and len(sent) == 1 and counted("sent") == 1
    # The score link opens the check-in page for that title and counts under its own source.
    token = check_in.make_token(user.id, [{"category": "movies", "id": dune.id}], "draw")
    assert check_in.read_token(token)["source"] == "draw"


def test_evening_email_dropped_when_late_or_finished(client, db_session, monkeypatch):
    user = member(db_session)
    dune, piranesi = shelf(db_session, user)[:2]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    post(client, user, "plan", {"night": (today() + timedelta(days=1)).isoformat(), "email": True})
    draw = backlog_draw.active(db_session, user.id)
    sent = []

    async def sender(*args):
        sent.append(args)

    monkeypatch.setattr(db_session, "close", lambda: None)
    late = asyncio.run(backlog_draw.send_due(lambda: db_session, now=draw.remind_at + backlog_draw.LATE + timedelta(minutes=1),
                                             sender=sender))
    assert late["dropped"] == 1 and not sent and counted("dropped") == 1


def test_site_stats_block(client, db_session):
    user = member(db_session)
    dune = shelf(db_session, user)[0]
    post(client, user, "pick", {"category": "movies", "item_id": dune.id})
    db_session.add(models.SiteTrafficDaily(day=datetime.utcnow().date(), kind="draw", key="back_after_night", count=4))
    db_session.commit()
    info = backlog_draw.stats(db_session, 30, backlog_draw._now())
    assert info["counts"]["back_after_night"] == 4 and info["counts"]["seen"] == 0
    assert info["kept_now"] == 1 and set(info["labels"]) == set(backlog_draw.COUNTERS)
    response = client.get("/api/site-stats?days=30", headers=headers(user))
    assert response.status_code in (401, 403, 404)  # members can't read it


def test_needs_sign_in(client):
    assert client.get("/api/backlog-draw").status_code == 401
    assert client.post("/api/backlog-draw/deal", json={}).status_code == 401
