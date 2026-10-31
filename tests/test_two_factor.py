"""Two-factor sign-in: setup, the code step at login, recovery codes, Google, and turning it off."""
import time

import pytest

from app import auth, models, two_factor

from .test_google_signin import _sign_in, google  # noqa: F401  (fixture)


def _secret_from(setup_json):
    return setup_json["secret"].replace(" ", "")


def _code(secret, offset_steps=0):
    return two_factor.code_at(secret, two_factor.current_step() + offset_steps)


def _turn_on(client, password="testpassword123"):
    setup = client.post("/account/two-factor/setup", json={"password": password})
    assert setup.status_code == 200, setup.text
    secret = _secret_from(setup.json())
    enabled = client.post("/account/two-factor/enable", json={"code": _code(secret)})
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["recovery_codes"]


def _log_in(client, username="testuser", password="testpassword123"):
    client.headers = {}
    client.cookies.clear()
    return client.post("/auth/login", data={"username": username, "password": password})


def _row(db_session):
    return db_session.query(models.UserTwoFactor).one()


# ---------------------------------------------------------------- the code math

def test_codes_match_the_rfc_6238_test_vector():
    # RFC 6238 appendix B, SHA-1, T = 59 seconds: 94287082 (last six digits shown by apps).
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert two_factor.code_at(secret, 59 // 30) == "287082"
    assert two_factor.matching_step(secret, "287082", now=59) == 1
    assert two_factor.matching_step(secret, "287082", last_used_step=1, now=59) is None


def test_recovery_codes_forgive_case_dashes_and_lookalikes():
    assert two_factor.normalize_code(" ABCDE-FGH0I ") == "abcdefgh01"
    assert two_factor.normalize_code("o0lI1") == "00111"


def test_secret_is_stored_encrypted(authenticated_client, db_session):
    secret, _ = _turn_on(authenticated_client)
    stored = _row(db_session).secret_encrypted
    assert secret not in stored
    assert two_factor.decrypt_secret(stored) == secret


# ---------------------------------------------------------------- settings

def test_members_start_with_it_off(authenticated_client):
    status = authenticated_client.get("/account/two-factor").json()
    assert status == {"enabled": False, "enabled_at": None, "recovery_codes_left": 0, "has_password": True}


def test_setup_needs_the_password(authenticated_client, db_session):
    response = authenticated_client.post("/account/two-factor/setup", json={"password": "wrong"})
    assert response.status_code == 400
    assert db_session.query(models.UserTwoFactor).count() == 0


def test_setup_returns_a_qr_code_and_stays_off_until_confirmed(authenticated_client, db_session):
    setup = authenticated_client.post("/account/two-factor/setup", json={"password": "testpassword123"}).json()
    assert setup["qr_code"].startswith("data:image/svg+xml;base64,")
    assert setup["otpauth_uri"].startswith("otpauth://totp/OmniTrackr%3Atest%40example.com?secret=")
    assert authenticated_client.get("/account/two-factor").json()["enabled"] is False
    # An unconfirmed setup doesn't change how this member logs in.
    assert "access_token" in _log_in(authenticated_client).json()


def test_wrong_confirmation_code_leaves_it_off(authenticated_client):
    authenticated_client.post("/account/two-factor/setup", json={"password": "testpassword123"})
    response = authenticated_client.post("/account/two-factor/enable", json={"code": "000000"})
    assert response.status_code == 400
    assert authenticated_client.get("/account/two-factor").json()["enabled"] is False


def test_turning_it_on_gives_ten_recovery_codes(authenticated_client):
    _, codes = _turn_on(authenticated_client)
    assert len(codes) == 10 and len(set(codes)) == 10
    status = authenticated_client.get("/account/two-factor").json()
    assert status["enabled"] is True and status["recovery_codes_left"] == 10
    # A second setup can't quietly replace the secret.
    again = authenticated_client.post("/account/two-factor/setup", json={"password": "testpassword123"})
    assert again.status_code == 400


# ---------------------------------------------------------------- logging in

def test_password_alone_no_longer_opens_the_session(authenticated_client):
    _turn_on(authenticated_client)
    response = _log_in(authenticated_client)
    assert response.status_code == 200
    assert response.json() == {"two_factor_required": True}
    assert auth.AUTH_COOKIE_NAME not in response.cookies
    assert authenticated_client.get("/account/me").status_code == 401


def test_code_step_finishes_the_login(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    # The code from enabling was used; wait out its step by using the next one.
    response = authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["username"] == "testuser" and body["access_token"]
    assert authenticated_client.get("/account/me").status_code == 200


def test_a_code_works_only_once(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    code = _code(secret, 1)
    assert authenticated_client.post("/auth/login/two-factor", json={"code": code}).status_code == 200
    _log_in(authenticated_client)
    assert authenticated_client.post("/auth/login/two-factor", json={"code": code}).status_code == 401


def test_code_step_needs_the_password_step_first(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    response = authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1)})
    assert response.status_code == 401


def test_tampered_challenge_is_refused(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    value = authenticated_client.cookies.get(two_factor.CHALLENGE_COOKIE)
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set(two_factor.CHALLENGE_COOKIE, value[:-2] + "xx", path="/auth")
    response = authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1)})
    assert response.status_code == 401


