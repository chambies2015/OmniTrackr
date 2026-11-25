"""Confirm a new account with the 6-digit code from its email (Nov 18 2026).

The email always had a link. On phones the mail app opens it in its own browser,
which isn't signed in and doesn't have the titles a guest saved, so the visitor was
sent to log in somewhere else. The code is typed on the card that signed up instead.
"""
import asyncio
import re
from pathlib import Path

import pytest

from app import auth, email as email_utils, funnel, models, start_flow
from app.routers import auth as auth_router
from app.site_traffic import RECORDER

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "app/templates/public_landing.html").read_text(encoding="utf-8")
INDEX = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
AUTH_JS = (ROOT / "app/static/auth.js").read_text(encoding="utf-8")


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(event):
    return sum(count for (day, kind, key), count in RECORDER._pending.items() if kind == "funnel" and key == event)


def register(client, username="newfan", email="newfan@example.com", password="tea on the porch"):
    return client.post("/auth/register", json={"email": email, "username": username, "password": password})


def account(db, username="newfan"):
    user = db.query(models.User).filter_by(username=username).one()
    db.refresh(user)
    return user


def code_for(db, username="newfan"):
    return email_utils.signup_code(account(db, username).verification_token)


def send_code(client, code, email="newfan@example.com"):
    return client.post("/auth/verify-code", json={"email": email, "code": code})


def wrong(code):
    return f"{(int(code) + 1) % 1_000_000:06d}"


# ---------------------------------------------------------------- the code itself

def test_the_code_is_six_digits_and_changes_with_each_email():
    first, second = email_utils.signup_code("token-a"), email_utils.signup_code("token-b")
    assert re.fullmatch(r"\d{6}", first) and re.fullmatch(r"\d{6}", second)
    assert first == email_utils.signup_code("token-a") and first != second


def test_the_email_leads_with_the_code(monkeypatch):
    sent = {}

    class Capture:
        def __init__(self, **kwargs):
            sent.update(kwargs)

    monkeypatch.setattr(email_utils, "MessageSchema", Capture)
    asyncio.run(email_utils.send_verification_email("x@example.com", "neo", "tok"))
    code = email_utils.signup_code("tok")
    assert sent["subject"] == f"{code} is your OmniTrackr code"
    assert f"{code[:3]} {code[3:]}" in sent["alternative_body"] and f"{code[:3]} {code[3:]}" in sent["body"]
    assert "token=tok" in sent["body"] and "48 hours" in sent["body"]


def test_resending_replaces_the_code(client, db_session):
    register(client)
    before = code_for(db_session)
    assert client.post("/auth/resend-verification?email=newfan@example.com").status_code == 200
    after = code_for(db_session)
    assert before != after
    assert send_code(client, before).status_code == 400
    assert send_code(client, after).status_code == 200


# ---------------------------------------------------------------- typing it

def test_the_right_code_confirms_and_opens_the_library_in_this_tab(client, db_session, recorder):
    register(client)
    response = send_code(client, code_for(db_session))
    assert response.status_code == 200
    body = response.json()
    assert body["signed_in"] is True and body["user"]["username"] == "newfan" and "hashed_password" not in body["user"]
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{auth.AUTH_COOKIE_NAME}=") and "HttpOnly" in c for c in cookies)
    assert any(c.startswith(f"{auth.PENDING_SIGNUP_COOKIE}=") and "Max-Age=0" in c for c in cookies)
    assert any(c.startswith(f"{start_flow.COOKIE}=") for c in cookies)  # first visit goes to /start
    user = account(db_session)
    assert user.is_verified and user.verification_token is None and user.login_count == 1
    assert client.get("/account/me").status_code == 200
    assert counted("email_verified") == 1 and counted("email_confirmed_code") == 1 and counted("first_login") == 1
    # The code is used up with the token.
    assert send_code(client, "123456").status_code == 400


def test_spaces_and_dashes_in_a_pasted_code_are_fine(client, db_session):
    register(client)
    code = code_for(db_session)
    assert send_code(client, f" {code[:3]}-{code[3:]} ").status_code == 200


def test_the_code_works_in_another_browser_after_logging_in_there(client, db_session):
    register(client)
    client.cookies.clear()  # on a phone after signing up on a laptop: logging in shows the code box
    assert client.post("/auth/login", data={"username": "newfan", "password": "tea on the porch"}).status_code == 403
    response = send_code(client, code_for(db_session))
    assert response.status_code == 200 and response.json()["signed_in"] is True
    assert client.get("/account/me").status_code == 200


