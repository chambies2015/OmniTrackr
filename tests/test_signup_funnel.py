"""Sign-up fixes (Oct 3): username/password rules, funnel counters, guest list, verification window."""
import asyncio
from datetime import date

import pytest

from app import auth, email as email_utils, funnel, guest_picks, models, signup_rules
from app.site_traffic import RECORDER


@pytest.fixture
def recorder(monkeypatch):
    """Turn the in-memory counters on (they're off in the test suite) and start empty."""
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(recorder, event):
    return sum(count for (day, kind, key), count in recorder._pending.items() if kind == "funnel" and key == event)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(auth, "ENVIRONMENT", "production")


def register(client, username="newfan", email="newfan@example.com", password="tea on the porch"):
    return client.post("/auth/register", json={"email": email, "username": username, "password": password})


# ---------------------------------------------------------------- usernames

@pytest.mark.parametrize("name", ["dan", "Movie_Fan", "a.b-c", "x" * 30, "007bond"])
def test_good_usernames(name):
    assert signup_rules.username_problem(name) is None


@pytest.mark.parametrize("name", ["ab", "x" * 31, " dan", "dan ", "John Smith", "<script>", "me@mail.com", "_dan", ".dan",
                                  "dan/../x", "dän"])
def test_rejected_usernames(name):
    assert signup_rules.username_problem(name)


def test_register_rejects_bad_usernames_with_a_clear_message(client, recorder):
    response = register(client, username="John Smith")
    assert response.status_code == 400
    assert "letters, numbers" in response.json()["detail"]
    assert counted(recorder, "signup_rejected_username_invalid") == 1
    assert counted(recorder, "signup_submitted") == 1


def test_usernames_are_unique_ignoring_capitals(client, db_session, recorder):
    assert register(client, username="Dan", email="dan@example.com").status_code == 201
    response = register(client, username="DAN", email="other@example.com")
    assert response.status_code == 400 and "already taken" in response.json()["detail"]
    assert counted(recorder, "signup_rejected_username_taken") == 1


def test_existing_odd_usernames_keep_working(client, db_session):
    """Rules apply to new names only: an older "John Smith" account can still log in."""
    db_session.add(models.User(username="John Smith", email="js@example.com", is_verified=True,
                               hashed_password=auth.get_password_hash("older-password")))
    db_session.commit()
    response = client.post("/auth/login", data={"username": "John Smith", "password": "older-password"})
    assert response.status_code == 200


def test_rename_follows_the_same_rules(authenticated_client, db_session):
    db_session.add(models.User(username="Taken", email="t@example.com", hashed_password="x"))
    db_session.commit()
    bad = authenticated_client.put("/account/username", json={"new_username": "has space", "password": "testpassword123"})
    assert bad.status_code == 400
    clash = authenticated_client.put("/account/username", json={"new_username": "taken", "password": "testpassword123"})
    assert clash.status_code == 400 and "taken" in clash.json()["detail"]
    own_caps = authenticated_client.put("/account/username", json={"new_username": "TestUser", "password": "testpassword123"})
    assert own_caps.status_code == 200


# ---------------------------------------------------------------- passwords

@pytest.mark.parametrize("password,ok", [
    ("tea on the porch", True),           # a phrase: no symbols or capitals required
    ("longenoughpassword", True),
    ("short1!", False),                    # under 8
    ("password123", False),                # common
    ("aaaaaaaaaaa", False),                # one character repeated
    ("newfan12", False),                   # username plus a couple of digits
    ("é" * 37, False),                     # over 72 bytes
])
def test_password_rules(password, ok):
    assert (signup_rules.password_problem(password, "newfan", "newfan@example.com") is None) is ok


def test_production_register_uses_the_new_password_rules(client, production, recorder):
    weak = register(client, password="password123")
    assert weak.status_code == 400 and "easy to guess" in weak.json()["detail"]
    assert counted(recorder, "signup_rejected_password") == 1
    assert register(client, password="tea on the porch").status_code == 201


def test_password_change_is_now_checked(authenticated_client, production):
    response = authenticated_client.put("/account/password", json={"current_password": "testpassword123", "new_password": "12345678"})
    assert response.status_code == 400


# ---------------------------------------------------------------- funnel