def test_five_wrong_codes_pause_sign_in(authenticated_client, db_session):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    for _ in range(5):
        assert authenticated_client.post("/auth/login/two-factor", json={"code": "000000"}).status_code == 401
    locked = authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1)})
    assert locked.status_code == 423


def test_recovery_code_gets_in_once(authenticated_client):
    _, codes = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    response = authenticated_client.post("/auth/login/two-factor", json={"code": codes[0].upper()})
    assert response.status_code == 200
    assert response.json()["recovery_codes_left"] == 9
    _log_in(authenticated_client)
    assert authenticated_client.post("/auth/login/two-factor", json={"code": codes[0]}).status_code == 401


def test_remembered_browser_skips_the_code(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1), "remember_device": True})
    device = authenticated_client.cookies.get(two_factor.DEVICE_COOKIE)
    assert device
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set(two_factor.DEVICE_COOKIE, device, path="/auth")
    response = authenticated_client.post("/auth/login", data={"username": "testuser", "password": "testpassword123"})
    assert "access_token" in response.json()

    # "Ask on every browser again" forgets it.
    assert authenticated_client.post("/account/two-factor/forget-browsers").status_code == 200
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set(two_factor.DEVICE_COOKIE, device, path="/auth")
    response = authenticated_client.post("/auth/login", data={"username": "testuser", "password": "testpassword123"})
    assert response.json() == {"two_factor_required": True}


def test_remembered_browser_is_forgotten_after_a_password_reset(authenticated_client, db_session):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1), "remember_device": True})
    device = authenticated_client.cookies.get(two_factor.DEVICE_COOKIE)
    user = db_session.query(models.User).filter_by(username="testuser").one()
    user.hashed_password = auth.get_password_hash("a-brand-new-password")
    db_session.commit()
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set(two_factor.DEVICE_COOKIE, device, path="/auth")
    response = authenticated_client.post("/auth/login", data={"username": "testuser", "password": "a-brand-new-password"})
    assert response.json() == {"two_factor_required": True}


def test_password_reset_still_works_and_keeps_two_factor(authenticated_client, db_session, monkeypatch):
    from app import email as email_utils
    _turn_on(authenticated_client)
    sent = {}

    async def capture(email, username, token):
        sent["token"] = token

    monkeypatch.setattr(email_utils, "send_password_reset_email", capture)
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    authenticated_client.post("/auth/request-password-reset?email=test@example.com")
    reset = authenticated_client.post("/auth/reset-password",
                                      json={"token": sent["token"], "new_password": "another-good-password"})
    assert reset.status_code == 200
    response = _log_in(authenticated_client, password="another-good-password")
    assert response.json() == {"two_factor_required": True}


def test_members_without_two_factor_log_in_as_before(authenticated_client):
    response = _log_in(authenticated_client)
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert two_factor.CHALLENGE_COOKIE not in response.cookies


# ---------------------------------------------------------------- Google

