"""Sweep of Pick swap (PR #316): who drew you stays a secret before unwrap day, draw days that have
already passed, the reminder landing on top of the draw, and invite bells after a new link."""
from datetime import date, datetime, timedelta
from pathlib import Path

from app import auth, models, pick_swap

ROOT = Path(__file__).resolve().parents[1]


def make_user(db, name):
    user = models.User(username=name, email=f"{name}@example.test", hashed_password="unused", is_active=True,
                       is_verified=True)
    db.add(user)
    db.commit()
    return user


def sign_in(client, user):
    client.cookies.clear()
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username, "uid": user.id})


def befriend(db, a, b):
    db.add(models.Friendship(user1_id=min(a.id, b.id), user2_id=max(a.id, b.id)))
    db.commit()


class Clock:
    def __init__(self, monkeypatch, at):
        self.at = at
        monkeypatch.setattr(pick_swap, "_now", lambda: self.at)


def test_boxes_dont_say_who_wrapped_before_unwrap_day(client, db_session):
    people = [make_user(db_session, name) for name in ("dana", "sam", "lee", "kim")]
    dana = people[0]
    sign_in(client, dana)
    made = client.post("/api/swaps", json={"name": "Office swap",
                                           "reveal_on": (date.today() + timedelta(days=10)).isoformat()}).json()
    swap = db_session.get(models.PickSwap, made["id"])
    for user in people[1:]:
        sign_in(client, user)
        assert client.post(f"/api/swaps/join/{swap.token}", json={}).status_code == 200
    sign_in(client, dana)
    assert client.post(f"/api/swaps/{swap.id}/draw").status_code == 200
    gives = {row.user_id: row.gives_to for row in db_session.query(models.PickSwapMember).filter_by(swap_id=swap.id)}
    # Whoever drew dana wraps first, and so does dana.
    giver = db_session.get(models.User, next(uid for uid, to in gives.items() if to == dana.id))
    for user in (giver, dana):
        sign_in(client, user)
        response = client.put(f"/api/swaps/{swap.id}/gift", json={"kind": "tv", "title": f"Pick by {user.username}"})
        assert response.status_code == 200 and response.json()["saved"]
    sign_in(client, dana)
    data = client.get(f"/api/swaps/{swap.id}").json()
    assert data["wrapped"] == 2 and data["givers"] == 4
    flags = {person["username"]: person["wrapped"] for person in data["people"]}
    # dana sees her own box and nobody else's: the giver's name isn't next to a filled box.
    assert flags == {"dana": True, "sam": None, "lee": None, "kim": None}
    for user in people[1:]:
        sign_in(client, user)
        seen = {p["username"]: p["wrapped"] for p in client.get(f"/api/swaps/{swap.id}").json()["people"]}
        assert [name for name, flag in seen.items() if flag is not None] == [user.username]
    # Unwrap day: everything is out in the open.
    db_session.refresh(swap)
    pick_swap.advance(db_session, swap, swap.reveal_at + timedelta(minutes=1))
    sign_in(client, dana)
    after = client.get(f"/api/swaps/{swap.id}").json()
    assert after["state"] == "revealed"
    assert {p["username"]: p["wrapped"] for p in after["people"]}[giver.username] is True


def test_a_draw_day_whose_8am_has_passed_is_refused(client, db_session, monkeypatch):
    clock = Clock(monkeypatch, datetime(2026, 12, 20, 15, 0))
    dana = make_user(db_session, "dana")
    sign_in(client, dana)
    late = client.post("/api/swaps?tz=0", json={"name": "Family picks", "reveal_on": "2026-12-25",
                                                 "draw_on": "2026-12-20"})
    assert late.status_code == 422 and "8 a.m." in late.json()["detail"]
    assert db_session.query(models.PickSwap).count() == 0
    # Early in the morning today still works, and tomorrow always does.
    clock.at = datetime(2026, 12, 20, 6, 0)
    early = client.post("/api/swaps?tz=0", json={"name": "Family picks", "reveal_on": "2026-12-25",
                                                  "draw_on": "2026-12-20"})
    assert early.status_code == 201, early.text
    swap_id = early.json()["id"]
    # Nobody hears "it's draw day and you're alone" the moment they start.
    assert client.get(f"/api/swaps/{swap_id}?tz=0").json()["draw_label"] == "Sun, Dec 20"
    assert db_session.query(models.Notification).filter_by(type="swap_short").count() == 0
    clock.at = datetime(2026, 12, 20, 15, 0)
    moved = client.patch(f"/api/swaps/{swap_id}?tz=0", json={"draw_on": "2026-12-21"})
    assert moved.status_code == 200 and moved.json()["draw_on"] == "2026-12-21"
    back = client.patch(f"/api/swaps/{swap_id}?tz=0", json={"draw_on": "2026-12-20"})
    assert back.status_code == 422 and "8 a.m." in back.json()["detail"]


