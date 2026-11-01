"""Regression tests for the Oct 30 sweep of memberships, time spent, why-I-added-it, On this day and the reader pages."""
from datetime import date, datetime

from sqlalchemy import event

from app import memories, models
from tests.test_friend_recs import _me
from tests.test_memories import _push_member, journal


def test_deleting_the_memory_notification_does_not_send_it_again(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    db_session.commit()
    journal(db_session, me, "movies", "Heat", "completed", datetime(2025, 10, 29, 18, 0), rating=10)
    _push_member(db_session, me, {"memories": True})
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 15, 0)) == 1  # 10 am in Chicago
    [note] = db_session.query(models.Notification).filter_by(user_id=me.id, type="memory").all()

    assert authenticated_client.delete(f"/notifications/{note.id}").status_code == 200
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 15, 15)) == 0
    assert db_session.query(models.Notification).filter_by(user_id=me.id, type="memory").count() == 0
    # The next local day is a new day.
    journal(db_session, me, "movies", "Ronin", "completed", datetime(2025, 10, 30, 18, 0))
    assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 30, 15, 0)) == 1


def test_a_day_with_nothing_to_show_is_looked_at_once(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    db_session.commit()
    _push_member(db_session, me, {"memories": True})
    calls = []
    real = memories.collect
    memories.collect = lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs)
    try:
        assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 15, 0)) == 0
        assert memories.send_due_pushes(db_session, now=datetime(2026, 10, 29, 15, 15)) == 0
    finally:
        memories.collect = real
    assert len(calls) == 1


def test_week_in_past_years_reads_the_week_in_one_pass(authenticated_client, db_session):
    me = _me(db_session)
    me.created_at = datetime(2020, 1, 1)
    db_session.commit()
    journal(db_session, me, "movies", "Alien", "completed", datetime(2023, 10, 25, 12, 0), rating=8)
    journal(db_session, me, "books", "Dune", "completed", datetime(2021, 10, 28, 12, 0), rating=9)
    journal(db_session, me, "movies", "Started only", "started", datetime(2024, 10, 26, 12, 0))
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        found = memories.week_in_past_years(db_session, me, date(2026, 10, 29))
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert [(m["title"], m["ago"]) for m in found] == [("Dune", 5), ("Alien", 3)]
    # One collect: the first-entry lookup, the journal, its titles and reflections, collections and the
    # eight shelves' adds. Seven separate collects ran 82 here.
    assert len(statements) < 30
