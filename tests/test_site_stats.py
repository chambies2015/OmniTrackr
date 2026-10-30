"""Owner-only Site stats page, admin access, and anonymous traffic counting."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from starlette.requests import Request

from app import admin_access, dashboard_assets, models, site_traffic
from app.site_traffic import TrafficRecorder, classify_device, should_count, traffic_source
from tests.conftest import TestingSessionLocal

ROOT = Path(__file__).resolve().parents[1]
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"


def make_request(path="/", *, method="GET", query="", headers=None, cookies=None, client=("203.0.113.9", 5000)):
    raw = [(b"user-agent", BROWSER_UA.encode())]
    for key, value in (headers or {}).items():
        raw = [pair for pair in raw if pair[0] != key.lower().encode()]
        raw.append((key.lower().encode(), value.encode()))
    if cookies:
        raw.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({
        "type": "http", "method": method, "path": path, "query_string": query.encode(),
        "headers": raw, "client": client, "scheme": "https", "server": ("omnitrackr.xyz", 443),
    })


@pytest.fixture
def admin_env(monkeypatch):
    for name in ("ADMIN_USERNAMES", "COLLECTION_MODERATOR_USERNAMES", "admin_usernames", "collection_moderator_usernames"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# ---------------------------------------------------------------- admin access

def test_admin_list_reads_both_variables_case_insensitively(admin_env):
    admin_env.setenv("collection_moderator_usernames", "Dan ")
    admin_env.setenv("ADMIN_USERNAMES", "owner,  second")
    assert admin_access.admin_usernames() == {"Dan", "owner", "second"}

    class User:
        username = "Dan"
    assert admin_access.is_site_admin(User()) and admin_access.is_moderator(User())
    User.username = "someone"
    assert not admin_access.is_site_admin(User())


@pytest.mark.parametrize("lookalike", ["DAN", "dan", "dAn", "Dan ", " Dan"])
def test_capitalised_copies_of_the_owner_name_are_not_admins(admin_env, lookalike):
    """Usernames are unique only as typed, so admin matching must be exact."""
    admin_env.setenv("ADMIN_USERNAMES", "Dan")

    class User:
        username = lookalike
    assert not admin_access.is_site_admin(User())
    assert not admin_access.is_moderator(User())


def test_no_admins_by_default(admin_env):
    assert admin_access.admin_usernames() == set()


def test_lowercase_moderator_variable_also_unlocks_moderator_insights(authenticated_client, admin_env):
    admin_env.setenv("collection_moderator_usernames", "testuser")
    assert authenticated_client.get("/collections/moderation/insights").status_code == 200


# ---------------------------------------------------------------- endpoints

def test_page_shell_is_public_but_noindex_and_holds_no_data(client):
    response = client.get("/site-stats")
    assert response.status_code == 200
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "/static/site-stats.js" in response.text
    assert "Content-Security-Policy" in response.headers
    assert "testuser" not in response.text
    # The Ko-fi linking card is an empty shell too; payments load from the admin-only API.
    assert 'id="kofiCard"' in response.text and 'id="kofiList"></ul>' in response.text


def test_overview_requires_login(client):
    assert client.get("/api/site-stats/overview").status_code == 401
    assert client.get("/api/site-stats/access").status_code == 401


def test_overview_is_forbidden_for_regular_members(authenticated_client, admin_env):
    admin_env.setenv("ADMIN_USERNAMES", "somebody-else")
    assert authenticated_client.get("/api/site-stats/access").json() == {"admin": False}
    response = authenticated_client.get("/api/site-stats/overview")
    assert response.status_code == 403
    assert "site owner" in response.json()["detail"]


def test_overview_for_admin_has_every_section(authenticated_client, admin_env, db_session):
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add_all([
        models.Movie(user_id=user.id, title="Heat", director="Mann", year=1995, watched=True, rating=9.0),
        models.Book(user_id=user.id, title="Dune", author="Herbert", year=1965),
    ])
    today = date.today()
    db_session.add_all([
        models.SiteTrafficDaily(day=today, kind="total", key="views", count=12),
        models.SiteTrafficDaily(day=today, kind="total", key="visitors", count=5),
        models.SiteTrafficDaily(day=today, kind="page", key="/release-radar", count=7),
        models.SiteTrafficDaily(day=today, kind="page", key="/", count=5),
        models.SiteTrafficDaily(day=today, kind="source", key="google.com", count=4),
        models.SiteTrafficDaily(day=today, kind="device", key="mobile", count=3),
        models.SiteTrafficDaily(day=today - timedelta(days=40), kind="total", key="views", count=3),
    ])
    db_session.commit()

    assert authenticated_client.get("/api/site-stats/access").json() == {"admin": True}
    response = authenticated_client.get("/api/site-stats/overview?days=30")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    data = response.json()
    assert data["days"] == 30 and data["viewer"] == "testuser"
    assert {"members", "signups", "journal_activity", "traffic", "popular_titles", "insights", "system"} <= set(data)
    assert len(data["signups"]) == 30 and len(data["traffic"]["series"]) == 30
    assert data["traffic"]["totals"] == {"views": 12, "visitors": 5}
    assert data["traffic"]["previous_totals"] == {"views": 3, "visitors": 0}
    assert data["traffic"]["top_pages"][0] == {"key": "/release-radar", "count": 7}
    assert data["traffic"]["sources"] == [{"key": "google.com", "count": 4}]
    assert data["traffic"]["tracking_since"] == (today - timedelta(days=40)).isoformat()
    assert data["insights"]["content"]["total_items"] == 2
    assert data["members"]["new_in_range"] == 1
    assert any(item["name"].startswith("OMDb") for item in data["system"]["integrations"])
    # Aggregates only: no emails or password material anywhere in the payload.
    assert "@example.com" not in response.text and "hashed_password" not in response.text


def test_overview_growth_counts_invites_supporters_email_and_takes(authenticated_client, admin_env, db_session):
    from datetime import datetime
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    user = db_session.query(models.User).filter_by(username="testuser").one()
    friend = models.User(username="growthfriend", email="growthfriend@example.com", hashed_password="x", is_verified=True)
    waiting = models.User(username="growthwaiting", email="growthwaiting@example.com", hashed_password="x")
    db_session.add_all([friend, waiting])
    db_session.flush()
    now = datetime.utcnow()
    old = now - timedelta(days=60)
    take = models.TakeRequest(asker_id=user.id, kind="movie", slug="heat-1995", title="Heat", token="growthtake",
                              expires_at=now + timedelta(days=30))
    db_session.add_all([
        models.FriendInvite(user_id=user.id, token="growthinvite"),
        models.FriendInviteSignup(inviter_id=user.id, invitee_id=friend.id, completed_at=now),
        models.FriendInviteSignup(inviter_id=user.id, invitee_id=waiting.id),
        models.Supporter(user_id=user.id, since=now, active_until=now + timedelta(days=30), monthly=True),
        models.Supporter(user_id=friend.id, since=old, active_until=old + timedelta(days=30)),
        models.KofiPayment(message_id="growth-1", kind="Donation", user_id=user.id),
        models.KofiPayment(message_id="growth-2", kind="Donation"),
        models.EmailDigestSubscription(user_id=user.id, token="growthdigest"),
        take,
    ])
    db_session.flush()
    db_session.add(models.TakeResponse(request_id=take.id, responder_id=friend.id))
    db_session.commit()

    response = authenticated_client.get("/api/site-stats/overview?days=30")
    assert response.status_code == 200
    growth = response.json()["growth"]
    assert growth["invites"] == {"links": 1, "new_links": 1, "signups": 2, "friends_made": 1, "awaiting_verification": 1}
    assert growth["supporters"] == {"active": 1, "monthly": 1, "all_time": 2, "new": 1, "payments": 2, "unlinked_payments": 1}
    assert growth["weekly_email"] == {"subscribers": 1, "new": 1}
    assert growth["takes"] == {"asked": 1, "answered": 1}
    # Counts only: no tokens or Ko-fi details anywhere, and no usernames in the growth block.
    assert "growthinvite" not in response.text and "growth-2" not in response.text
    assert "growthfriend" not in str(growth)


@pytest.mark.parametrize("days", [3, 91])
def test_overview_range_is_bounded(authenticated_client, admin_env, days):
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    assert authenticated_client.get(f"/api/site-stats/overview?days={days}").status_code == 422


def test_popular_titles_need_two_members(authenticated_client, admin_env, db_session):
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    users = []
    for name in ("pop_a", "pop_b"):
        user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
        db_session.add(user)
        users.append(user)
    db_session.flush()
    db_session.add_all([
        models.Movie(user_id=users[0].id, title="Arrival", year=2016),
        models.Movie(user_id=users[1].id, title="arrival ", year=2016),
        models.Movie(user_id=users[0].id, title="Only Mine", year=2020),
    ])
    db_session.commit()
    titles = authenticated_client.get("/api/site-stats/overview").json()["popular_titles"]
    assert titles[0]["members"] == 2 and titles[0]["title"].strip().lower() == "arrival"
    assert all(item["title"] != "Only Mine" for item in titles)


# ---------------------------------------------------------------- traffic counting

def test_should_count_only_human_html_page_views():
    assert should_count(make_request("/release-radar"), 200, "text/html; charset=utf-8")
    assert not should_count(make_request("/release-radar"), 404, "text/html")
    assert not should_count(make_request("/movies/"), 200, "application/json")
    assert not should_count(make_request("/", method="POST"), 200, "text/html")
    for path in ("/api/x", "/static/site.css", "/site-stats", "/auth/verify-email"):
        assert not should_count(make_request(path), 200, "text/html")
    for agent in ("Googlebot/2.1", "curl/8.0", "python-httpx/0.27", "Render/1.0", "HeadlessChrome/120", ""):
        assert not should_count(make_request("/", headers={"User-Agent": agent}), 200, "text/html")
    assert not should_count(make_request("/", headers={"Sec-Purpose": "prefetch"}), 200, "text/html")


def test_traffic_sources():
    assert traffic_source(make_request("/")) == "(direct)"
    assert traffic_source(make_request("/", headers={"Referer": "https://www.google.com/search?q=x"})) == "google.com"
    assert traffic_source(make_request("/", headers={"Referer": "https://omnitrackr.xyz/reviews"})) is None
    assert traffic_source(make_request("/", headers={"Referer": "https://www.omnitrackr.xyz/"})) is None
    assert traffic_source(make_request("/", query="utm_source=Newsletter", headers={"Referer": "https://mail.example"})) == "newsletter"


def test_device_classification():
    assert classify_device("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148") == "mobile"
    assert classify_device("Mozilla/5.0 (iPad; CPU OS 17_0)") == "tablet"
    assert classify_device(BROWSER_UA) == "desktop"


def test_recorder_buffers_then_writes_daily_counters(db_session):
    recorder = TrafficRecorder(session_factory=TestingSessionLocal)
    recorder.enabled = True
    html = "text/html; charset=utf-8"
    recorder.record(make_request("/", headers={"Referer": "https://www.google.com/"}), 200, html)
    recorder.record(make_request("/reviews/", headers={"Referer": "https://omnitrackr.xyz/"}), 200, html)
    recorder.record(make_request("/reviews", client=("198.51.100.4", 1)), 200, html)
    recorder.record(make_request("/faq", cookies={"omnitrackr_session": "x"}), 200, html)
    recorder.record(make_request("/faq", headers={"User-Agent": "Googlebot"}), 200, html)  # ignored
    assert db_session.query(models.SiteTrafficDaily).count() == 0  # buffered, not yet written
    assert recorder.flush() > 0

    def count(kind, key):
        row = db_session.query(models.SiteTrafficDaily).filter_by(kind=kind, key=key).one_or_none()
        return row.count if row else 0

    db_session.expire_all()
    assert count("total", "views") == 4
    assert count("total", "visitors") == 2  # same IP + UA counted once per day
    assert count("page", "/reviews") == 2  # trailing slash normalised
    assert count("source", "google.com") == 1
    assert count("source", "(direct)") == 2
    assert count("audience", "member") == 1 and count("audience", "guest") == 3
    assert count("device", "desktop") == 4

    recorder.record(make_request("/"), 200, html)
    recorder.flush()
    db_session.expire_all()
    assert count("total", "views") == 5
    assert count("total", "visitors") == 2
    # Nothing identifying is stored.
    keys = {row.key for row in db_session.query(models.SiteTrafficDaily).all()}
    assert not any("203.0.113" in key or "Mozilla" in key for key in keys)


def test_recorder_is_off_in_tests_and_respects_the_switch(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.delenv("SITE_TRAFFIC_TRACKING", raising=False)
    assert TrafficRecorder().enabled is False
    monkeypatch.setenv("SITE_TRAFFIC_TRACKING", "on")
    assert TrafficRecorder().enabled is True
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("SITE_TRAFFIC_TRACKING", "off")
    assert TrafficRecorder().enabled is False


def test_disabled_recorder_counts_nothing():
    recorder = TrafficRecorder()
    recorder.enabled = False
    assert recorder.record(make_request("/"), 200, "text/html") is False
    assert recorder.flush() == 0


def test_middleware_counts_real_page_loads_without_changing_them(client, db_session, monkeypatch):
    recorder = TrafficRecorder(session_factory=TestingSessionLocal)
    recorder.enabled = True
    monkeypatch.setattr(site_traffic, "RECORDER", recorder)
    response = client.get("/faq", headers={"User-Agent": BROWSER_UA, "Accept": "text/html"})
    assert response.status_code == 200
    client.get("/api/public/reviews", headers={"User-Agent": BROWSER_UA})
    recorder.flush()
    rows = {(row.kind, row.key): row.count for row in db_session.query(models.SiteTrafficDaily).all()}
    assert rows[("page", "/faq")] == 1
    assert rows[("total", "views")] == 1


def test_traffic_table_is_new_and_separate():
    table = models.SiteTrafficDaily.__table__
    assert table.name == "site_traffic_daily"
    assert not any(fk for column in table.columns for fk in column.foreign_keys)


# ---------------------------------------------------------------- dashboard link

def test_dashboard_link_is_hidden_until_the_server_confirms_admin():
    index = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    app_js = dashboard_assets.full_source()
    auth_js = (ROOT / "app" / "static" / "auth.js").read_text(encoding="utf-8")
    assert '<a id="siteStatsLink" class="site-stats-link" href="/site-stats" hidden>' in index
    assert "/api/site-stats/access" in app_js
    assert "window.refreshSiteStatsLink?.();" in auth_js
    assert auth_js.count("window.resetSiteStatsLink?.();") == 2


def test_site_stats_paths_are_not_blocked_by_the_bot_filter(client):
    # The bot filter blocks anything containing "/admin", so the page lives at /site-stats.
    assert client.get("/site-stats").status_code == 200


# ---------------------------------------------------------------- likely people

def test_scanner_tags_are_not_stored_as_written():
    payload = "'>\"></script><svg/onload=confirm('xsss-utm_source18')>"
    assert traffic_source(make_request("/", query=f"utm_source={payload}")) == site_traffic.BAD_TAG
    assert site_traffic.source_for("Ko-fi Newsletter", "") == "ko-fi newsletter"
    assert site_traffic.source_for("", "https://www.reddit.com/r/movies") == "reddit.com"


def test_page_reports_count_people_and_skip_bots_reloads_and_crawlers(db_session, monkeypatch):
    recorder = TrafficRecorder(session_factory=TestingSessionLocal)
    recorder.enabled = True
    now = [1000.0]
    monkeypatch.setattr(site_traffic.time, "monotonic", lambda: now[0])
    same_site = {"Sec-Fetch-Site": "same-origin"}
    assert recorder.record_person(make_request("/api/visit", method="POST", headers=same_site), "/", "", "Reddit")
    assert not recorder.record_person(make_request("/api/visit", method="POST", headers=same_site), "/", "", "")  # reload
    now[0] += site_traffic.HUMAN_REPEAT_SECONDS + 1
    assert recorder.record_person(make_request("/api/visit", method="POST", headers=same_site), "/", "", "")
    assert recorder.record_person(make_request("/api/visit", method="POST"), "/reviews/", "https://omnitrackr.xyz/", "")
    # Not people: a bot, another site posting in, a Googlebot address, odd paths.
    assert not recorder.record_person(make_request("/api/visit", method="POST", headers={"User-Agent": "HeadlessChrome/120"}), "/faq")
    assert not recorder.record_person(make_request("/api/visit", method="POST", headers={"Sec-Fetch-Site": "cross-site"}), "/faq")
    assert not recorder.record_person(make_request("/api/visit", method="POST", client=("66.249.66.1", 1)), "/faq")
    assert not recorder.record_person(make_request("/api/visit", method="POST", headers={"True-Client-IP": "66.249.66.1"}), "/faq")
    for path in ("faq", "//evil.example/x", "/api/x", "/static/site.css"):
        assert not recorder.record_person(make_request("/api/visit", method="POST", client=("198.51.100.7", 1)), path)
    recorder.flush()
    db_session.expire_all()
    rows = {(row.kind, row.key): row.count for row in db_session.query(models.SiteTrafficDaily).all()}
    assert rows[("human_total", "views")] == 3 and rows[("human_total", "visitors")] == 1
    assert rows[("human_page", "/")] == 2 and rows[("human_page", "/reviews")] == 1
    assert rows[("human_source", "reddit")] == 1 and rows[("human_source", "(direct)")] == 1
    assert rows[("human_device", "desktop")] == 3 and rows[("human_audience", "guest")] == 3
    assert rows[("funnel", "landing_seen")] == 1  # once per person per day
    # The all-requests counters are untouched by page reports.
    assert ("total", "views") not in rows
    assert not any("198.51" in key or "Mozilla" in key for _, key in rows)


def test_one_person_cannot_flood_the_people_counts(monkeypatch):
    recorder = TrafficRecorder()
    recorder.enabled = True
    clock = [0.0]
    monkeypatch.setattr(site_traffic.time, "monotonic", lambda: clock[0])
    counted = 0
    for index in range(site_traffic.HUMAN_MAX_VIEWS_PER_DAY + 20):
        clock[0] += 1
        counted += recorder.record_person(make_request("/api/visit", method="POST"), f"/titles/movie/x-{index}")
    assert counted == site_traffic.HUMAN_MAX_VIEWS_PER_DAY


def test_members_on_the_homepage_are_not_counted_as_landing_visitors():
    recorder = TrafficRecorder()
    recorder.enabled = True
    assert recorder.record_person(make_request("/api/visit", method="POST", cookies={"omnitrackr_session": "x"}), "/")
    assert not any(key == "landing_seen" for (_, kind, key) in recorder._pending if kind == "funnel")
    assert any(kind == "human_audience" and key == "member" for (_, kind, key) in recorder._pending)


def test_visit_endpoint_feeds_the_recorder_and_never_fails(client, monkeypatch):
    recorder = TrafficRecorder(session_factory=TestingSessionLocal)
    recorder.enabled = True
    monkeypatch.setattr(site_traffic, "RECORDER", recorder)
    from app.routers import site_stats
    monkeypatch.setattr(site_stats, "RECORDER", recorder)
    headers = {"User-Agent": BROWSER_UA}
    assert client.post("/api/visit", json={"path": "/reviews", "referrer": "", "utm": ""}, headers=headers).status_code == 204
    assert client.post("/api/visit", json={"path": "x" * 400}, headers=headers).status_code == 422
    assert client.post("/api/visit", json={"path": "/faq"}, headers={"User-Agent": "curl/8"}).status_code == 204
    pages = {key for (_, kind, key) in recorder._pending if kind == "human_page"}
    assert pages == {"/reviews"}


def test_public_pages_and_the_dashboard_load_the_visit_report(client):
    assert '/static/visit.js?v=' in client.get("/").text
    assert '/static/visit.js?v=' in client.get("/faq").text
    assert '/static/visit.js?v=' in (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app" / "static" / "visit.js").read_text(encoding="utf-8")
    assert "navigator.webdriver" in script and "visibilityState" in script and "/api/visit" in script


def test_overview_splits_people_from_all_requests(authenticated_client, admin_env, db_session):
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    today = date.today()
    db_session.add_all([
        models.SiteTrafficDaily(day=today, kind="total", key="views", count=500),
        models.SiteTrafficDaily(day=today, kind="total", key="visitors", count=400),
        models.SiteTrafficDaily(day=today, kind="source", key="(direct)", count=380),
        models.SiteTrafficDaily(day=today, kind="human_total", key="views", count=30),
        models.SiteTrafficDaily(day=today, kind="human_total", key="visitors", count=12),
        models.SiteTrafficDaily(day=today, kind="human_source", key="google.com", count=9),
        models.SiteTrafficDaily(day=today, kind="human_page", key="/", count=20),
    ])
    db_session.commit()
    traffic = authenticated_client.get("/api/site-stats/overview?days=30").json()["traffic"]
    assert traffic["totals"] == {"views": 500, "visitors": 400}  # all requests, as before
    assert traffic["sources"] == [{"key": "(direct)", "count": 380}]
    human = traffic["human"]
    assert human["totals"] == {"views": 30, "visitors": 12} and human["tracking_since"] == today.isoformat()
    assert human["sources"] == [{"key": "google.com", "count": 9}] and human["top_pages"] == [{"key": "/", "count": 20}]
    assert len(human["series"]) == 30


def test_site_stats_page_renders_sources_as_text_only():
    script = (ROOT / "app" / "static" / "site-stats.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script and "outerHTML" not in script
