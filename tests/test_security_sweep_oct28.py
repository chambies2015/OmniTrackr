"""Fixes from the October 28 security and privacy sweep."""
from app import auth, models


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", is_active=True, is_verified=True,
                       hashed_password=auth.get_password_hash("testpassword123"), **extra)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_friend_requests_and_password_resets_are_rate_limited():
    from app.main import limiter
    limited = set(limiter._route_limits)
    for name in ("app.routers.friends.send_friend_request", "app.routers.auth.reset_password"):
        assert name in limited, name


def test_friend_requests_still_send(client, db_session):
    sender = member(db_session, "requester")
    member(db_session, "receiver")
    client.headers = {"Authorization": f"Bearer {auth.create_user_access_token(sender)}"}
    response = client.post("/friends/request", json={"receiver_username": "receiver"})
    assert response.status_code in (200, 201), response.text


def test_podcast_discussion_board_opens(client, db_session):
    host = member(db_session, "listener")
    db_session.add(models.Podcast(user_id=host.id, title="Night Signals", year=2024, listened=True))
    db_session.commit()
    board = client.get("/titles/podcast/night-signals-2024/discussions")
    assert board.status_code == 200, board.text
    assert ">Podcasts</a>" in board.text


def test_deleting_an_opening_post_removes_its_text(client, db_session, monkeypatch):
    from app import title_discussions
    from tests.test_shared_lists import _as
    from tests.test_title_discussions import API, _reply, _setup

    monkeypatch.setattr(title_discussions, "POST_GAP_SECONDS", 0)
    alice, bob = _setup(db_session)
    _as(client, alice)
    opener = "Plinthwax theory: the whole ending is a dream and the docking scene proves it."
    started = client.post(API, json={"subject": "Ending theory", "body": opener, "spoiler": False}).json()
    _as(client, bob)
    assert _reply(client, started["id"], "I'm not sure, but the organ music fits.").status_code == 201
    _as(client, alice)
    assert client.delete(f"/api/discussions/{started['id']}").json()["state"] == "cleared"
    thread = db_session.get(models.TitleDiscussion, started["id"])
    db_session.refresh(thread)
    assert thread.body == ""

    # Threads deleted before this fix still have their text stored: it must not reach the page.
    thread.body = opener
    db_session.commit()
    _as(client, None)
    page = client.get(started["url"])
    assert page.status_code == 200
    assert "Plinthwax" not in page.text
    assert "the organ music fits" in page.text
