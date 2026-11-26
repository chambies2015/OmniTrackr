"""Getting people who chose email through sign-up (Nov 23 2026).

Walking the email path on a phone showed where it loses people: the code step lived only
in the tab that signed up. Reading the email in the mail app and coming back often reloads
that tab, and the homepage then looked as if nothing had happened. GET /auth/pending-signup
lets the card open the code step again, for the browser that signed up only. Create also
stopped waiting up to 30 seconds on a slow mail server, and Site stats now counts how long
the code email takes, which box stopped people, and who came back to finish.
"""
import asyncio
from pathlib import Path

import pytest

from app import auth, email as email_utils, funnel, models
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


def register(client, username="comeback", email="comeback@example.com", password="tea on the porch"):
    return client.post("/auth/register", json={"email": email, "username": username, "password": password})


def account(db, username="comeback"):
    user = db.query(models.User).filter_by(username=username).one()
    db.refresh(user)
    return user


def pending(client):
    return client.get("/auth/pending-signup")


# ---------------------------------------------------------------- picking the sign-up up again

def test_the_browser_that_signed_up_gets_its_address_back(client):
    assert register(client).status_code == 201
    response = pending(client)
    assert response.status_code == 200
    assert response.json() == {"waiting": True, "email": "comeback@example.com"}
    assert "no-store" in response.headers["cache-control"]
    # Asking again (another reload) still works: nothing is used up.
    assert pending(client).json()["waiting"] is True


def test_any_other_browser_learns_nothing(client):
    register(client)
    client.cookies.clear()
    assert pending(client).json() == {"waiting": False}
    client.cookies.set(auth.PENDING_SIGNUP_COOKIE, "made-up", path="/auth")
    assert pending(client).json() == {"waiting": False}


def test_a_browser_that_logged_in_with_the_right_password_counts_like_the_one_that_signed_up(client):
    register(client)
    client.cookies.clear()
    assert client.post("/auth/login", data={"username": "comeback", "password": "tea on the porch"}).status_code == 403
    assert pending(client).json() == {"waiting": True, "email": "comeback@example.com"}


def test_confirmed_meanwhile_elsewhere_asks_to_log_in_and_forgets_the_sign_up(client, db_session):
    register(client)
    pending_cookie = client.cookies.get(auth.PENDING_SIGNUP_COOKIE)
    token = account(db_session).verification_token
    client.cookies.clear()  # the mail app's own browser opens the link
    assert client.get(f"/auth/verify-email?token={token}").json()["signed_in"] is False
    client.cookies.set(auth.PENDING_SIGNUP_COOKIE, pending_cookie, path="/auth")  # back in the first browser
    response = pending(client)
    assert response.json() == {"waiting": False, "confirmed": True, "login_hint": "comeback@example.com"}
    assert any(c.startswith(f"{auth.PENDING_SIGNUP_COOKIE}=") and "Max-Age=0" in c
               for c in response.headers.get_list("set-cookie"))
    # It never signs anyone in: the password is still needed.
    assert not any(c.startswith(f"{auth.AUTH_COOKIE_NAME}=") for c in response.headers.get_list("set-cookie"))
    assert client.get("/account/me").status_code == 401


def test_logging_in_forgets_the_sign_up_on_that_browser(client, db_session):
    register(client)
    user = account(db_session)
    user.is_verified, user.verification_token = True, None
    db_session.commit()
    response = client.post("/auth/login", data={"username": "comeback", "password": "tea on the porch"})
    assert response.status_code == 200
    assert any(c.startswith(f"{auth.PENDING_SIGNUP_COOKIE}=") and "Max-Age=0" in c
               for c in response.headers.get_list("set-cookie"))
    # A browser without one gets no extra cookie line.
    client.cookies.clear()
    again = client.post("/auth/login", data={"username": "comeback", "password": "tea on the porch"})
    assert not any(c.startswith(f"{auth.PENDING_SIGNUP_COOKIE}=") for c in again.headers.get_list("set-cookie"))


def test_a_deactivated_account_is_not_offered(client, db_session):
    register(client)
    user = account(db_session)
    user.is_active = False
    db_session.commit()
    assert pending(client).json() == {"waiting": False}


def test_the_endpoint_is_rate_limited():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    start = main.index('route.path == "/auth/pending-signup"')
    assert 'limiter.limit("30/minute")(route.endpoint)' in main[start:main.index("elif", start + 10)]


# ---------------------------------------------------------------- the code email

def _sender(result=True, delay=0.0, error=None):
    async def send(*args, **kwargs):
        await asyncio.sleep(delay)
        if error:
            raise error
        return result
    return send


def test_a_quick_email_is_counted_by_how_long_it_took(monkeypatch, recorder):
    monkeypatch.setattr(email_utils, "send_verification_email", _sender(True))
    assert asyncio.run(auth_router._send_signup_email("a@example.com", "a", "tok", None)) == "sent"
    assert counted("signup_email_quick") == 1 and counted("signup_email_failed") == 0


