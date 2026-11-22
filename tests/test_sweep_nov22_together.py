"""Nov 22 2026 sweep of Watch together (#314) and the public speed pass (#313)."""
import asyncio
import inspect
import re
from datetime import date, datetime, timedelta

from fastapi.routing import APIRoute

from app import models, page_hints, site_traffic, together
from tests.test_together import _plan_started, make_user, show, sign_in, sign_out, stale_session  # noqa: F401
from tests.test_together import pair  # noqa: F401


def _befriend(db, one, two):
    db.add(models.Friendship(user1_id=min(one.id, two.id), user2_id=max(one.id, two.id)))
    db.commit()


# ---------------------------------------------------------------- taking someone out

def test_someone_taken_out_cannot_walk_back_in_with_the_link(client, db_session, pair):
    owner, friend, _row, plan = pair
    sign_in(client, friend)
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 200
    member = together.member_of(db_session, plan.id, friend.id)
    sign_in(client, owner)
    assert client.delete(f"/api/together/{plan.id}/members/{member.id}").status_code == 200
    sign_in(client, friend)
    again = client.post(f"/api/together/join/{plan.token}", json={})
    assert again.status_code == 403
    assert "took you out" in again.json()["detail"]
    assert together.member_of(db_session, plan.id, friend.id) is None
    page = client.get(f"/together/join/{plan.token}")
    assert page.status_code == 200
    assert "took you out" in page.text and "data-together-join" not in page.text
    # Leaving on your own is different: the link still works afterwards.
    third = make_user(db_session, "lee")
    sign_in(client, third)
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 200
    assert client.post(f"/api/together/{plan.id}/leave").status_code == 200
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 200


def test_only_the_owner_can_ask_someone_taken_out_back(client, db_session, pair):
    owner, friend, _row, plan = pair
    helper = make_user(db_session, "lee")
    _befriend(db_session, owner, friend)
    _befriend(db_session, helper, friend)
    sign_in(client, helper)
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 200
    sign_in(client, friend)
    client.post(f"/api/together/join/{plan.token}", json={})
    member = together.member_of(db_session, plan.id, friend.id)
    sign_in(client, owner)
    client.delete(f"/api/together/{plan.id}/members/{member.id}")
    # Another member can't see them in their list of friends to ask, or ask them anyway.
    sign_in(client, helper)
    assert friend.id not in [f["id"] for f in client.get(f"/api/together/{plan.id}/friends").json()["friends"]]
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 0
    sign_in(client, friend)
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 403
    # The owner asking them in again opens the link back up, with a fresh invite.
    sign_in(client, owner)
    assert friend.id in [f["id"] for f in client.get(f"/api/together/{plan.id}/friends").json()["friends"]]
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 1
    sign_in(client, friend)
    assert client.post(f"/api/together/join/{plan.token}", json={}).status_code == 200


# ---------------------------------------------------------------- invites

def test_a_friend_is_not_asked_again_and_again(client, db_session, pair):
    owner, friend, _row, plan = pair
    _befriend(db_session, owner, friend)
    sign_in(client, owner)
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 1
    # Reading the bell used to let the next tap send another one, push included.
    db_session.query(models.Notification).filter_by(user_id=friend.id).update({"read_at": datetime.utcnow()})
    db_session.commit()
    for _ in range(3):
        assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 0
    assert db_session.query(models.Notification).filter_by(user_id=friend.id, type="together_invite").count() == 1
    # A few days on, one more is fine.
    db_session.query(models.Notification).filter_by(user_id=friend.id).update(
        {"created_at": datetime.utcnow() - timedelta(days=together.INVITE_AGAIN_DAYS + 1)})
    db_session.commit()
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 1


def test_a_full_plan_asks_nobody(client, db_session, pair, monkeypatch):
    owner, friend, _row, plan = pair
    _befriend(db_session, owner, friend)
    monkeypatch.setattr(together, "MEMBERS_MAX", 1)
    sign_in(client, owner)
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id]}).json()["asked"] == 0
    assert db_session.query(models.Notification).filter_by(user_id=friend.id, type="together_invite").count() == 0


# ---------------------------------------------------------------- an owner who left the site