def test_a_browser_that_never_showed_the_password_confirms_but_must_log_in(client, db_session):
    """Like the link: a code typed where nobody signed up or logged in confirms the address, then asks to log in.
    The Nov 18 2026 sweep changed this from signing straight in (see test_merge_sweep_nov18b)."""
    register(client)
    client.cookies.clear()
    response = send_code(client, code_for(db_session))
    assert response.status_code == 200
    assert response.json()["signed_in"] is False and response.json()["login_hint"] == "newfan@example.com"
    assert account(db_session).is_verified
    assert auth.AUTH_COOKIE_NAME not in response.headers.get("set-cookie", "")
    assert client.get("/account/me").status_code == 401


def test_the_email_is_matched_ignoring_capitals(client, db_session):
    register(client)
    assert send_code(client, code_for(db_session), email=" NewFan@Example.com ").status_code == 200


@pytest.mark.parametrize("code", ["", "12345", "abcdef", "1234567"])
def test_a_code_that_isnt_six_digits_is_turned_down_before_any_lookup(client, db_session, code):
    register(client)
    response = send_code(client, code)
    assert response.status_code in (400, 422)
    assert not db_session.query(models.SignupCodeAttempt).count()


def test_a_wrong_code_is_counted_and_ten_stop_the_code_but_not_the_link(client, db_session, recorder):
    register(client)
    right = code_for(db_session)
    for _ in range(auth_router.SIGNUP_CODE_MAX_FAILURES):
        response = send_code(client, wrong(right))
        assert response.status_code == 400 and "didn't work" in response.json()["detail"]
    assert counted("signup_code_wrong") == auth_router.SIGNUP_CODE_MAX_FAILURES
    attempts = db_session.query(models.SignupCodeAttempt).one()
    assert attempts.failures == auth_router.SIGNUP_CODE_MAX_FAILURES and attempts.last_failed_at is not None
    blocked = send_code(client, right)
    assert blocked.status_code == 429 and "link" in blocked.json()["detail"]
    assert not account(db_session).is_verified
    # A new email doesn't reset the count, so guesses can't be spread over many codes.
    client.post("/auth/resend-verification?email=newfan@example.com")
    assert send_code(client, code_for(db_session)).status_code == 429
    token = account(db_session).verification_token
    assert client.get(f"/auth/verify-email?token={token}").status_code == 200
    assert account(db_session).is_verified


def test_an_expired_code_says_so(client, db_session, monkeypatch):
    import itsdangerous.timed as timed

    register(client)
    user = account(db_session)
    three_days_ago = timed.time.time() - 3 * 24 * 3600
    with monkeypatch.context() as patch:  # the link and the code last 48 hours
        patch.setattr(timed.time, "time", lambda: three_days_ago)
        stale = email_utils.generate_verification_token(user.email)
    user.verification_token = stale
    db_session.commit()
    response = send_code(client, email_utils.signup_code(stale))
    assert response.status_code == 400 and "expired" in response.json()["detail"]
    assert not account(db_session).is_verified


def test_unknown_confirmed_and_email_change_accounts_get_the_same_answer(client, db_session):
    unknown = send_code(client, "123456", email="nobody@example.com")
    register(client)
    user = account(db_session)
    user.is_verified = True
    db_session.commit()
    confirmed = send_code(client, email_utils.signup_code(user.verification_token))
    user.verification_token = "email_change:abc:new@example.com"
    db_session.commit()
    changing = send_code(client, email_utils.signup_code(user.verification_token))
    assert unknown.status_code == confirmed.status_code == changing.status_code == 400
    assert unknown.json() == confirmed.json() == changing.json()


def test_a_deactivated_account_cannot_be_opened_with_a_code(client, db_session):
    register(client)
    user = account(db_session)
    user.is_active = False
    db_session.commit()
    assert send_code(client, code_for(db_session)).status_code == 400
    assert not account(db_session).is_verified


# ---------------------------------------------------------------- ways back to the code

def test_logging_in_before_confirming_offers_the_code_and_marks_this_browser(client, db_session, recorder):
    register(client)
    client.cookies.clear()
    response = client.post("/auth/login", data={"username": "newfan", "password": "tea on the porch"})
    assert response.status_code == 403
    body = response.json()
    assert body["unverified"] is True and body["email"] == "newfan@example.com" and "verify" in body["detail"].lower()
    assert counted("login_blocked_unverified") == 1
    # The link opened in this browser now signs in, like the browser that signed up.
    token = account(db_session).verification_token
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is True
    assert counted("email_confirmed_link") == 1


