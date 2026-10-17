"""Friend invite links: share a /join link; friends who sign up or accept through it become friends."""
from app import auth, email as email_utils, friend_invites, models
from tests.test_title_pages import member

PASSWORD = "tea on the porch"


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _link(client):
    response = client.post("/api/friends/invite-link")
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["url"].startswith("https://omnitrackr.xyz/join/")
    return data, data["url"].rsplit("/", 1)[1]


def _sign_out(client):
    client.headers = {}
    client.cookies.clear()


def _as(client, user):
    _sign_out(client)
    token = auth.create_user_access_token(user)
    client.headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set(auth.AUTH_COOKIE_NAME, token)


def _friends(db, a, b):
    return friend_invites.are_friends(db, a.id, b.id)


def test_link_is_reusable_and_can_be_reset(authenticated_client, db_session):
    data, token = _link(authenticated_client)
    assert "We'll be friends as soon as you sign up." in data["text"]
    assert _link(authenticated_client)[1] == token
    fresh = authenticated_client.post("/api/friends/invite-link", json={"reset": True}).json()["url"].rsplit("/", 1)[1]
    assert fresh != token and friend_invites.inviter_for(db_session, token) is None
    assert friend_invites.inviter_for(db_session, fresh).username == "testuser"


def test_join_page_for_visitors(authenticated_client, db_session):
    _, token = _link(authenticated_client)
    _sign_out(authenticated_client)
    page = authenticated_client.get(f"/join/{token}")
    assert page.status_code == 200
    assert "testuser invited you to OmniTrackr" in page.text
    assert f'href="/?invite={token}#signup"' in page.text and 'href="/#signup"' not in page.text
    assert f'href="/?next=%2Fjoin%2F{token}#landing-auth"' in page.text
    assert "data-join-accept" not in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow" and page.headers["cache-control"] == "private, no-store"
    for bad in ("short", "x" * 20, token + "!"):
        assert authenticated_client.get(f"/join/{bad}").status_code == 404


def test_signup_through_the_link_makes_friends_after_verification(authenticated_client, db_session):
    _, token = _link(authenticated_client)
    inviter = _me(db_session)
    _sign_out(authenticated_client)
    response = authenticated_client.post("/auth/register", json={
        "email": "newfan@example.com", "username": "newfan", "password": PASSWORD, "invite": token})
    assert response.status_code == 201
    newfan = db_session.query(models.User).filter_by(username="newfan").one()
    assert not _friends(db_session, inviter, newfan)  # not until the email is verified

    verify = newfan.verification_token
    assert authenticated_client.get(f"/auth/verify-email?token={verify}").status_code == 200
    assert _friends(db_session, inviter, newfan)
    note = db_session.query(models.Notification).filter_by(user_id=inviter.id, type="friend_invite_accepted").one()
    assert note.message == "newfan joined OmniTrackr from your invite. You're now friends."
    # Verifying again (or a second visit) changes nothing.
    friend_invites.complete_signup(db_session, newfan)
    assert db_session.query(models.Friendship).count() == 1


def test_bad_or_missing_invites_never_block_signup(client, db_session):
    for index, invite in enumerate(("not a token!", "x" * 20, None)):
        body = {"email": f"fan{index}@example.com", "username": f"fan{index}", "password": PASSWORD}
        if invite is not None:
            body["invite"] = invite
        assert client.post("/auth/register", json=body).status_code == 201
    assert db_session.query(models.FriendInviteSignup).count() == 0
    assert client.post("/auth/register", json={"email": "long@example.com", "username": "longinvite",
                                                "password": PASSWORD, "invite": "x" * 65}).status_code == 422


