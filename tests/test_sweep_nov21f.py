"""Nov 21 afternoon sweep of #292 (October 2027), #293 (library length limits) and #294 (November and December 2027).

The November "tell" step counts recommendations made this month, so sending a title again to a friend who still
has it waiting from an earlier month has to count; the October "draw" step must not offer a kept card whose
title was finished before the month; and the October card's "Deal me in" has to bring the backlog draw out
from behind Show more (that part is pinned in test_backlog_draw_ui.cjs and test_home_layout_ui.cjs).
"""
from datetime import date, datetime, timedelta
from pathlib import Path

from app import backlog_draw, challenges, models, title_pages
from app.routers import titles

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
STATIC = ROOT / "app" / "static"
CHANGELOG = (ROOT / "app" / "templates" / "changelog.html").read_text(encoding="utf-8")
OCTOBER = datetime(2027, 10, 10, 20, 0)


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=False, **fields):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished}, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _friends(db_session, me, friend):
    db_session.add(models.Friendship(user1_id=min(me.id, friend.id), user2_id=max(me.id, friend.id)))
    db_session.commit()


# ---------------------------------------------------------------- #294 tell step


def test_sending_a_title_still_waiting_from_an_earlier_month_counts_this_month(authenticated_client, db_session):
    me = _user(db_session)
    friend = _member(db_session, "stillwaiting")
    _friends(db_session, me, friend)
    film = _row(db_session, me, models.Movie, "The Princess Bride", year=1987)
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    waiting = models.FriendRecommendation(sender_id=me.id, recipient_id=friend.id, category="movies", title="The Princess Bride",
                                          details="{}", note="old note", created_at=start - timedelta(days=5))
    db_session.add(waiting)
    db_session.commit()
    month = challenges.month_key()
    assert challenges.tell_count(db_session, me.id, month) == 0
    pings = db_session.query(models.Notification).filter_by(user_id=friend.id).count()

    sent = authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": film.id,
                                                              "friend_ids": [friend.id], "note": "Watch it again"})
    assert sent.status_code == 200, sent.text
    assert (sent.json()["sent"], sent.json()["already"]) == (0, 1)
    # Still one row in their inbox and no second ping, but it is this month's telling now.
    assert challenges.tell_count(db_session, me.id, month) == 1
    db_session.refresh(waiting)
    assert waiting.note == "Watch it again" and waiting.created_at >= start and waiting.status == "pending"
    assert db_session.query(models.FriendRecommendation).filter_by(sender_id=me.id).count() == 1
    assert db_session.query(models.Notification).filter_by(user_id=friend.id).count() == pings


def test_sending_again_in_the_same_month_leaves_the_inbox_order_alone(authenticated_client, db_session):
    me = _user(db_session)
    friend = _member(db_session, "samemonth")
    _friends(db_session, me, friend)
    book = _row(db_session, me, models.Book, "The Thirteenth Tale")
    now = datetime.utcnow()
    earlier = max(datetime(now.year, now.month, 1), now - timedelta(hours=2))
    waiting = models.FriendRecommendation(sender_id=me.id, recipient_id=friend.id, category="books", title="The Thirteenth Tale",
                                          details="{}", created_at=earlier)
    db_session.add(waiting)
    db_session.commit()
    sent = authenticated_client.post("/api/friend-recs", json={"category": "books", "item_id": book.id, "friend_ids": [friend.id]})
    assert sent.status_code == 200 and sent.json()["already"] == 1
    db_session.refresh(waiting)
    assert waiting.created_at == earlier


def test_the_dialog_tells_the_challenge_card_about_a_send_that_was_already_waiting():
    js = (STATIC / "friend-recs.js").read_text(encoding="utf-8")
    assert "if (data.sent || data.already) told('friends');" in js
    assert titles.FRIEND_RECS_VERSION == "20261121-sweep-f-1"
    assert "/static/friend-recs.js?v=20261121-sweep-f-1" in INDEX


# ---------------------------------------------------------------- #292 draw step


def test_a_kept_card_finished_before_october_is_not_offered_as_the_deal(db_session):
    user = _member(db_session, "finishedearly")
    film = _row(db_session, user, models.Movie, "Dune")
    for title in ("Arrival", "Heat", "Alien"):
        _row(db_session, user, models.Movie, title)
    # Kept in September and ticked off in the library before the home screen closed the card.
    db_session.add(models.BacklogDraw(user_id=user.id, category="movies", item_id=film.id, status=backlog_draw.ACTIVE,
                                      picked_at=datetime(2027, 9, 20, 19, 0), created_at=datetime(2027, 9, 20, 19, 0)))
    film.watched = True
    db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=film.id, title="Dune",
                                        action="completed", occurred_at=datetime(2027, 9, 28, 21, 0)))
    db_session.commit()
    step = challenges.progress(db_session, user.id, "2027-10")[1]
    assert step["kind"] == "draw" and step["done"] is False
    # Nothing to finish on that card: the step offers a fresh deal instead.
    assert step["card"] is None and step["ready"] is True


def test_a_kept_card_still_waiting_is_offered_as_before(db_session):
    user = _member(db_session, "stillkept")
    film = _row(db_session, user, models.Movie, "Death Becomes Her")
    db_session.add(models.BacklogDraw(user_id=user.id, category="movies", item_id=film.id, status=backlog_draw.ACTIVE,
                                      picked_at=OCTOBER, created_at=OCTOBER, night=date(2027, 10, 15)))
    db_session.commit()
    step = challenges.progress(db_session, user.id, "2027-10")[1]
    assert step["card"] == {"title": "Death Becomes Her", "category": "movies", "night": "2027-10-15"}


def test_the_draw_card_brings_itself_out_from_behind_show_more():
    draw = (STATIC / "backlog-draw.js").read_text(encoding="utf-8")
    show = draw[draw.index("function show() {"):draw.index("function wire() {")]
    assert show.index("layout.reveal(section)") < show.index("section.scrollIntoView(")
    layout = (STATIC / "home-layout.js").read_text(encoding="utf-8")
    assert "reveal: revealFor" in layout
    assert "/static/backlog-draw.js?v=20261121-sweep-f-1" in INDEX
    assert "/static/home-layout.js?v=20261127-home-refresh-1" in INDEX


# ---------------------------------------------------------------- #293 length limits (checked, unchanged)


def test_a_legacy_long_title_and_review_save_from_the_dashboard_and_finish_in_october(authenticated_client, db_session):
    me = _user(db_session)
    long_title, long_review = "Old " + "t" * 900, "Old review. " * 3000
    row = _row(db_session, me, models.Book, long_title, author="A", year=1979, review=long_review)
    # The dashboard sends every field back on save, and an edit that only marks it read must go through.
    saved = authenticated_client.put(f"/books/{row.id}", json={"title": long_title, "author": "A", "year": 1979,
                                                               "review": long_review, "read": True})
    assert saved.status_code == 200, saved.text
    db_session.refresh(row)
    assert (row.title, row.review, row.read) == (long_title, long_review, True)


def test_the_changelog_says_what_this_sweep_fixed():
    assert 'id="security-nov21f-2026-heading"' in CHANGELOG
    assert CHANGELOG.index("security-nov21f-2026") < CHANGELOG.index("security-nov21e-2026")