def test_a_wrong_password_never_reveals_the_email(client, db_session):
    register(client)
    response = client.post("/auth/login", data={"username": "newfan", "password": "not the one"})
    assert response.status_code == 401 and "email" not in response.json()
    assert auth.PENDING_SIGNUP_COOKIE not in response.headers.get("set-cookie", "")


def test_signing_up_again_with_a_waiting_email_offers_a_new_code(client, db_session, recorder):
    register(client)
    again = register(client, username="newfan2", password="another long phrase")
    assert again.status_code == 400
    assert again.json() == {"detail": again.json()["detail"], "unverified": True, "email": "newfan@example.com"}
    assert "already registered" in again.json()["detail"]
    assert counted("signup_rejected_email_pending") == 1
    assert db_session.query(models.User).count() == 1


def test_a_confirmed_email_still_gets_log_in_or_reset(client, db_session, recorder):
    register(client)
    user = account(db_session)
    user.is_verified = True
    db_session.commit()
    again = register(client, username="newfan2")
    assert again.status_code == 400 and "Log in, or reset" in again.json()["detail"] and "unverified" not in again.json()
    assert counted("signup_rejected_email_taken") == 1


def test_register_says_whether_the_email_went(client, monkeypatch):
    unconfigured = email_utils.send_verification_email

    async def delivered(*args, **kwargs):
        return True

    monkeypatch.setattr(email_utils, "send_verification_email", delivered)
    assert register(client).headers["X-Verification-Email"] == "sent"

    async def broken(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(email_utils, "send_verification_email", broken)
    response = register(client, username="second", email="second@example.com")
    assert response.status_code == 201 and response.headers["X-Verification-Email"] == "failed"

    # With no mail server set up nothing is sent, so the inbox step says so.
    monkeypatch.setattr(email_utils, "send_verification_email", unconfigured)
    response = register(client, username="third", email="third@example.com")
    assert response.status_code == 201 and response.headers["X-Verification-Email"] == "failed"


def test_a_link_opened_in_another_browser_is_counted(client, db_session, recorder):
    register(client)
    client.cookies.clear()
    token = account(db_session).verification_token
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is False
    assert counted("email_link_other_browser") == 1 and counted("email_confirmed_link") == 0


# ---------------------------------------------------------------- Site stats and pages

def test_site_stats_lists_how_emails_get_confirmed():
    counts = {"signup_created": 5, "google_account_created": 2, "email_confirmed_code": 2, "email_confirmed_link": 1,
              "email_link_other_browser": 1, "signup_code_wrong": 3, "signup_inbox_opened": 2}
    rows = {row["event"]: row["count"] for row in funnel.summary(counts)["email_confirm"]}
    assert rows == {"signup_created_email": 3, "email_confirmed_code": 2, "email_confirmed_link": 1,
                    "email_link_other_browser": 1, "signup_code_wrong": 3, "signup_inbox_opened": 2}
    assert "signup_inbox_opened" in funnel.CLIENT_EVENTS
    assert not {"email_confirmed_code", "email_confirmed_link", "signup_code_wrong"} & funnel.CLIENT_EVENTS
    script = (ROOT / "app/static/site-stats.js").read_text(encoding="utf-8")
    assert "fillList('emailConfirm'" in script and "Confirming the email: " in script
    assert 'id="emailConfirm"' in (ROOT / "app/templates/site_stats.html").read_text(encoding="utf-8")


def test_both_sign_in_cards_have_the_code_box():
    for html in (LANDING, INDEX):
        panel = html[html.index('<div id="verifySentPanel"'):html.index('<div id="authStatusPanel"')]
        assert 'id="verifyCodeForm"' in panel and 'autocomplete="one-time-code"' in panel and 'inputmode="numeric"' in panel
        assert panel.index('id="verifyCodeForm"') < panel.index('id="verifySentInbox"')
        assert "6-digit code to confirm" in html
        assert "auth.js?v=20261125-yearbook-1" in html


def test_the_code_endpoint_is_rate_limited():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    start = main.index('route.path == "/auth/verify-code"')
    assert 'limiter.limit("10/minute")(route.endpoint)' in main[start:main.index("elif", start + 10)]


def test_the_card_handles_the_new_answers():
    assert "error.unverified === true" in AUTH_JS and "showInboxPanel('pending'" in AUTH_JS
    assert "X-Verification-Email" in AUTH_JS and "/auth/verify-code" in AUTH_JS
