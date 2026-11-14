"""Sweep of the Nov 12 merges: group poll upgrades (#202), the awards ballot (#203) and the
Statistics and Settings redesign (#204), after the Nov 12 sweep itself (#201)."""
import threading

from sqlalchemy import event

from app import title_metadata, title_search, tonight_polls
from app.routers import awards as awards_router
from app.routers import tonight as tonight_router
from tests.conftest import engine
from tests.test_security_sweep_nov06 import _limited
from tests.test_shared_lists import _as
from tests.test_title_pages import add_movie, member
from tests.test_tonight_polls import _close_with_winner, _make


# ---------------------------------------------------------------- rate limits

def test_every_group_poll_api_route_is_rate_limited():
    """The October routes had none, and a poll's read route answers anyone holding the link."""
    checked = 0
    for route in tonight_router.router.routes:
        if not route.path.startswith("/api/"):
            continue
        for method in route.methods:
            assert _limited(tonight_router.router, route.path, method), (method, route.path)
            checked += 1
    assert checked == 12


def test_every_awards_api_route_and_shared_ballot_is_rate_limited():
    for route in awards_router.router.routes:
        if not route.path.startswith(("/api/", "/ballot/")):
            continue
        for method in route.methods:
            assert _limited(awards_router.router, route.path, method), (method, route.path)


def test_the_newly_limited_poll_routes_still_answer(authenticated_client, db_session):
    token = _make(authenticated_client)["token"]
    assert authenticated_client.get("/api/tonight").status_code == 200
    assert authenticated_client.get("/api/tonight/suggestions").status_code == 200
    ids = [option["id"] for option in authenticated_client.get(f"/api/tonight/{token}").json()["options"]]
    assert authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": ids[0]}).status_code == 200
    assert authenticated_client.delete(f"/api/tonight/{token}/vote").status_code == 200
    assert authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": ids[1]}).status_code == 200
    assert authenticated_client.post(f"/api/tonight/{token}/close").status_code == 200
    assert authenticated_client.delete(f"/api/tonight/{token}").status_code == 204


# ---------------------------------------------------------------- where to watch the winner

def test_finding_the_winner_runs_off_the_event_loop(authenticated_client, db_session, monkeypatch):
    """The route is async for the lookups, so its database reads used to hold up every other request."""
    from tests.test_where_to_watch import MOVIE_META, WHERE
    token = _make(authenticated_client)["token"]
    title_metadata.store(db_session, "movie:arrival:2016", MOVIE_META, "ok")
    title_metadata.store(db_session, "where:movie:arrival:2016", WHERE, "ok")
    _close_with_winner(authenticated_client, db_session, token)
    threads = {}
    find, lookup = tonight_router._winner_to_look_up, title_metadata.get_or_fetch

    def finding(*args):
        threads["db"] = threading.get_ident()
        return find(*args)

    async def looking(*args, **kwargs):
        threads["loop"] = threading.get_ident()
        return await lookup(*args, **kwargs)

    monkeypatch.setattr(tonight_router, "_winner_to_look_up", finding)
    monkeypatch.setattr(tonight_router.title_metadata, "get_or_fetch", looking)
    _as(authenticated_client, None)
    response = authenticated_client.get(f"/api/tonight/{token}/where")
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Arrival"
    assert threads["db"] != threads["loop"]


def test_an_open_or_missing_poll_still_has_nothing_to_look_up(authenticated_client):
    token = _make(authenticated_client)["token"]
    assert authenticated_client.get(f"/api/tonight/{token}/where").status_code == 404
    assert authenticated_client.get("/api/tonight/NoSuchPollHere1/where").status_code == 404


# ---------------------------------------------------------------- popular starter titles

def _count_sql(call):
    statements = []

    def seen(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", seen)
    try:
        result = call()
    finally:
        event.remove(engine, "before_cursor_execute", seen)
    return result, len(statements)


def test_visitor_starter_titles_are_worked_out_once_per_ten_minutes(authenticated_client, db_session):
    """Each signed-out visit to /tonight asked the database to group three whole library tables."""
    for name in ("ana", "ben"):
        person = member(db_session, name)
        add_movie(db_session, person, "Arrival", 2016, poster_url="https://image.tmdb.org/t/p/w500/arrival.jpg")
    db_session.commit()
    title_search.clear_cache()
    first, first_sql = _count_sql(lambda: authenticated_client.get("/api/tonight/starters").json())
    again, again_sql = _count_sql(lambda: authenticated_client.get("/api/tonight/starters").json())
    assert [entry["title"] for entry in first["titles"]] == ["Arrival"]
    assert again == first
    assert first_sql >= 3 and again_sql == 0
    # Callers get copies, so nobody can change the kept answer.
    tonight_polls.starters(db_session)[0]["title"] = "Changed"
    assert tonight_polls.starters(db_session)[0]["title"] == "Arrival"
    tonight_polls.clear_starters_cache()
    _, cleared_sql = _count_sql(lambda: tonight_polls.starters(db_session))
    assert cleared_sql >= 3


def test_starter_titles_expire(db_session, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(tonight_polls.time, "monotonic", lambda: clock[0])
    tonight_polls.starters(db_session)
    _, cached_sql = _count_sql(lambda: tonight_polls.starters(db_session))
    clock[0] += tonight_polls.STARTERS_CACHE_SECONDS + 1
    _, expired_sql = _count_sql(lambda: tonight_polls.starters(db_session))
    assert cached_sql == 0 and expired_sql > 0