def test_after_a_short_draw_day_the_host_draws_by_hand(client, db_session, monkeypatch):
    clock = Clock(monkeypatch, datetime(2026, 12, 10, 12, 0))
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    sign_in(client, dana)
    made = client.post("/api/swaps?tz=0", json={"name": "Family picks", "reveal_on": "2026-12-20",
                                                 "draw_on": "2026-12-12"})
    assert made.status_code == 201, made.text
    swap_id = made.json()["id"]
    clock.at = datetime(2026, 12, 13, 12, 0)
    data = client.get(f"/api/swaps/{swap_id}?tz=0").json()
    assert data["state"] == "open" and data["draw_on"] is None and data["draw_label"] == ""
    assert db_session.query(models.Notification).filter_by(user_id=dana.id, type="swap_short").count() == 1
    # The spent draw day doesn't stand in the way of a new unwrap day.
    moved = client.patch(f"/api/swaps/{swap_id}?tz=0", json={"name": "Family picks", "reveal_on": "2026-12-22"})
    assert moved.status_code == 200, moved.text
    swap = db_session.get(models.PickSwap, swap_id)
    sign_in(client, sam)
    assert client.post(f"/api/swaps/join/{swap.token}", json={}).status_code == 200
    page = client.get(f"/swap/join/{swap.token}?tz=0")
    assert "draws names when everyone is in" in page.text
    # sam joining doesn't draw two names behind dana's back.
    assert client.get(f"/api/swaps/{swap_id}?tz=0").json()["state"] == "open"
    sign_in(client, dana)
    line = client.get("/api/swaps?tz=0").json()["swaps"][0]
    assert "you draw names" in line["line"]
    assert client.post(f"/api/swaps/{swap_id}/draw?tz=0").json()["state"] == "drawn"


def test_the_reminder_doesnt_land_on_top_of_the_draw(client, db_session):
    from tests.conftest import TestingSessionLocal
    import asyncio
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    now = datetime(2026, 12, 20, 10, 0)
    swap = pick_swap.create(db_session, dana, name="Late swap", note=None, kinds=[], draw_on=None,
                            reveal_on=date(2026, 12, 22), tz=0, wish=None, today=date(2026, 12, 20), now=now)
    db_session.commit()
    pick_swap.join(db_session, swap, sam, now=now)
    assert pick_swap.draw(db_session, swap, now)
    assert pick_swap.advance(db_session, swap, now)["reminded"] == 0
    assert db_session.query(models.Notification).filter_by(type="swap_reminder").count() == 0
    sent = []

    async def sender(to, subject, body, unsubscribe):
        sent.append(subject)

    import pytest
    patch = pytest.MonkeyPatch()
    patch.setattr(pick_swap, "allowance", lambda db, at: 10)
    try:
        asyncio.run(pick_swap.run_once(TestingSessionLocal, now=now + timedelta(minutes=15), sender=sender))
        assert len(sent) == 2 and all(subject.startswith("You're picking for") for subject in sent)
        # A day after the draw, with unwrap day still ahead, the people who haven't picked are nudged.
        db_session.refresh(swap)
        assert pick_swap.advance(db_session, swap, now + timedelta(hours=24, minutes=1))["reminded"] == 2
        asyncio.run(pick_swap.run_once(TestingSessionLocal, now=now + timedelta(hours=24, minutes=16), sender=sender))
        assert len(sent) == 4 and sum("Still time" in subject for subject in sent) == 2
    finally:
        patch.undo()


def test_friends_asked_in_keep_a_working_link_after_a_new_one(client, db_session):
    dana = make_user(db_session, "dana")
    ola = make_user(db_session, "ola")
    befriend(db_session, dana, ola)
    sign_in(client, dana)
    made = client.post("/api/swaps", json={"name": "Office swap", "friend_ids": [ola.id],
                                           "reveal_on": (date.today() + timedelta(days=10)).isoformat()}).json()
    assert made["asked"] == 1
    swap = db_session.get(models.PickSwap, made["id"])
    old = swap.token
    fresh = client.post(f"/api/swaps/{swap.id}/link").json()
    db_session.refresh(swap)
    assert swap.token != old and fresh["invite_path"] == f"/swap/join/{swap.token}"
    note = db_session.query(models.Notification).filter_by(user_id=ola.id, type="swap_invite").one()
    db_session.refresh(note)
    assert note.link == f"/swap/join/{swap.token}"
    sign_in(client, ola)
    assert client.get(f"/swap/join/{old}").status_code == 404
    assert client.post(f"/api/swaps/join/{swap.token}", json={}).status_code == 200


def test_guide_and_page_say_what_three_people_can_work_out(client):
    guide = client.get("/swap").text
    assert "With three, whoever you didn't draw must have drawn you" in guide
    assert "With three or more, nobody knows who drew them" not in guide
    script = (ROOT / "app" / "static" / "pick-swap.js").read_text(encoding="utf-8")
    boxes = script[script.index("function boxesRow"):script.index("function secretLine")]
    assert "username" not in boxes
    from app.routers import pick_swap as router
    assert router.JS_VERSION != "20261123-swap-1"
    assert f"/static/pick-swap.js?v={router.JS_VERSION}" in guide


def test_sweep_entries_stay_off_the_supporters_recent_work():
    from app import support_asks
    support_asks.recent_work.cache_clear()
    entries = support_asks.recent_work()
    assert entries and not any(anchor.startswith("security-") for anchor, _date, _title in entries)