def test_a_deactivated_owner_hands_the_plan_on(client, db_session, pair):
    owner, friend, _row, plan = pair
    sign_in(client, friend)
    client.post(f"/api/together/join/{plan.token}", json={})
    owner.is_active = False
    db_session.commit()
    detail = client.get(f"/api/together/{plan.id}").json()
    assert detail["you"]["owner"] is True
    db_session.refresh(plan)
    assert plan.owner_id == friend.id
    assert client.patch(f"/api/together/{plan.id}", json={"pace": 3}).status_code == 200


# ---------------------------------------------------------------- the weekly email

def test_one_reminder_a_week_however_many_plans(stale_session):
    db = stale_session
    owner, friend, first = _plan_started(db, days_ago=3)
    second_row = show(db, owner, title="Pluribus")
    second = together.create(db, owner, second_row, "tv-shows", total=10, pace=2,
                             starts_on=date.today() - timedelta(days=3), today=date.today() - timedelta(days=3))
    db.commit()
    db.add(models.TogetherMember(plan_id=second.id, user_id=friend.id, item_id=None, position=0,
                                 moved_at=datetime.utcnow(), remind_email=True))
    for plan in (first, second):
        together.member_of(db, plan.id, owner.id).position = 2
    db.commit()
    sent = []

    async def fake(to, subject, html, unsubscribe):
        sent.append(to)

    asyncio.run(together.run_once(lambda: db, now=datetime.utcnow(), sender=fake))
    assert sent == ["sam@example.test"]
    asyncio.run(together.run_once(lambda: db, now=datetime.utcnow() + timedelta(days=2), sender=fake))
    assert sent == ["sam@example.test"]


# ---------------------------------------------------------------- Site stats

def test_invite_links_are_masked_in_site_stats():
    assert site_traffic.clean_path("/together/join/QSHVIhDknB3CgnbKZSiC8Q") == "/together/join/(private link)"
    assert site_traffic.clean_path("/together") == "/together"


# ---------------------------------------------------------------- hover prefetch

def _routes(router):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _routes(route.original_router)
        elif hasattr(route, "routes"):
            yield from _routes(route)


def _pattern(path):
    return re.compile("^" + re.escape(path).replace(r"\*", ".*") + "$")


def test_prefetched_pages_never_count_an_open():
    """A prefetch is a hover, not a visit: no page the rules allow may record a funnel event on GET."""
    from app.main import app
    allowed = [_pattern(path) for path in page_hints.PREFETCH_PATHS]
    left_out = [_pattern(path) for path in page_hints.NO_PREFETCH_PATHS]
    checked, excluded = 0, []
    for route in _routes(app.router):
        if "GET" not in route.methods:
            continue
        sample = re.sub(r"\{[^}]+\}", "x1", route.path)
        if not any(p.match(sample) for p in allowed):
            continue
        if any(p.match(sample) for p in left_out):
            excluded.append(route.path)
            continue
        checked += 1
        source = inspect.getsource(inspect.unwrap(route.endpoint))
        assert "funnel.record(" not in source, route.path
    assert checked > 40
    assert {"/essentials/score/{counts}", "/essentials/{fmt}/score/{done}",
            "/holidays/advent-calendar/{year}/{day}"} <= set(excluded)
    rule = page_hints.SPECULATION_RULES["prefetch"][0]["where"]["and"]
    assert {"not": {"href_matches": list(page_hints.NO_PREFETCH_PATHS)}} in rule


def test_together_pages_stay_off_the_prefetch_list():
    for path in ("/together", "/together/join/x1", "/together/1"):
        assert not any(_pattern(p).match(path) for p in page_hints.PREFETCH_PATHS), path


# ---------------------------------------------------------------- sign-in return

def test_together_pages_send_guests_to_sign_in_with_a_way_back(client, db_session, pair):
    _owner, _friend, _row, plan = pair
    sign_out(client)
    join = client.get(f"/together/join/{plan.token}").text
    assert f"next=%2Ftogether%2Fjoin%2F{plan.token}" in join
    assert "next=%2Ftogether%2F" in client.get(f"/together/{plan.id}").text
    # The poster comes with the page, with the letter together.js shows if it no longer loads.
    assert 'data-letter="S"' in join
    auth_js = (__import__("pathlib").Path(__file__).parents[1] / "app" / "static" / "auth.js").read_text()
    assert "\\/together(?:\\/join\\/" in auth_js
