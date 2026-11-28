"""Nov 26 2026 sweep of the yearbook (#339): a let-in note from someone who isn't a friend can't be
swapped for new words without the owner reading them, the per-address cap holds under the book lock,
a preview book tells friends once signing opens, a closing bell survives a later failed check, and a
preview link before opening day doesn't say signing closed."""
import asyncio
from datetime import datetime

from app import models, yearbook
from tests.test_yearbook import Clock, befriend, clock, make_book, make_user, sign, sign_in, sign_out, token_of  # noqa: F401


def _note(db, user):
    db.expire_all()
    return db.query(models.YearbookSignature).filter_by(signer_id=user.id).one()


def test_a_let_in_note_from_a_non_friend_waits_again_after_a_change(client, db_session, clock):
    dana = make_user(db_session, "dana")
    lee = make_user(db_session, "lee")
    make_book(client, dana)
    token = token_of(db_session, dana)
    assert sign(client, token, lee, note="Great year of films").json()["status"] == "waiting"
    note_id = _note(db_session, lee).id
    sign_in(client, dana)
    assert client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "show"}).json() == {"status": "shown"}
    sign_in(client, lee)
    assert "reads it again before the new version shows" in client.get(f"/yearbook/{token}").text
    # Saving the same words again changes nothing.
    assert sign(client, token, lee, note="Great year of films").json() == {"status": "shown", "new": False}
    db_session.query(models.Notification).update({models.Notification.read_at: datetime(2026, 12, 5, 16, 0)})
    db_session.commit()
    swapped = sign(client, token, lee, note="Something the owner never read")
    assert swapped.json() == {"status": "waiting", "new": False}
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "Something the owner never read" not in page and "Great year of films" not in page
    bell = db_session.query(models.Notification).filter_by(user_id=dana.id, type="yearbook_waiting",
                                                            read_at=None).one()
    assert bell.message == "lee changed their note in your yearbook. It shows again once you let it in."
    assert bell.link == "/yearbook#waiting"
    # A new vote alone counts as a change too.
    sign_in(client, dana)
    client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "show"})
    assert sign(client, token, lee, note="Something the owner never read",
                superlative="twist").json()["status"] == "waiting"


def test_friends_keep_changing_their_note_in_place(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign(client, token, sam)
    assert sign(client, token, sam, note="A new note").json() == {"status": "shown", "new": False}
    page = client.get(f"/yearbook/{token}").text
    assert "Your note is in the yearbook." in page and "reads it again" not in page


def test_a_note_let_in_from_a_friend_who_since_left_waits_after_a_change(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    token = token_of(db_session, dana)
    assert sign(client, token, sam).json()["status"] == "shown"
    db_session.query(models.Friendship).delete()
    db_session.commit()
    assert sign(client, token, sam, note="Different words now").json()["status"] == "waiting"


def test_the_guest_cap_is_counted_under_the_book_lock(db_session, clock, monkeypatch):
    dana = make_user(db_session, "dana")
    book, _ = yearbook.save(db_session, dana, 2026, cover_name="Dana", quote=None, picks=[], show_numbers=True,
                            listed=False)
    db_session.commit()
    order = []
    real_query = db_session.query

    def watching(*entities, **kwargs):
        query = real_query(*entities, **kwargs)
        if entities and entities[0] is models.Yearbook:
            original = query.with_for_update

            def locked(*args, **kw):
                order.append("lock")
                return original(*args, **kw)
            query.with_for_update = locked
        return query

    monkeypatch.setattr(db_session, "query", watching)
    real_mark = yearbook._mark
    monkeypatch.setattr(yearbook, "_mark", lambda address, book: order.append("mark") or real_mark(address, book))
    for index in range(yearbook.GUEST_PER_ADDRESS):
        yearbook.sign(db_session, book, guest_name=f"Guest {index}", note="Hello there", address="203.0.113.9")
    try:
        yearbook.sign(db_session, book, guest_name="Again", note="Hello again", address="203.0.113.9")
    except yearbook.YearbookError as error:
        assert error.status == 429
    else:
        raise AssertionError("the fourth note from one address went in")
    # The count for the fourth note ran after the lock, not before it.
    assert order[-2:] == ["mark", "lock"]


def test_a_preview_book_tells_friends_once_signing_opens(client, db_session, monkeypatch):
    clock = Clock(monkeypatch, datetime(2026, 11, 20, 12, 0))
    monkeypatch.setenv("ADMIN_USERNAMES", "dana")
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    assert db_session.query(models.Notification).filter_by(user_id=sam.id, type="yearbook_friend").count() == 0
    clock.at = datetime(2026, 11, 27, 9, 0)
    make_book(client, dana, quote="Open now")
    make_book(client, dana, quote="Open now, again")
    assert db_session.query(models.Notification).filter_by(user_id=sam.id, type="yearbook_friend").count() == 1


def test_a_preview_link_before_opening_day_says_when_signing_opens(client, db_session, monkeypatch):
    Clock(monkeypatch, datetime(2026, 11, 20, 12, 0))
    monkeypatch.setenv("ADMIN_USERNAMES", "dana")
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "Signing opens on November 26" in page
    assert "Signing closed" not in page and "Nobody signed this one" not in page
    assert "data-yearbook-sign " not in page and "Sign the yearbook" not in page


def test_a_closing_bell_survives_a_later_books_failed_check(db_session, monkeypatch):
    from tests.conftest import TestingSessionLocal
    Clock(monkeypatch, datetime(2026, 12, 5, 15, 0))
    dana = make_user(db_session, "dana")
    lee = make_user(db_session, "lee")
    sam = make_user(db_session, "sam")
    first, _ = yearbook.save(db_session, dana, 2026, cover_name="Dana", quote=None, picks=[], show_numbers=True,
                             listed=False)
    second, _ = yearbook.save(db_session, lee, 2026, cover_name="Lee", quote=None, picks=[], show_numbers=True,
                              listed=False)
    db_session.commit()
    befriend(db_session, dana, sam)
    yearbook.sign(db_session, first, user=sam, note="See you next year")
    db_session.commit()
    first_id, second_id = first.id, second.id
    real_due = yearbook.email_due

    def flaky(db, book, now):
        if book.id == second_id:
            raise RuntimeError("boom")
        return real_due(db, book, now)

    monkeypatch.setattr(yearbook, "email_due", flaky)
    monkeypatch.setattr(yearbook, "allowance", lambda db, at: 10)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append(to)

    closed = datetime(2027, 1, 3, 9, 0)
    result = asyncio.run(yearbook.run_once(TestingSessionLocal, now=closed, sender=sender))
    assert result["closed_notes"] == 1 and sent == ["dana@example.test"]
    db_session.expire_all()
    assert db_session.get(models.Yearbook, first_id).closed_told_at is not None
    assert db_session.query(models.Notification).filter_by(user_id=dana.id, type="yearbook_closed").count() == 1


def test_an_empty_recap_leaves_the_yearbook_box_off(authenticated_client, db_session, clock):
    page = authenticated_client.get("/year-in-review/2026").text
    assert "Nothing was logged this year yet" in page
    assert 'aria-labelledby="recap-yearbook"' not in page