def test_a_failed_email_says_failed(monkeypatch, recorder):
    for sender in (_sender(False), _sender(error=RuntimeError("smtp down"))):
        monkeypatch.setattr(email_utils, "send_verification_email", sender)
        assert asyncio.run(auth_router._send_signup_email("a@example.com", "a", "tok", None)) == "failed"
    assert counted("signup_email_failed") == 2


def test_a_slow_mail_server_no_longer_holds_the_create_button(monkeypatch, recorder):
    """Create used to wait up to 30 seconds. Now the code step shows after the wait and the send finishes on its own."""
    monkeypatch.setattr(auth_router, "SIGNUP_EMAIL_WAIT_SECONDS", 0.05)
    finished = []

    async def slow(*args, **kwargs):
        await asyncio.sleep(0.2)
        finished.append(True)
        return False  # and then it fails after all

    monkeypatch.setattr(email_utils, "send_verification_email", slow)

    async def scenario():
        answer = await auth_router._send_signup_email("a@example.com", "a", "tok", None)
        assert not finished  # answered before the mail server did
        assert len(auth_router._unfinished_sends) == 1
        await asyncio.sleep(0.3)
        return answer

    assert asyncio.run(scenario()) == "sending"
    assert finished and not auth_router._unfinished_sends
    assert counted("signup_email_slow") == 1 and counted("signup_email_failed") == 1


def test_register_passes_the_answer_to_the_card(client, monkeypatch):
    monkeypatch.setattr(auth_router, "_send_signup_email", lambda *args: _done("sending"))
    response = register(client)
    assert response.status_code == 201 and response.headers["X-Verification-Email"] == "sending"


async def _done(value):
    return value


# ---------------------------------------------------------------- Site stats

def test_site_stats_shows_the_new_steps():
    counts = {"signup_check_email": 2, "signup_check_password": 3, "signup_request_failed": 1,
              "signup_email_quick": 5, "signup_email_wait": 2, "signup_email_slow": 1, "signup_email_failed": 1,
              "signup_waiting_resumed": 4, "signup_waiting_confirmed": 1, "signup_restart_clicked": 1}
    summary = funnel.summary(counts)
    rows = lambda key: {row["event"]: row["count"] for row in summary[key]}  # noqa: E731
    assert rows("email_snags") == {"signup_check_email": 2, "signup_check_password": 3, "signup_check_username": 0,
                                   "signup_request_failed": 1}
    assert rows("email_delivery") == {"signup_email_quick": 5, "signup_email_wait": 2, "signup_email_slow": 1,
                                      "signup_email_failed": 1}
    assert rows("email_return") == {"signup_waiting_resumed": 4, "signup_waiting_confirmed": 1, "signup_restart_clicked": 1}
    # Browsers report what only they see; how long the mail server took is the server's to say.
    browser = {"signup_check_email", "signup_check_password", "signup_check_username", "signup_request_failed",
               "signup_waiting_resumed", "signup_waiting_confirmed", "signup_restart_clicked"}
    assert browser <= funnel.CLIENT_EVENTS
    assert not {"signup_email_quick", "signup_email_wait", "signup_email_slow", "signup_email_failed"} & funnel.CLIENT_EVENTS
    assert {"signup_email_quick", "signup_email_wait", "signup_email_slow"} <= funnel.SERVER_EVENTS
    page = (ROOT / "app/templates/site_stats.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/site-stats.js").read_text(encoding="utf-8")
    for list_id, key, line in (("emailSnags", "email_snags", "Email form, what stopped people: "),
                               ("emailDelivery", "email_delivery", "Sending the code email: "),
                               ("emailReturn", "email_return", "Coming back to finish signing up: ")):
        assert f'id="{list_id}"' in page and f"fillList('{list_id}', data.funnel.{key}" in script and line in script
    assert "site-stats.js?v=20261123-signup-1" in page


def test_the_browser_can_report_the_new_steps(client, recorder):
    for event in ("signup_check_password", "signup_waiting_resumed", "signup_email_quick"):
        assert client.post("/api/funnel", json={"event": event}).status_code == 204
    assert counted("signup_check_password") == 1 and counted("signup_waiting_resumed") == 1
    assert counted("signup_email_quick") == 0  # server-only


# ---------------------------------------------------------------- the card

def test_both_cards_keep_the_code_step_open_for_the_quiz_and_read_the_line_above_the_box():
    for html in (LANDING, INDEX):
        assert '<a href="/taste-quiz" target="_blank" rel="noopener">take the 1-minute taste quiz</a> (it opens in a new tab)' in html
        assert 'aria-describedby="verifySentLead verifyCodeError"' in html
        assert "auth.js?v=20261125-yearbook-1" in html


def test_the_card_asks_for_a_waiting_sign_up_without_storing_the_address():
    assert "/auth/pending-signup" in AUTH_JS and "resumeWaitingSignup().then" in AUTH_JS
    marker = AUTH_JS[AUTH_JS.index("function markSignupWaiting()"):AUTH_JS.index("function clearSignupWaiting()")]
    assert "String(Date.now())" in marker and "email" not in marker
    assert "headers.get('X-Verification-Email')" in AUTH_JS and "emailSlow: delivery === 'sending'" in AUTH_JS