def test_successful_signup_and_verification_are_counted(client, db_session, recorder):
    assert register(client).status_code == 201
    assert counted(recorder, "signup_created") == 1
    user = db_session.query(models.User).filter_by(username="newfan").one()
    token = email_utils.generate_verification_token(user.email)
    assert client.get(f"/auth/verify-email?token={token}").status_code == 200
    assert counted(recorder, "email_verified") == 1
    login = client.post("/auth/login", data={"username": "newfan", "password": "tea on the porch"})
    assert login.status_code == 200
    assert counted(recorder, "first_login") == 1
    client.post("/auth/login", data={"username": "newfan", "password": "tea on the porch"})
    assert counted(recorder, "first_login") == 1


def test_unverified_login_and_duplicate_email_are_counted(client, recorder):
    register(client)
    assert client.post("/auth/login", data={"username": "newfan", "password": "tea on the porch"}).status_code == 403
    assert counted(recorder, "login_blocked_unverified") == 1
    again = register(client, username="another")
    assert again.status_code == 400 and "Log in, or reset" in again.json()["detail"]
    assert counted(recorder, "signup_rejected_email_taken") == 1


def test_expired_links_are_counted(client, recorder):
    assert client.get("/auth/verify-email?token=not-a-token").status_code == 400
    assert counted(recorder, "verification_link_expired") == 1


def test_funnel_events_store_no_personal_data(client, recorder):
    register(client)
    keys = list(recorder._pending)
    assert keys and all(isinstance(day, date) and kind in ("funnel",) and "@" not in key and "newfan" not in key
                        for day, kind, key in keys)


def test_browser_can_only_report_whitelisted_events(client, recorder):
    assert client.post("/api/funnel", json={"event": "signup_form_opened"}).status_code == 204
    assert client.post("/api/funnel", json={"event": "signup_created"}).status_code == 204  # server-only: ignored
    assert client.post("/api/funnel", json={"event": "anything<script>"}).status_code == 204
    assert counted(recorder, "signup_form_opened") == 1
    assert counted(recorder, "signup_created") == 0
    assert all(key in funnel.SERVER_EVENTS for (_, kind, key) in recorder._pending if kind == "funnel")


def test_bots_are_not_counted(client, recorder):
    client.post("/api/funnel", json={"event": "signup_form_opened"}, headers={"User-Agent": "Googlebot/2.1"})
    assert counted(recorder, "signup_form_opened") == 0


