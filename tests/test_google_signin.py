"""Sign in with Google: hidden until configured, then new, linked and returning accounts."""
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from app import auth, funnel, google_signin, models

CLIENT_ID = "test-client.apps.googleusercontent.com"


@pytest.fixture
def google(monkeypatch):
    """Configure Google sign-in and answer the code exchange with a crafted ID token."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://omnitrackr.xyz/auth/google/callback")
    answer = {"claims": {}}

    async def fake_exchange(code, http_client=None, return_to=None):
        assert code == "good-code"
        answer["return_to"] = return_to
        return jwt.encode(answer["claims"], "not-checked", algorithm="HS256")

    monkeypatch.setattr(google_signin, "exchange_code", fake_exchange)
    return answer


def _start(client, invite=None):
    url = "/auth/google/start" + (f"?invite={invite}" if invite else "")
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    return response, query["state"][0], query["nonce"][0]


def _claims(expected_nonce, **overrides):
    claims = {
        "iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1001",
        "email": "newfan@gmail.com", "email_verified": True, "given_name": "Riley",
        "nonce": expected_nonce, "exp": int(time.time()) + 600,
    }
    claims.update(overrides)
    return claims


def _sign_in(client, google, invite=None, **overrides):
    _, state, nonce = _start(client, invite)
    google["claims"] = _claims(nonce, **overrides)
    return client.get(f"/auth/google/callback?code=good-code&state={state}", follow_redirects=False)


def _user(db, email):
    return db.query(models.User).filter(models.User.email == email).one()


def test_button_is_hidden_until_configured(client):
    page = client.get("/").text
    assert "data-google-signin" not in page and "GOOGLE_SIGNIN" not in page
    response = client.get("/auth/google/start", follow_redirects=False)
    assert response.headers["location"] == "/?google_error=unavailable#landing-auth"


def test_button_shows_on_both_forms_once_configured(client, google):
    page = client.get("/").text
    # The log-in form, the sign-up form, the homepage hero and the save bar.
    assert page.count('href="/auth/google/start"') == 4
    # Every sign-up button (not the log-in one) counts as starting to sign up.
    assert page.count("data-google-signup") == 3
    assert "Sign up with Google" in page and "Log in with Google" in page


def test_hero_offers_google_and_email_sign_up_once_configured(client, google):
    page = client.get("/").text
    assert "HERO_SIGNUP" not in page
    assert "Continue with Google" in page and "Sign up with email" in page
    assert 'href="/auth/google/start" rel="nofollow" data-google-signin data-google-signup data-hero-signup' in page
    assert 'href="/demo"' in page


def test_hero_keeps_the_email_button_without_google(client):
    page = client.get("/").text
    assert "HERO_SIGNUP" not in page and "Continue with Google" not in page
    assert "Create a free library" in page and 'data-action="show-register-form" data-hero-signup' in page


def test_start_sends_visitor_to_google_with_a_signed_state(client, google):
    response, state, nonce = _start(client)
    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert location.netloc == "accounts.google.com"
    assert query["client_id"] == [CLIENT_ID] and query["scope"] == ["openid email profile"]
    assert query["redirect_uri"] == ["https://omnitrackr.xyz/auth/google/callback"]
    cookie = response.headers["set-cookie"]
    assert google_signin.STATE_COOKIE in cookie and "HttpOnly" in cookie and "Path=/auth/google" in cookie
    assert state and nonce and state != nonce


def test_new_member_is_created_verified_and_signed_in(client, google, db_session):
    response = _sign_in(client, google)
    assert response.status_code == 303
    assert response.headers["location"] == "/?signed_in=google&new=1"
    assert auth.AUTH_COOKIE_NAME in response.headers.get("set-cookie", "")
    user = _user(db_session, "newfan@gmail.com")
    assert user.is_verified and user.google_sub == "1001" and user.username == "Riley"
    assert user.password_set is False and user.has_password is False and user.login_count == 1
    me = client.get("/account/me")
    assert me.status_code == 200 and me.json()["username"] == "Riley" and me.json()["has_password"] is False
    assert "google_sub" not in me.json()


def test_returning_member_signs_in_by_google_id(client, google, db_session):
    _sign_in(client, google)
    client.cookies.clear()
    response = _sign_in(client, google, email="renamed@gmail.com")
    assert response.headers["location"] == "/?signed_in=google"
    assert db_session.query(models.User).count() == 1
    assert _user(db_session, "newfan@gmail.com").login_count == 2


def test_existing_verified_member_is_linked_and_keeps_their_password(client, google, db_session, test_user_data):
    assert client.post("/auth/register", json=test_user_data).status_code == 201
    user = _user(db_session, "test@example.com")
    user.is_verified = True
    db_session.commit()
    original = user.hashed_password
    response = _sign_in(client, google, email="Test@Example.com", sub="2002")
    assert response.headers["location"] == "/?signed_in=google"
    db_session.refresh(user)
    assert user.google_sub == "2002" and user.hashed_password == original and user.has_password
    assert db_session.query(models.User).count() == 1
    login = client.post("/auth/login", data={"username": "testuser", "password": test_user_data["password"]})
    assert login.status_code == 200


def test_unverified_account_is_claimed_by_the_inbox_owner(client, google, db_session, test_user_data):
    assert client.post("/auth/register", json=test_user_data).status_code == 201
    user = _user(db_session, "test@example.com")
    original = user.hashed_password
    _sign_in(client, google, email="test@example.com", sub="3003")
    db_session.refresh(user)
    assert user.is_verified and user.verification_token is None
    assert user.hashed_password != original and user.has_password is False
    login = client.post("/auth/login", data={"username": "testuser", "password": test_user_data["password"]})
    assert login.status_code == 401


def test_deactivated_account_is_left_untouched(client, google, db_session, test_user_data):
    client.post("/auth/register", json=test_user_data)
    user = _user(db_session, "test@example.com")
    user.is_verified, user.is_active = True, False
    db_session.commit()
    response = _sign_in(client, google, email="test@example.com", sub="4004")
    assert response.headers["location"] == "/?google_error=deactivated#landing-auth"
    db_session.refresh(user)
    assert user.google_sub is None and auth.AUTH_COOKIE_NAME not in response.headers.get("set-cookie", "")


@pytest.mark.parametrize("overrides, code", [
    ({"email_verified": False}, "unverified"),
    ({"aud": "someone-else"}, "failed"),
    ({"iss": "https://evil.example"}, "failed"),
    ({"nonce": "replayed"}, "failed"),
    ({"exp": 1000}, "expired"),
])
def test_bad_id_tokens_are_refused(client, google, db_session, overrides, code):
    response = _sign_in(client, google, **overrides)
    assert response.headers["location"] == f"/?google_error={code}#landing-auth"
    assert db_session.query(models.User).count() == 0


def test_state_must_match_the_cookie(client, google, db_session):
    _start(client)
    response = client.get("/auth/google/callback?code=good-code&state=forged", follow_redirects=False)
    assert response.headers["location"] == "/?google_error=expired#landing-auth"
    client.cookies.clear()
    response = client.get("/auth/google/callback?code=good-code&state=anything", follow_redirects=False)
    assert response.headers["location"] == "/?google_error=expired#landing-auth"
    assert db_session.query(models.User).count() == 0


def test_cancel_on_google_returns_quietly(client, google):
    _, state, _ = _start(client)
    response = client.get(f"/auth/google/callback?error=access_denied&state={state}", follow_redirects=False)
    assert response.headers["location"] == "/?google_error=cancelled#landing-auth"


def test_invite_link_makes_friends(authenticated_client, google, db_session):
    token = authenticated_client.post("/api/friends/invite-link").json()["url"].rsplit("/", 1)[1]
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    _sign_in(authenticated_client, google, invite=token)
    from app import friend_invites
    inviter = db_session.query(models.User).filter_by(username="testuser").one()
    assert friend_invites.are_friends(db_session, inviter.id, _user(db_session, "newfan@gmail.com").id)


def test_usernames_are_free_and_valid(db_session, client, google, test_user_data):
    client.post("/auth/register", json={**test_user_data, "username": "Riley"})
    _sign_in(client, google, sub="5005", email="riley.two@gmail.com")
    username = _user(db_session, "riley.two@gmail.com").username
    assert username.startswith("Riley") and username != "Riley"
    assert google_signin._username_base("", "x@gmail.com") == "member"
    assert google_signin._username_base("Zoë", "zo.e+tag@gmail.com") == "zo.etag"


def test_google_member_sets_a_password_without_a_current_one(client, google, db_session):
    _sign_in(client, google)
    deactivate = client.post("/account/deactivate", json={"password": ""})
    assert deactivate.status_code == 400 and "Set a password" in deactivate.json()["detail"]
    rename = client.put("/account/username", json={"new_username": "riley_reads"})
    assert rename.status_code == 200 and rename.json()["username"] == "riley_reads"
    changed = client.put("/account/password", json={"new_password": "lanterns over the bay"})
    assert changed.status_code == 200
    user = _user(db_session, "newfan@gmail.com")
    assert user.password_set is True and user.has_password
    # From now on the password is needed like for everyone else.
    assert client.put("/account/username", json={"new_username": "riley_again"}).status_code == 400
    login = client.post("/auth/login", data={"username": "riley_reads", "password": "lanterns over the bay"})
    assert login.status_code == 200


def test_password_members_still_need_their_password(authenticated_client):
    response = authenticated_client.put("/account/username", json={"new_username": "someone_new"})
    assert response.status_code == 400
    assert authenticated_client.get("/account/me").json()["has_password"] is True


def test_site_stats_counts_google_sign_ins(client, google):
    names = {name for name, _ in funnel.GOOGLE}
    assert names <= funnel.SERVER_EVENTS and not names & funnel.CLIENT_EVENTS
    summary = funnel.summary({"google_account_created": 2})
    assert {"event": "google_account_created", "label": "New accounts made with Google", "count": 2} in summary["google"]


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, response):
        self.response, self.calls = response, []

    async def post(self, url, data=None, timeout=None):
        self.calls.append((url, data))
        return self.response


async def test_code_exchange_posts_to_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    fake = _FakeClient(_FakeResponse(200, {"id_token": "a.b.c"}))
    assert await google_signin.exchange_code("abc", fake) == "a.b.c"
    url, data = fake.calls[0]
    assert url == google_signin.TOKEN_URL and data["grant_type"] == "authorization_code"
    assert data["client_secret"] == "test-secret" and data["code"] == "abc"
    with pytest.raises(google_signin.SignInError) as used:
        await google_signin.exchange_code("abc", _FakeClient(_FakeResponse(400, {"error": "invalid_grant"})))
    assert used.value.code == "expired"
    with pytest.raises(google_signin.SignInError) as broken:
        await google_signin.exchange_code("abc", _FakeClient(_FakeResponse(200, {"access_token": "x"})))
    assert broken.value.code == "failed"


@pytest.mark.parametrize("host, expected", [
    ("omnitrackr.xyz", "https://omnitrackr.xyz/auth/google/callback"),
    ("www.omnitrackr.xyz", "https://www.omnitrackr.xyz/auth/google/callback"),
    ("evil.example", "https://omnitrackr.xyz/auth/google/callback"),
])
def test_google_returns_visitors_to_the_host_they_started_on(client, google, monkeypatch, host, expected):
    """The state cookie belongs to one host, so the return address must be that host."""
    monkeypatch.delenv("GOOGLE_REDIRECT_URI")
    monkeypatch.setenv("APP_URL", "https://omnitrackr.xyz")
    monkeypatch.setattr("app.email.APP_URL", "https://omnitrackr.xyz")
    monkeypatch.setattr(auth, "ENVIRONMENT", "production")
    response = client.get("/auth/google/start", headers={"host": host}, follow_redirects=False)
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["redirect_uri"] == [expected]
    saved = google_signin.read_state(response.cookies.get(google_signin.STATE_COOKIE)
                                     or response.headers["set-cookie"].split(";")[0].split("=", 1)[1])
    assert saved["redirect_uri"] == expected


def test_code_exchange_uses_the_same_return_address(client, google, db_session):
    _sign_in(client, google)
    assert google["return_to"] == "https://omnitrackr.xyz/auth/google/callback"


def test_google_button_presses_count_only_real_clicks(client, google, monkeypatch):
    from app.site_traffic import RECORDER
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()

    def presses():
        return sum(count for (_, kind, key), count in RECORDER._pending.items()
                   if kind == "funnel" and key == "google_signin_started")

    client.get("/auth/google/start", follow_redirects=False)  # a link checker following the URL
    assert presses() == 0
    client.get("/auth/google/start", follow_redirects=False, headers={"Sec-Fetch-User": "?1"})
    assert presses() == 1
    RECORDER._pending.clear()
