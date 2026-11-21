"""Search visitors (Nov 18 2026): landing-section counters, the keep-your-list sheet marker, Discover guest saves."""
from datetime import date
from pathlib import Path

import pytest

from app import funnel, guest_signup, html_finish, models, search_journey, site_traffic
from app.discover_catalog import TRAILS, find_guest_pick, guest_fields, published_editions
from app.site_traffic import RECORDER, TrafficRecorder
from tests.test_google_signin import _sign_in, google  # noqa: F401  (fixture)
from tests.test_site_stats import BROWSER_UA, admin_env, make_request  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def journey(recorder) -> dict:
    return {key: count for (_, kind, key), count in recorder._pending.items() if kind == search_journey.KIND}


# ---------------------------------------------------------------- sections and hosts

@pytest.mark.parametrize("value, section", [
    ("/in-order/star-wars", "in-order"), ("in-order", "in-order"), ("/binge-calculator/naruto", "binge-calculator"),
    ("/titles/movie/inception-2010", "titles"), ("/movie-tracker", "trackers"), ("anime-tracker", "trackers"),
    ("/", "home"), ("home", "home"), ("/halloween", "holidays"), ("/release-radar/games", "new-releases"),
    ("/u/dan", "other"), ("/nope", "other"), ("<script>", "other"), ("/discover/monthly/november-2026", "discover"),
])
def test_landing_sections(value, section):
    assert search_journey.section_for(value) == section


@pytest.mark.parametrize("host, expected", [
    ("google.com", True), ("google.co.uk", True), ("bing.com", True), ("duckduckgo.com", True), ("search.brave.com", True),
    ("reddit.com", False), ("notgoogle.example", False), ("google.com.evil.example", False), (None, False), ("(direct)", False),
])
def test_search_hosts(host, expected):
    assert search_journey.is_search(host) is expected


# ---------------------------------------------------------------- counting

def test_a_search_landing_is_counted_by_section_for_guests_only():
    recorder = TrafficRecorder()
    recorder.enabled = True
    assert recorder.record_person(make_request("/api/visit", method="POST"), "/in-order/star-wars", "https://www.google.com/", "")
    assert recorder.record_person(make_request("/api/visit", method="POST", client=("198.51.100.4", 1)), "/faq", "https://reddit.com/", "")
    assert recorder.record_person(make_request("/api/visit", method="POST", client=("198.51.100.5", 1),
                                               cookies={"omnitrackr_session": "x"}), "/in-order/dune", "https://www.bing.com/", "")
    assert journey(recorder) == {"in-order|landed": 1}


def test_later_steps_follow_the_landing_cookie(recorder):
    cookie = {search_journey.COOKIE: "binge-calculator"}
    assert funnel.record("guest_pick_added", make_request("/api/funnel", method="POST", cookies=cookie))
    assert funnel.record("signup_form_opened", make_request("/api/funnel", method="POST", cookies=cookie))
    assert funnel.record("signup_created", make_request("/auth/register", method="POST", cookies=cookie))
    # No cookie, a member, or an event that is not a step: nothing more.
    funnel.record("guest_pick_added", make_request("/api/funnel", method="POST"))
    funnel.record("guest_pick_added", make_request("/api/funnel", method="POST", cookies={**cookie, "omnitrackr_session": "x"}))
    funnel.record("share_clicked", make_request("/api/funnel", method="POST", cookies=cookie))
    assert journey(recorder) == {"binge-calculator|saved": 1, "binge-calculator|signup": 1, "binge-calculator|account": 1}


def test_odd_cookie_values_fold_into_other(recorder):
    funnel.record("guest_pick_added", make_request("/api/funnel", method="POST", cookies={search_journey.COOKIE: "x" * 41}))
    funnel.record("guest_pick_added", make_request("/api/funnel", method="POST", cookies={search_journey.COOKIE: "wp-admin"}))
    assert journey(recorder) == {"other|saved": 1}


def test_email_sign_up_from_a_search_landing_counts_an_account(client, recorder):
    client.cookies.set(search_journey.COOKIE, "if-you-liked")
    response = client.post("/auth/register", json={"email": "fan@example.com", "username": "searchfan", "password": "tea on the porch"})
    assert response.status_code == 201
    assert journey(recorder) == {"if-you-liked|account": 1}