def test_funnel_is_off_when_tracking_is_off(client, monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", False)
    RECORDER._pending.clear()
    register(client)
    assert not RECORDER._pending


def test_site_stats_shows_the_funnel(client, db_session, monkeypatch):
    from app.routers import site_stats
    db_session.add_all([
        models.SiteTrafficDaily(day=date.today(), kind="funnel", key="signup_form_opened", count=9),
        models.SiteTrafficDaily(day=date.today(), kind="funnel", key="signup_created", count=2),
        models.SiteTrafficDaily(day=date.today(), kind="funnel", key="signup_rejected_password", count=3),
    ])
    db_session.commit()
    data = site_stats._funnel(db_session, 30, date.today())
    steps = {step["event"]: step["count"] for step in data["steps"]}
    assert steps["signup_form_opened"] == 9 and steps["signup_created"] == 2 and steps["email_verified"] == 0
    assert {item["event"]: item["count"] for item in data["issues"]}["signup_rejected_password"] == 3
    assert site_stats._retention(db_session) == {"weekly_email_subscribers": 0, "public_profiles": 0}


# ---------------------------------------------------------------- verification email

def test_verification_links_last_48_hours(client, db_session, monkeypatch):
    register(client)
    seen = {}
    real = email_utils.verify_token

    def spy(token, max_age=3600):
        seen["max_age"] = max_age
        return real(token, max_age=max_age)

    monkeypatch.setattr(email_utils, "verify_token", spy)
    token = email_utils.generate_verification_token("newfan@example.com")
    client.get(f"/auth/verify-email?token={token}")
    assert seen["max_age"] == 48 * 3600


def test_usernames_are_escaped_in_emails(monkeypatch):
    sent = {}

    class FakeMessage:
        def __init__(self, **kwargs):
            sent.update(kwargs)

    monkeypatch.setattr(email_utils, "MessageSchema", FakeMessage)
    asyncio.run(email_utils.send_verification_email("x@example.com", '<a href="https://evil.example">win</a>', "tok"))
    html = sent["alternative_body"]
    assert '<a href="https://evil.example">' not in html and "&lt;a href=" in html
    assert "48 hours" in html and "48 hours" in sent["body"]  # plain-text part too


# ---------------------------------------------------------------- guest list

def seed_popular(db):
    users = [models.User(username=f"m{i}", email=f"m{i}@example.com", hashed_password="x", is_verified=True)
             for i in range(3)]
    db.add_all(users)
    db.flush()
    titles = [("Interstellar", 2014), ("Arrival", 2016), ("Dune", 2021), ("Heat", 1995), ("Alien", 1979), ("Up", 2009)]
    for user in users[:2]:
        for title, year in titles:
            db.add(models.Movie(user_id=user.id, title=title, director="x", year=year, rating=9,
                                poster_url="https://img.example/p.jpg", review="private note"))
    db.commit()
    return users


def test_homepage_picks_section(db_session):
    seed_popular(db_session)
    items = guest_picks.picks(db_session)
    assert len(items) == 6
    html = guest_picks.section_html(items)
    assert 'data-guest-slug="interstellar-2014"' in html and "Start your list" in html
    assert 'data-action="show-register-form"' in html
    assert guest_picks.section_html(items[:5]) == ""  # too few to be worth showing


def test_homepage_includes_picks(client, db_session, monkeypatch):
    seed_popular(db_session)
    guest_picks.clear_cache()
    monkeypatch.setattr(guest_picks, "homepage_section", lambda: guest_picks.section_html(guest_picks.picks(db_session)))
    page = client.get("/").text
    assert 'id="start-your-list"' in page and "guest-list.js" in page
    assert 'id="signup"' in page


def test_guest_list_import_adds_public_details_only(authenticated_client, db_session):
    seed_popular(db_session)
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "movie", "slug": "interstellar-2014"},
        {"kind": "movie", "slug": "interstellar-2014"},   # duplicate in the list
        {"kind": "movie", "slug": "not-a-real-title-1900"},
        {"kind": "podcast", "slug": "x"},
    ]})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["title"] for item in data["added"]] == ["Interstellar"] and data["missing"] == 2
    me = db_session.query(models.User).filter_by(username="testuser").one()
    movie = db_session.query(models.Movie).filter_by(user_id=me.id).one()
    assert movie.rating is None and movie.review is None and not movie.watched
    again = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": "movie", "slug": "interstellar-2014"}]})
    assert again.json()["existing"][0]["title"] == "Interstellar" and again.json()["added"] == []


def test_guest_list_import_needs_sign_in(client):
    assert client.post("/api/guest-list/import", json={"items": []}).status_code == 401


def test_guest_list_import_is_bounded(authenticated_client):
    too_many = [{"kind": "movie", "slug": f"t-{i}"} for i in range(31)]
    assert authenticated_client.post("/api/guest-list/import", json={"items": too_many}).status_code == 422


def test_title_pages_offer_guests_a_save_button(client, db_session):
    seed_popular(db_session)
    page = client.get("/titles/movie/interstellar-2014").text
    assert 'data-guest-save' in page and 'data-guest-slug="interstellar-2014"' in page and "guest-list.js" in page


# ---------------------------------------------------------------- rate-limit address

class _Req:
    def __init__(self, headers, host="10.226.90.65"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()
        self.scope = {"client": (host, 1234)}


def test_rate_limits_use_the_real_visitor_on_render(monkeypatch):
    from app.main import client_address
    monkeypatch.setenv("RENDER", "true")
    request = _Req({"true-client-ip": "81.97.145.24", "x-forwarded-for": "1.2.3.4, 172.71.195.123, 10.226.90.65"})
    assert client_address(request) == "81.97.145.24"
    assert client_address(_Req({"cf-connecting-ip": "81.97.145.25"})) == "81.97.145.25"


def test_forwarding_headers_are_ignored_off_render(monkeypatch):
    from app.main import client_address
    monkeypatch.delenv("RENDER", raising=False)
    assert client_address(_Req({"true-client-ip": "6.6.6.6"}, host="127.0.0.1")) == "127.0.0.1"
