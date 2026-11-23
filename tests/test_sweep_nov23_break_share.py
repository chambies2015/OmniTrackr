"""Nov 23 2026 sweep of break plan share links (PR #327): the sign-up link on a shared plan, links the
planner no longer shows, and the share page's extra work."""
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import event

from app import break_plan, break_share, models
from tests.test_break_share import CHROME, THANKSGIVING, clock, make_user, shared, sign_in, sign_out  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def _at(monkeypatch, day: str) -> None:
    moment = datetime.fromisoformat(f"{day}T12:00:00")
    monkeypatch.setattr(break_plan, "_now", lambda: moment)


def _queries(db, call):
    engine = db.get_bind()
    seen = []

    def hook(_conn, _cursor, statement, *_args):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        result = call()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return result, seen


# ---------------------------------------------------------------- signing up from a shared plan

def test_signing_up_from_a_shared_plan_never_makes_you_the_owners_friend(client, db_session, shared):
    owner, _rows, _plan, path = shared
    # nova made a friend invite link at some point. A break plan goes on stories, so a stranger who
    # signs up from it must not become nova's friend (friends see scores and reviews) or learn the name.
    db_session.add(models.FriendInvite(user_id=owner.id, token="novasfriendinvite12345"))
    db_session.commit()
    page = client.get(path, headers=CHROME).text
    assert "novasfriendinvite12345" not in page
    assert "invite=" not in page
    back = path.replace("/", "%2F")
    assert f'href="/?next={back}#signup"' in page


# ---------------------------------------------------------------- links the planner no longer shows

def test_a_link_still_working_after_the_plan_leaves_the_planner_can_be_turned_off(client, db_session, shared,
                                                                                 monkeypatch):
    owner, _rows, plan, path = shared
    _at(monkeypatch, "2026-12-05")  # the break ended Nov 29 and the planner shows it until Dec 3
    sign_in(client, owner)
    state = client.get("/api/break?today=2026-12-05").json()
    assert state["plan"] is None
    links = state["older_links"]
    assert [link["id"] for link in links] == [plan["id"]]
    assert links[0]["path"] == path and links[0]["share"].endswith(path)
    assert links[0]["until"] == "2026-12-29" and links[0]["name"] == "Thanksgiving weekend"
    sign_out(client)
    assert client.get(path, headers=CHROME).status_code == 200  # the link really does still work
    sign_in(client, owner)
    after = client.delete(f"/api/break/{plan['id']}/share?today=2026-12-05")
    assert after.status_code == 200 and after.json()["older_links"] == []
    sign_out(client)
    assert client.get(path, headers=CHROME).status_code == 404


def test_planning_the_next_break_keeps_the_last_ones_link_working_and_listed(client, db_session, shared,
                                                                            monkeypatch):
    owner, _rows, plan, path = shared
    _at(monkeypatch, "2026-12-01")
    sign_in(client, owner)
    wrapping = client.get("/api/break?today=2026-12-01").json()
    assert wrapping["plan"]["id"] == plan["id"] and wrapping["older_links"] == []  # its own panel shows the link
    # The home card's "Share how it went" link went on a story. Planning next weekend used to cancel the
    # finished plan, which turned that link off weeks before the date its page gave.
    made = client.post("/api/break", json={"starts_on": "2026-12-05", "ends_on": "2026-12-06", "minutes": {},
                                          "today": "2026-12-01"})
    assert made.status_code == 201, made.text
    newer = made.json()["plan"]
    assert newer["id"] != plan["id"]
    assert [link["id"] for link in made.json()["older_links"]] == [plan["id"]]
    db_session.expire_all()
    assert db_session.get(models.BreakPlan, plan["id"]).status == break_plan.REPLACED
    sign_out(client)
    assert client.get(path, headers=CHROME).status_code == 200
    assert client.get(f"{path}/card.png").status_code == 200
    sign_in(client, owner)
    client.post(f"/api/break/{newer['id']}/share", json={"today": "2026-12-01"})
    state = client.get("/api/break?today=2026-12-01").json()
    assert state["plan"]["id"] == newer["id"] and state["plan"]["share"]
    assert [link["id"] for link in state["older_links"]] == [plan["id"]]
    # The old plan can only have its link turned off; everything else about it is closed.
    assert client.post(f"/api/break/{plan['id']}/fill", json={"today": "2026-12-01"}).status_code == 404
    assert client.post(f"/api/break/{plan['id']}/share", json={"today": "2026-12-01"}).status_code == 404
    assert client.delete(f"/api/break/{plan['id']}/share?today=2026-12-01").status_code == 200
    sign_out(client)
    assert client.get(path, headers=CHROME).status_code == 404
    assert break_plan.active(db_session, owner.id, datetime(2026, 12, 1).date()).id == newer["id"]


def test_older_links_stop_listing_once_they_stop_working_and_belong_to_their_owner(client, db_session, shared,
                                                                                  monkeypatch):
    owner, _rows, plan, _path = shared
    remy = make_user(db_session, "remy")
    sign_in(client, remy)
    assert client.get("/api/break?today=2026-12-05").json()["older_links"] == []
    assert client.delete(f"/api/break/{plan['id']}/share?today=2026-12-05").status_code == 404
    _at(monkeypatch, "2026-12-30")
    sign_in(client, owner)
    assert client.get("/api/break?today=2026-12-30").json()["older_links"] == []
    db_session.expire_all()
    assert db_session.get(models.BreakPlan, plan["id"]).share_token  # remy's delete changed nothing


def test_the_planner_draws_older_links_with_text_only():
    source = (ROOT / "app/static/break-plan.js").read_text(encoding="utf-8")
    body = source[source.index("function olderLinks"):source.index("// ------", source.index("function olderLinks"))]
    assert "innerHTML" not in body and "insertAdjacentHTML" not in body
    assert "data.older_links" in body and "Turn it off" in body
    assert "/share`, { method: 'DELETE' }" in body
    # The same-days step names whose plan it is, not the plan's own name ("the same as Your break").
    assert "the same as ${from.name}" not in source


# ---------------------------------------------------------------- the share page's work

def test_the_share_page_builds_the_shared_view_once(client, db_session, shared, monkeypatch):
    _owner, _rows, plan, path = shared
    calls = []
    real = break_plan.shared_view

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(break_plan, "shared_view", counted)
    page = client.get(path, headers=CHROME).text
    assert len(calls) == 1
    version = re.search(r"/card\.png\?v=([0-9a-f]{16})", page).group(1)
    row = db_session.get(models.BreakPlan, plan["id"])
    today = break_plan._now().date()
    assert version == break_share.fingerprint(break_plan.card_facts(db_session, row, today))
