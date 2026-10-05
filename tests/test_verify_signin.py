"""Opening the verification link in the browser that signed up signs the member straight in (Oct 2026)."""
from app import auth, email as email_utils, models


def register(client, username="newfan", email="newfan@example.com", password="tea on the porch"):
    return client.post("/auth/register", json={"email": email, "username": username, "password": password})


def token_for(db, username="newfan"):
    user = db.query(models.User).filter_by(username=username).one()
    return user, email_utils.generate_verification_token(user.email)


def test_register_marks_this_browser_with_a_signed_httponly_cookie(client, db_session):
    response = register(client)
    assert response.status_code == 201
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith(auth.PENDING_SIGNUP_COOKIE))
    assert "HttpOnly" in header and "Path=/auth" in header and "samesite=lax" in header.lower()
    assert "newfan" not in header and "@" not in header  # carries a signed id, not personal data
    user, _ = token_for(db_session)
    assert auth.pending_signup_user_id(client.cookies.get(auth.PENDING_SIGNUP_COOKIE)) == user.id


def test_same_browser_verification_signs_in(client, db_session):
    register(client)
    user, token = token_for(db_session)
    response = client.get(f"/auth/verify-email?token={token}")
    assert response.status_code == 200
    body = response.json()
    assert body["signed_in"] is True and body["user"]["username"] == "newfan"
    assert "hashed_password" not in body["user"]
    assert response.headers["cache-control"].startswith("no-store")
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{auth.AUTH_COOKIE_NAME}=") and "HttpOnly" in c for c in cookies)
    assert any(c.startswith(f"{auth.PENDING_SIGNUP_COOKIE}=") and "Max-Age=0" in c for c in cookies)
    db_session.refresh(user)
    assert user.is_verified and user.login_count == 1 and user.last_login_at is not None
    assert client.get("/account/me").status_code == 200


def test_other_browser_gets_the_login_form_with_email_filled(client, db_session):
    register(client)
    client.cookies.clear()  # e.g. the mail app's built-in browser
    user, token = token_for(db_session)
    body = client.get(f"/auth/verify-email?token={token}").json()
    assert body["signed_in"] is False and body["login_hint"] == "newfan@example.com"
    assert client.get("/account/me").status_code == 401
    db_session.refresh(user)
    assert user.is_verified and not user.login_count


def test_cookie_for_another_account_does_not_sign_in(client, db_session):
    register(client)  # this browser created "newfan"
    register(client, username="second", email="second@example.com")  # now marked for "second"
    _, token = token_for(db_session, "newfan")
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is False


def test_tampered_or_forged_cookie_is_ignored(client, db_session):
    register(client)
    user, token = token_for(db_session)
    client.cookies.set(auth.PENDING_SIGNUP_COOKIE, '{"uid": %d}' % user.id, path="/auth")
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is False
    for bad in (None, "", "x" * 600, "garbage.value"):
        assert auth.pending_signup_user_id(bad) is None


def test_reusing_the_link_never_signs_in_again(client, db_session):
    register(client)
    _, token = token_for(db_session)
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is True
    client.post("/auth/logout")
    again = client.get(f"/auth/verify-email?token={token}").json()
    assert again == {"message": "Email already verified"}
    assert client.get("/account/me").status_code == 401


def test_deactivated_account_is_not_signed_in(client, db_session):
    register(client)
    user, token = token_for(db_session)
    user.is_active = False
    db_session.commit()
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is False


def test_bad_tokens_still_fail_even_with_the_cookie(client):
    register(client)
    assert client.get("/auth/verify-email?token=not-a-token").status_code == 400
    assert client.get("/account/me").status_code == 401
