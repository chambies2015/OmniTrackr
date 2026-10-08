"""Sessions are tied to the account id, so renaming an account is safe.

Before this, a session token only named the username. Renaming an account
signed it out everywhere, and for the rest of the token's life anyone who
registered the old username would be signed in by the old token.
"""


from app import auth, crud, models, schemas


def _register(client, db_session, username, email):
    response = client.post("/auth/register", json={"email": email, "username": username, "password": "password123"})
    assert response.status_code == 201
    user = crud.get_user_by_id(db_session, response.json()["id"])
    user.is_verified = True
    db_session.commit()
    return user


def _token(client, username):
    response = client.post("/auth/login", data={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _me(client, token):
    return client.get("/account/me", headers={"Authorization": f"Bearer {token}"})


def test_login_tokens_carry_the_account_id(client, db_session):
    user = _register(client, db_session, "idcarrier", "idcarrier@example.com")
    payload = auth.decode_access_token(_token(client, "idcarrier"))
    assert payload["uid"] == user.id
    assert payload["sub"] == "idcarrier"


def test_renaming_keeps_the_member_signed_in(client, db_session):
    _register(client, db_session, "oldname", "oldname@example.com")
    token = _token(client, "oldname")
    response = client.put(
        "/account/username",
        json={"new_username": "newname", "password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "newname"
    assert auth.AUTH_COOKIE_NAME in response.headers.get("set-cookie", "")
    refreshed = auth.decode_access_token(response.cookies.get(auth.AUTH_COOKIE_NAME))
    assert refreshed["sub"] == "newname"

    me = _me(client, token)  # the token issued before the rename
    assert me.status_code == 200
    assert me.json()["username"] == "newname"


def test_old_token_never_signs_in_as_whoever_takes_the_old_name(client, db_session):
    original = _register(client, db_session, "dan", "dan@example.com")
    token = _token(client, "dan")
    assert client.put(
        "/account/username",
        json={"new_username": "dan_renamed", "password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200
    newcomer = _register(client, db_session, "dan", "newcomer@example.com")
    assert newcomer.id != original.id

    me = _me(client, token)
    assert me.status_code == 200
    assert me.json()["id"] == original.id
    assert me.json()["username"] == "dan_renamed"


def test_tokens_issued_before_the_update_still_work(client, db_session):
    user = _register(client, db_session, "legacyuser", "legacy@example.com")
    legacy = auth.create_access_token(data={"sub": "legacyuser"})
    me = _me(client, legacy)
    assert me.status_code == 200 and me.json()["id"] == user.id


def test_malformed_ids_are_rejected(client, db_session):
    _register(client, db_session, "shapecheck", "shape@example.com")
    for uid in (True, "1", 999999):
        token = auth.create_access_token(data={"sub": "shapecheck", "uid": uid})
        if uid == 999999:
            assert _me(client, token).status_code == 401
        else:
            # Non-integer ids are ignored and the legacy username path applies.
            assert _me(client, token).status_code == 200
    assert _me(client, auth.create_access_token(data={"other": 1})).status_code == 401


def test_deactivated_accounts_are_refused_by_id(client, db_session):
    user = _register(client, db_session, "goingaway", "away@example.com")
    token = _token(client, "goingaway")
    user.is_active = False
    db_session.commit()
    assert _me(client, token).status_code == 401


def test_site_stats_admin_follows_the_current_username(client, db_session, monkeypatch):
    monkeypatch.delenv("COLLECTION_MODERATOR_USERNAMES", raising=False)
    monkeypatch.setenv("ADMIN_USERNAMES", "owner_now")
    _register(client, db_session, "owner_before", "owner@example.com")
    token = _token(client, "owner_before")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/site-stats/access", headers=headers).json() == {"admin": False}
    client.put("/account/username", json={"new_username": "owner_now", "password": "password123"}, headers=headers)
    assert client.get("/api/site-stats/access", headers=headers).json() == {"admin": True}
    assert client.get("/api/site-stats/overview", headers=headers).status_code == 200


def test_rename_page_no_longer_forces_a_logout():
    from app import dashboard_assets
    app_js = dashboard_assets.full_source()
    start = app_js.index("window.changeUsername = async function")
    body = app_js[start:app_js.index("\n};", start)]
    assert "clearAuth()" not in body
    assert "localStorage.setItem('omnitrackr_user', JSON.stringify(updatedUser))" in body


# ---------------------------------------------------------------- 30-day sessions

def test_sessions_last_thirty_days(client, db_session):
    from datetime import datetime, timezone
    _register(client, db_session, "longstay", "longstay@example.com")
    response = client.post("/auth/login", data={"username": "longstay", "password": "password123"})
    payload = auth.decode_access_token(response.json()["access_token"])
    lifetime = payload["exp"] - datetime.now(timezone.utc).timestamp()
    assert 29 * 86400 < lifetime <= 30 * 86400 + 5
    cookie = response.headers["set-cookie"]
    assert f"Max-Age={30 * 24 * 60 * 60}" in cookie
    assert "HttpOnly" in cookie


def test_password_change_signs_out_other_sessions_but_keeps_this_one(client, db_session):
    _register(client, db_session, "rotator", "rotator@example.com")
    other_device = _token(client, "rotator")
    this_device = _token(client, "rotator")
    response = client.put(
        "/account/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
        headers={"Authorization": f"Bearer {this_device}"},
    )
    assert response.status_code == 200
    fresh = response.cookies.get(auth.AUTH_COOKIE_NAME)
    assert fresh
    assert _me(client, other_device).status_code == 401
    assert _me(client, this_device).status_code == 401  # the pre-change token is retired too
    assert _me(client, fresh).status_code == 200


def test_password_reset_signs_out_every_session(client, db_session):
    user = _register(client, db_session, "resetme", "resetme@example.com")
    token = _token(client, "resetme")
    user.hashed_password = auth.get_password_hash("brandnew789")
    db_session.commit()
    assert _me(client, token).status_code == 401


def test_session_tokens_do_not_expose_the_password_hash(client, db_session):
    user = _register(client, db_session, "opaque", "opaque@example.com")
    payload = auth.decode_access_token(_token(client, "opaque"))
    assert len(payload["pv"]) == 16
    assert payload["pv"] not in user.hashed_password
