"""Sweep of the Nov 16 2026 evening merges: the /start poster wall (#225), email sign-up step
counters and title lookup fixes (#227), the stay-posted card and note (#226), taste test
invites (#228) and the search signals pass (#229)."""
import json
from datetime import datetime

from sqlalchemy import event

from app import digest, models, stay_posted, title_metadata, title_pages
from app.routers import invites as invites_router
from app.routers import start as start_router
from app.routers import stay_posted as stay_posted_router
from app.site_traffic import RECORDER
from tests.conftest import engine
from tests.test_security_sweep_nov06 import _limited
from tests.test_stay_posted import headers, member


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


# ---------------------------------------------------------------- rate limits

def test_every_start_and_stay_posted_api_route_is_rate_limited():
    for router in (start_router.router, stay_posted_router.router):
        for route in router.routes:
            if not route.path.startswith("/api/"):
                continue
            for method in route.methods:
                assert _limited(router, route.path, method), (method, route.path)


def test_taste_test_invite_routes_are_rate_limited():
    """The guess route answers anyone holding a /join link, so it gets the compare guess limit."""
    for route in invites_router.router.routes:
        for method in route.methods:
            assert _limited(invites_router.router, route.path, method), (method, route.path)


# ---------------------------------------------------------------- the poster wall

def test_poster_wall_reads_cached_covers_in_one_query(authenticated_client, db_session):
    for title, year, status, poster in (("Interstellar", 2014, "ok", "https://image.tmdb.org/t/p/w342/known.jpg"),
                                        ("The Matrix", 1999, "error", "https://image.tmdb.org/t/p/w342/reason.jpg")):
        db_session.add(models.TitleMetadata(key=title_metadata.cache_key("movie", title_pages.normalize(title), year),
                                            status=status, data=json.dumps({"poster": poster}), fetched_at=datetime.utcnow()))
    db_session.commit()
    response, statements = _count_sql(lambda: authenticated_client.get("/api/start/deck?kinds=movie,tv,anime,game,book,music"))
    assert response.status_code == 200
    cards = {card["id"]: card for card in response.json()["cards"]}
    assert len(cards) >= 40
    assert cards["movie/interstellar-2014"]["image"] == "https://image.tmdb.org/t/p/w342/known.jpg"
    # A failed lookup's saved reason is never read as a cover.
    assert cards["movie/the-matrix-1999"]["image"] is None
    lookups = [sql for sql in statements if "FROM title_metadata" in sql]
    assert len(lookups) == 1, len(lookups)


# ---------------------------------------------------------------- stay posted

def test_stay_posted_card_counts_the_library_in_one_query(client, db_session, monkeypatch):
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    user = member(db_session)
    user_id = user.id
    assert stay_posted._library_size(db_session, user_id) == 12
    db_session.add(models.Book(title="Dune", author="Frank Herbert", read=True, user_id=user_id))
    db_session.commit()
    total, statements = _count_sql(lambda: stay_posted._library_size(db_session, user_id))
    assert total == 13 and len(statements) == 1
    _, statements = _count_sql(lambda: client.get("/api/stay-posted", headers=headers(user)))
    assert len(statements) <= 20, len(statements)


def _counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "stay" and name == key)


def test_a_channel_answer_counts_only_when_the_channel_is_on_and_only_once(client, db_session, monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setattr(digest, "mail_configured", lambda: True)
    monkeypatch.setattr(stay_posted, "upcoming", lambda db, user, today=None: [])
    RECORDER._pending.clear()
    try:
        user = member(db_session)
        assert client.post("/api/stay-posted/seen", headers=headers(user), json={"moment": "library"}).json() == {"shown": True}

        def answer(reply):
            return client.post("/api/stay-posted/answer", headers=headers(user), json={"answer": reply}).json()

        # A hand-made "calendar" answer with no calendar is not counted as turned on.
        assert answer("calendar") == {"saved": False}
        assert _counted("card_calendar_library") == 0
        assert client.post("/api/calendar", headers=headers(user)).status_code == 200
        assert answer("calendar") == {"saved": True}
        assert answer("calendar") == {"saved": True}
        assert _counted("card_calendar_library") == 1
        # The sample email can be opened as often as they like; each look counts.
        answer("sample")
        answer("sample")
        assert _counted("card_sample_library") == 2
    finally:
        RECORDER._pending.clear()