def test_existing_member_accepts_with_one_click(authenticated_client, db_session):
    _, token = _link(authenticated_client)
    inviter = _me(db_session)
    pal = member(db_session, "pal")
    db_session.add(models.FriendRequest(sender_id=inviter.id, receiver_id=pal.id, status="pending"))
    db_session.commit()
    assert authenticated_client.post(f"/api/friends/invite/{token}/accept").status_code == 400  # own link

    _as(authenticated_client, pal)
    page = authenticated_client.get(f"/join/{token}").text
    assert f'data-join-accept data-token="{token}">Add testuser as a friend</button>' in page
    assert '<script src="/static/join.js?v=' in page
    first = authenticated_client.post(f"/api/friends/invite/{token}/accept").json()
    assert first == {"friend": "testuser", "added": True} and _friends(db_session, inviter, pal)
    assert db_session.query(models.FriendRequest).one().status == "accepted"  # the old request is closed
    assert authenticated_client.post(f"/api/friends/invite/{token}/accept").json()["added"] is False
    assert authenticated_client.post("/api/friends/invite/" + "y" * 22 + "/accept").status_code == 404


def test_deactivated_inviters_links_stop_working(authenticated_client, db_session):
    _, token = _link(authenticated_client)
    me = _me(db_session)
    me.is_active = False
    db_session.commit()
    assert friend_invites.inviter_for(db_session, token) is None


def test_requires_login(client):
    assert client.post("/api/friends/invite-link").status_code == 401
    assert client.post("/api/friends/invite/" + "y" * 22 + "/accept").status_code == 401


# ---------------------------------------------------------------- spreading the word

def _brought(db, inviter, *names, completed=True, active=True):
    from datetime import datetime
    for name in names:
        friend = member(db, name)
        friend.is_active = active
        db.add(models.FriendInviteSignup(inviter_id=inviter.id, invitee_id=friend.id,
                                         completed_at=datetime.utcnow() if completed else None))
    db.commit()


def test_profile_shows_how_many_friends_joined(client, db_session):
    from tests.test_public_profiles import enable, library, member as profile_member
    host = profile_member(db_session, "host")
    library(db_session, host)
    enable(db_session, host, show_stats=True)
    assert "Brought" not in client.get("/u/host").text
    _brought(db_session, host, "one", "two")
    _brought(db_session, host, "pending", completed=False)
    _brought(db_session, host, "gone", active=False)
    assert '<span class="site-chip">Brought 2 friends to OmniTrackr</span>' in client.get("/u/host").text
    db_session.query(models.PublicProfile).filter_by(user_id=host.id).update({"show_stats": False})
    db_session.commit()
    assert "Brought" not in client.get("/u/host").text  # follows the member's "Library counts" choice


def test_weekly_email_invite_nudge(db_session):
    from datetime import datetime
    from app import digest
    report = {"matches": [{"title": "Severance", "label": "TV", "date": "2026-10-02", "url": "/release-radar/tv", "reason": "x"}],
              "popular": []}
    _, html, text = digest.build_digest("reader", report, "u", None, None, True)
    assert "Better with a friend" in html and "/#invite-friends" in html and "/#invite-friends" in text
    ask = {"title": "Heat", "path": "/titles/movie/heat-1995"}
    _, html, _ = digest.build_digest("reader", report, "u", None, ask, True)
    assert "Better with a friend" not in html  # one social ask per email
    assert digest.build_digest("reader", {"matches": [], "popular": []}, "u", None, None, True) is None  # never forces a send
    weeks = [digest.invite_nudge_due(7, datetime(2026, 1, 5) + __import__("datetime").timedelta(weeks=w)) for w in range(12)]
    assert weeks.count(True) == 3  # about once a month


def test_has_friends(db_session):
    a, b = member(db_session, "a"), member(db_session, "b")
    db_session.commit()
    assert not friend_invites.has_friends(db_session, a.id)
    db_session.add(models.Friendship(user1_id=a.id, user2_id=b.id))
    db_session.commit()
    assert friend_invites.has_friends(db_session, a.id) and friend_invites.has_friends(db_session, b.id)