def test_google_sign_up_from_a_search_landing_counts_an_account(client, google, recorder):  # noqa: F811
    client.cookies.set(search_journey.COOKIE, "titles")
    assert _sign_in(client, google).status_code == 303
    assert journey(recorder) == {"titles|account": 1}


def test_the_sheet_events_are_accepted_from_browsers():
    for event in ("guest_sheet_opened", "guest_sheet_google", "guest_sheet_email", "guest_sheet_login", "guest_return_clicked"):
        assert event in funnel.CLIENT_EVENTS and event in funnel.SERVER_EVENTS


# ---------------------------------------------------------------- Site stats

def test_summary_totals_and_rows():
    data = search_journey.summary({"in-order|landed": 5, "in-order|saved": 2, "titles|landed": 9, "titles|account": 1,
                                   "nonsense|landed": 7})
    assert [step["count"] for step in data["steps"]] == [14, 2, 0, 1]
    assert [row["section"] for row in data["sections"]] == ["titles", "in-order"]
    assert data["sections"][1] == {"section": "in-order", "label": "In order guides", "landed": 5, "saved": 2, "signup": 0, "account": 0}


def test_site_stats_overview_includes_search_visitors(authenticated_client, admin_env, db_session):  # noqa: F811
    admin_env.setenv("ADMIN_USERNAMES", "testuser")
    today = date.today()
    db_session.add_all([
        models.SiteTrafficDaily(day=today, kind="search_journey", key="in-order|landed", count=12),
        models.SiteTrafficDaily(day=today, kind="search_journey", key="in-order|saved", count=3),
        models.SiteTrafficDaily(day=today, kind="search_journey", key="discover|account", count=1),
    ])
    db_session.commit()
    data = authenticated_client.get("/api/site-stats/overview?days=30").json()["search_journey"]
    assert [step["count"] for step in data["steps"]] == [12, 3, 0, 1]
    assert {row["section"] for row in data["sections"]} == {"in-order", "discover"}
    page = (ROOT / "app" / "templates" / "site_stats.html").read_text(encoding="utf-8")
    assert 'id="searchJourney"' in page and 'id="searchJourneySections"' in page


# ---------------------------------------------------------------- the sheet marker

def test_pages_with_a_save_bar_get_the_sheet(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    page = client.get("/in-order/star-wars").text
    assert '<body data-guest-sheet="email"' in page
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    assert '<body data-guest-sheet="google"' in client.get("/binge-calculator/breaking-bad").text
    # The homepage has the sign-up form itself; pages without saves are left alone.
    assert "data-guest-sheet" not in client.get("/").text
    assert "data-guest-sheet" not in client.get("/faq").text


def test_sheet_marker_is_added_once():
    html = '<html><body class="x"><div data-guest-bar></div></body></html>'
    once = html_finish.finish(html)
    assert once.count("data-guest-sheet") == 1 and guest_signup.mark_guest_pages(once) == once
    assert guest_signup.mark_guest_pages('<body><form id="registerForm"></form><i data-guest-save></i></body>').count("data-guest-sheet") == 0


# ---------------------------------------------------------------- Discover guest saves

def test_every_discover_pick_has_a_unique_guest_slug():
    seen = set()
    for trail in (*TRAILS.values(), *published_editions().values()):
        for item in trail["items"]:
            fields = guest_fields(item)
            assert fields is not None
            key = (fields["kind"], fields["slug"])
            assert key not in seen
            seen.add(key)
            found = find_guest_pick(*key)
            assert found["title"] == item["title"] and found["kind"] == fields["kind"]


def test_discover_pages_offer_guest_saves(client):
    slug = next(iter(published_editions()))
    for path in (f"/discover/monthly/{slug}", f"/discover/{next(iter(TRAILS))}"):
        page = client.get(path).text
        assert page.count("data-guest-save") >= 4 and "data-guest-bar" in page and "/static/guest-list.js?v=" in page
        assert "No account yet?" in page


def test_discover_picks_move_into_a_new_library(authenticated_client, db_session):
    item = next(iter(published_editions().values()))["items"][0]
    fields = guest_fields(item)
    result = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]}).json()
    assert [entry["title"] for entry in result["added"]] == [item["title"]] and result["missing"] == 0
    again = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]}).json()
    assert again["added"] == [] and len(again["existing"]) == 1


def test_privacy_policy_names_the_search_cookie(client):
    assert search_journey.COOKIE in client.get("/privacy").text
    assert search_journey.COOKIE in (ROOT / "app" / "static" / "visit.js").read_text(encoding="utf-8")
