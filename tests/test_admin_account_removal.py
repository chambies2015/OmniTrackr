"""Owner-only "Remove an account" on Site stats: preview, typed confirmation, clean removal."""
import logging
from pathlib import Path

import pytest

from app import account_removal, models
from app.database import Base

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def owner(authenticated_client, monkeypatch):
    for name in ("ADMIN_USERNAMES", "COLLECTION_MODERATOR_USERNAMES", "admin_usernames", "collection_moderator_usernames"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    return authenticated_client


def member(db, username, **extra):
    user = models.User(username=username, email=f"{username}@example.com", hashed_password="x", **extra)
    db.add(user)
    db.commit()
    return user


def movie(db, user, title):
    row = models.Movie(title=title, director="Someone", year=2020, user_id=user.id)
    db.add(row)
    db.commit()
    return row


def preview(client, username):
    return client.get("/api/site-stats/accounts", params={"username": username})


def remove(client, user, confirm=None):
    return client.post("/api/site-stats/accounts/remove",
                       json={"user_id": user.id, "username": user.username, "confirm": user.username if confirm is None else confirm})


def references_to(db, user_id):
    """Every row anywhere that still points at this account id."""
    found = {}
    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table is models.User.__table__:
                count = db.execute(table.select().where(foreign_key.parent == user_id)).all()
                if count:
                    found[f"{table.name}.{foreign_key.parent.name}"] = len(count)
    return found


# ---------------------------------------------------------------- who may use it

def test_members_who_are_not_the_owner_get_403(authenticated_client, db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAMES", raising=False)
    monkeypatch.delenv("COLLECTION_MODERATOR_USERNAMES", raising=False)
    probe = member(db_session, "probe")
    assert preview(authenticated_client, "probe").status_code == 403
    assert remove(authenticated_client, probe).status_code == 403
    assert db_session.get(models.User, probe.id) is not None


def test_signed_out_visitors_get_401(client, db_session):
    probe = member(db_session, "probe")
    assert preview(client, "probe").status_code == 401
    assert remove(client, probe).status_code == 401


def test_cross_site_post_is_rejected(owner, db_session):
    probe = member(db_session, "probe")
    response = owner.post("/api/site-stats/accounts/remove", headers={"Origin": "https://evil.example"},
                          json={"user_id": probe.id, "username": "probe", "confirm": "probe"})
    assert response.status_code == 403
    assert db_session.get(models.User, probe.id) is not None


# ---------------------------------------------------------------- preview

def test_preview_describes_the_account_without_changing_anything(owner, db_session):
    probe = member(db_session, "probe", is_verified=False)
    movie(db_session, probe, "Probe film")
    response = preview(owner, "probe")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "probe" and data["user_id"] == probe.id
    assert data["can_remove"] is True and data["reason"] is None
    assert data["verified"] is False and data["titles"] == 1
    assert data["email_domain"] == "example.com"
    assert "probe@example.com" not in response.text
    assert {"table": "movies", "label": "movies", "count": 1} in data["rows"]
    assert response.headers["Cache-Control"] == "private, no-store"
    db_session.expire_all()
    assert db_session.get(models.User, probe.id) is not None
    assert db_session.query(models.Movie).count() == 1


def test_preview_needs_the_exact_username(owner, db_session):
    member(db_session, "probe")
    assert preview(owner, "Probe").status_code == 404
    assert preview(owner, "@probe").status_code == 200


# ---------------------------------------------------------------- removal

def test_wrong_confirmation_removes_nothing(owner, db_session):
    probe = member(db_session, "probe")
    for typed in ("", "Probe", "probe ", "testuser"):
        assert remove(owner, probe, confirm=typed).status_code == 422
    db_session.expire_all()
    assert db_session.get(models.User, probe.id) is not None


def test_stale_lookup_is_refused(owner, db_session):
    probe = member(db_session, "probe")
    response = owner.post("/api/site-stats/accounts/remove",
                          json={"user_id": probe.id, "username": "someone-else", "confirm": "someone-else"})
    assert response.status_code == 404
    assert db_session.get(models.User, probe.id) is not None


def test_removal_takes_only_that_account(owner, db_session, caplog):
    probe = member(db_session, "probe")
    friend = member(db_session, "friend")
    owner_row = db_session.query(models.User).filter_by(username="testuser").one()
    movie(db_session, probe, "Probe film")
    kept = movie(db_session, friend, "Friend film")
    mine = movie(db_session, owner_row, "Owner film")
    db_session.add(models.Friendship(user1_id=min(probe.id, friend.id), user2_id=max(probe.id, friend.id)))
    request = models.FriendRequest(sender_id=probe.id, receiver_id=friend.id)
    db_session.add(request)
    db_session.commit()
    note = models.Notification(user_id=friend.id, type="friend_request", message="probe wants to be friends",
                               friend_request_id=request.id)
    payment = models.KofiPayment(message_id="kofi-1", kind="Donation", user_id=probe.id)
    db_session.add_all([note, payment])
    db_session.commit()
    probe_id, note_id, payment_id = probe.id, note.id, payment.id

    with caplog.at_level(logging.WARNING, logger="omnitrackr.admin"):
        response = remove(owner, probe)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["removed"] is True and data["username"] == "probe"
    assert any("removed username=probe" in record.getMessage() and "admin=testuser" in record.getMessage()
               for record in caplog.records)

    db_session.expire_all()
    assert db_session.get(models.User, probe_id) is None
    assert references_to(db_session, probe_id) == {}
    # Everyone else is untouched.
    assert db_session.get(models.User, friend.id) is not None
    assert db_session.get(models.Movie, kept.id) is not None
    assert db_session.get(models.Movie, mine.id) is not None
    assert db_session.query(models.User).filter_by(username="testuser").one()
    # The friend's own notification stays; only its link to the gone request is cleared.
    kept_note = db_session.get(models.Notification, note_id)
    assert kept_note is not None and kept_note.friend_request_id is None
    # Payment records are kept for the books, just no longer tied to an account.
    kept_payment = db_session.get(models.KofiPayment, payment_id)
    assert kept_payment is not None and kept_payment.user_id is None
    # The owner is still signed in.
    assert owner.get("/api/site-stats/access").json() == {"admin": True}
    assert preview(owner, "probe").status_code == 404


def test_owner_cannot_remove_themselves_or_another_admin(owner, db_session, monkeypatch):
    me = db_session.query(models.User).filter_by(username="testuser").one()
    response = remove(owner, me)
    assert response.status_code == 409
    assert "your own account" in response.json()["detail"]
    other = member(db_session, "second")
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser,second")
    assert preview(owner, "second").json()["can_remove"] is False
    assert remove(owner, other).status_code == 409
    db_session.expire_all()
    assert db_session.get(models.User, other.id) is not None


def test_removal_is_refused_when_it_would_take_another_members_rows(owner, db_session):
    probe = member(db_session, "probe")
    friend = member(db_session, "friend")
    thread = models.TitleDiscussion(kind="movie", slug="probe-film", title="Probe film", user_id=probe.id,
                                    subject="Thoughts?", body="Talk about it")
    db_session.add(thread)
    db_session.commit()
    reply = models.TitleDiscussionReply(discussion_id=thread.id, user_id=friend.id, body="Loved it")
    db_session.add(reply)
    db_session.commit()

    data = preview(owner, "probe").json()
    assert data["can_remove"] is False
    assert data["other_members_rows"] == [{"table": "title_discussion_replies", "label": "title discussion replies", "count": 1}]
    assert "Deactivate it instead" in data["reason"]
    response = remove(owner, probe)
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(models.User, probe.id) is not None
    assert db_session.get(models.TitleDiscussionReply, reply.id) is not None


def test_own_rows_deeper_down_go_with_the_account(owner, db_session):
    """A reply the account wrote on its own discussion is its own row, not someone else's."""
    probe = member(db_session, "probe")
    thread = models.TitleDiscussion(kind="movie", slug="probe-film", title="Probe film", user_id=probe.id,
                                    subject="Thoughts?", body="Talk about it")
    db_session.add(thread)
    db_session.commit()
    db_session.add(models.TitleDiscussionReply(discussion_id=thread.id, user_id=probe.id, body="Me again"))
    db_session.commit()
    probe_id = probe.id
    assert remove(owner, probe).status_code == 200
    db_session.expire_all()
    assert db_session.query(models.TitleDiscussion).count() == 0
    assert db_session.query(models.TitleDiscussionReply).count() == 0
    assert references_to(db_session, probe_id) == {}


def test_a_busy_account_removes_cleanly_with_foreign_keys_enforced(owner, db_session):
    """Production runs PostgreSQL, which checks every foreign key; SQLite does too with the pragma on."""
    from datetime import date, datetime, timedelta
    from sqlalchemy import text

    db_session.commit()
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    try:
        probe = member(db_session, "probe")
        friend = member(db_session, "friend")
        later = datetime.utcnow() + timedelta(days=7)
        movie(db_session, probe, "Probe film")
        club = models.SharedList(owner_id=probe.id, name="Probe club", token="probe-club-token")
        poll = models.TonightPoll(token="probe-poll", owner_id=probe.id, question="What tonight?", closes_at=later)
        collection = models.Collection(user_id=probe.id, name="Probe picks")
        tab = models.CustomTab(user_id=probe.id, name="Board games", slug="board-games")
        gifts = models.GiftList(owner_id=probe.id, token="probe-gifts")
        take = models.TakeRequest(asker_id=probe.id, kind="movie", slug="probe-film", title="Probe film",
                                  token="probe-take", expires_at=later)
        asked = models.RecommendationRequest(owner_id=probe.id, public_token="probe-ask", prompt="Anything?",
                                             allowed_categories="movies", expires_at=later)
        db_session.add_all([club, poll, collection, tab, gifts, take, asked])
        db_session.commit()
        db_session.add(models.SharedListMember(list_id=club.id, user_id=probe.id))
        item = models.SharedListItem(list_id=club.id, kind="movie", title="Probe film", normalized="probe film",
                                     added_by_id=probe.id)
        club_round = models.ClubRound(list_id=club.id, kind="movie", title="Probe film",
                                      ends_on=date.today() + timedelta(days=7), started_by_id=probe.id)
        option = models.TonightPollOption(poll_id=poll.id, kind="movie", title="Probe film")
        db_session.add_all([item, club_round, option,
                            models.CollectionItem(collection_id=collection.id, category="movies", item_id=1),
                            models.CustomTabField(tab_id=tab.id, key="players", label="Players", field_type="text"),
                            models.CustomTabItem(tab_id=tab.id, title="Catan"),
                            models.GiftListItem(list_id=gifts.id, kind="book", title="A book", normalized="a book"),
                            models.RecommendationSubmission(request_id=asked.id, guest_name="Guest", category="movies",
                                                            title="Heat", reason="Great")])
        db_session.commit()
        first = models.FriendRecommendation(sender_id=probe.id, recipient_id=friend.id, category="movies", title="Heat")
        db_session.add(first)
        db_session.commit()
        db_session.add_all([
            models.FriendRecommendation(sender_id=friend.id, recipient_id=probe.id, category="movies", title="Heat",
                                        source_id=first.id),
            models.SharedListVote(item_id=item.id, user_id=probe.id),
            models.ClubPost(round_id=club_round.id, user_id=probe.id, body="Week one"),
            models.ClubProgress(round_id=club_round.id, user_id=probe.id, status="started"),
            models.TonightPollVote(poll_id=poll.id, option_id=option.id),  # a guest's vote
            models.TakeResponse(request_id=take.id, responder_id=probe.id),
        ])
        db_session.commit()
        probe_id, friend_id = probe.id, friend.id

        data = preview(owner, "probe").json()
        assert data["can_remove"] is True, data["reason"]
        response = remove(owner, probe)
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert references_to(db_session, probe_id) == {}
        assert db_session.query(models.SharedList).count() == 0
        assert db_session.query(models.ClubPost).count() == 0
        assert db_session.query(models.TonightPollVote).count() == 0
        assert db_session.query(models.CustomTabItem).count() == 0
        # Recommendations to or from the account go with it.
        assert db_session.query(models.FriendRecommendation).count() == 0
        assert db_session.get(models.User, friend_id) is not None
        assert db_session.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        db_session.rollback()
        db_session.execute(text("PRAGMA foreign_keys=OFF"))


# ---------------------------------------------------------------- the schema walk

def test_every_table_the_walk_can_reach_has_a_single_column_key():
    """Removal deletes row by row, so a future table with a composite key must be noticed here."""
    reached, queue = set(), [models.User.__table__]
    while queue:
        table = queue.pop()
        for foreign_key in account_removal._referencing(table):
            child = foreign_key.parent.table
            if child.name not in reached:
                reached.add(child.name)
                assert len(child.primary_key.columns) == 1, child.name
                queue.append(child)
    assert {"movies", "friendships", "club_posts", "kofi_payments"} <= reached


# ---------------------------------------------------------------- page

def test_site_stats_page_has_the_remove_card():
    html = (ROOT / "app" / "templates" / "site_stats.html").read_text(encoding="utf-8")
    assert 'id="removeCard"' in html and 'id="removeConfirm"' in html
    script = (ROOT / "app" / "static" / "site-stats.js").read_text(encoding="utf-8")
    assert "/api/site-stats/accounts/remove" in script