def test_google_sign_in_asks_for_the_code_too(client, google, db_session, test_user_data):  # noqa: F811
    client.post("/auth/register", json=test_user_data)
    user = db_session.query(models.User).filter_by(username="testuser").one()
    user.is_verified = True
    db_session.commit()
    login = client.post("/auth/login", data={"username": "testuser", "password": "testpassword123"})
    client.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    secret, _ = _turn_on(client)
    client.headers = {}
    client.cookies.clear()

    response = _sign_in(client, google, email="test@example.com", sub="2002")
    assert response.status_code == 303
    assert response.headers["location"] == "/?two_factor=1#landing-auth"
    assert auth.AUTH_COOKIE_NAME not in response.cookies
    assert client.get("/account/me").status_code == 401

    finished = client.post("/auth/login/two-factor", json={"code": _code(secret, 1)})
    assert finished.status_code == 200
    assert client.get("/account/me").json()["username"] == "testuser"


def test_google_members_without_two_factor_are_unchanged(client, google, db_session):  # noqa: F811
    response = _sign_in(client, google)
    assert response.headers["location"].startswith("/?signed_in=google")
    assert auth.AUTH_COOKIE_NAME in response.cookies


def test_google_only_members_can_turn_it_on_without_a_password(client, google, db_session):  # noqa: F811
    _sign_in(client, google)
    status = client.get("/account/two-factor").json()
    assert status["has_password"] is False
    setup = client.post("/account/two-factor/setup", json={"password": ""})
    assert setup.status_code == 200
    secret = _secret_from(setup.json())
    assert client.post("/account/two-factor/enable", json={"code": _code(secret)}).status_code == 200


# ---------------------------------------------------------------- managing it

def test_new_recovery_codes_replace_the_old_ones(authenticated_client):
    secret, old = _turn_on(authenticated_client)
    response = authenticated_client.post("/account/two-factor/recovery-codes",
                                         json={"code": _code(secret, 1), "password": "testpassword123"})
    assert response.status_code == 200
    new = response.json()["recovery_codes"]
    assert not set(new) & set(old)
    _log_in(authenticated_client)
    assert authenticated_client.post("/auth/login/two-factor", json={"code": old[1]}).status_code == 401
    assert authenticated_client.post("/auth/login/two-factor", json={"code": new[1]}).status_code == 200


def test_turning_it_off_needs_password_and_code(authenticated_client, db_session):
    secret, codes = _turn_on(authenticated_client)
    wrong_password = authenticated_client.post("/account/two-factor/disable",
                                               json={"code": _code(secret, 1), "password": "nope"})
    assert wrong_password.status_code == 400
    wrong_code = authenticated_client.post("/account/two-factor/disable",
                                           json={"code": "123456", "password": "testpassword123"})
    assert wrong_code.status_code == 400
    # A recovery code works here too, for a member who lost their phone but is still signed in.
    off = authenticated_client.post("/account/two-factor/disable",
                                    json={"code": codes[2], "password": "testpassword123"})
    assert off.status_code == 200 and off.json()["enabled"] is False
    assert db_session.query(models.UserTwoFactor).count() == 0
    assert "access_token" in _log_in(authenticated_client).json()


def test_settings_page_has_the_two_factor_section(authenticated_client):
    page = authenticated_client.get("/").text
    assert 'id="twoFactorSection"' in page


def test_a_right_password_does_not_reset_wrong_code_count(authenticated_client, db_session):
    secret, _ = _turn_on(authenticated_client)
    _log_in(authenticated_client)
    for _ in range(4):
        authenticated_client.post("/auth/login/two-factor", json={"code": "000000"})
    # Logging in again with the password must not hand out four more guesses.
    _log_in(authenticated_client)
    assert authenticated_client.post("/auth/login/two-factor", json={"code": "000000"}).status_code == 401
    locked = _log_in(authenticated_client)
    assert locked.status_code == 423
    assert authenticated_client.post("/auth/login/two-factor", json={"code": _code(secret, 1)}).status_code == 401


def test_reactivate_does_not_reset_wrong_code_count(authenticated_client, db_session):
    _turn_on(authenticated_client)
    _log_in(authenticated_client)
    for _ in range(3):
        authenticated_client.post("/auth/login/two-factor", json={"code": "000000"})
    authenticated_client.post("/auth/reactivate", json={"username": "testuser", "password": "testpassword123"})
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.refresh(user)
    assert user.failed_login_attempts == 3
