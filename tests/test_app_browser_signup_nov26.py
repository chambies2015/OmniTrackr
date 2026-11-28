"""Sign-up from inside Instagram, TikTok and other apps' browsers, and phones in Site stats (Nov 26 2026).

Google refuses to sign anyone in inside an app's built-in browser ("403 disallowed_useragent"),
and Google is how every account so far was made. Continue with Google there now opens /continue,
which explains and hands the sign-up, with the visitor's saved titles, to Safari or Chrome.
Site stats also splits the sign-up steps by phone, and counts people reading inside apps.
"""
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app import app_browsers, continue_page, funnel, models
from app.site_traffic import RECORDER

ROOT = Path(__file__).resolve().parents[1]

IG_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Mobile/15E148 Instagram 357.0.0.25.101 (iPhone15,3; iOS 18_1; en_US; en; scale=3.00; 1290x2796; 654321)")
FB_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Mobile/15E148 [FBAN/FBIOS;FBAV/470.0.0.40.98;FBBV/612345;FBDV/iPhone14,5;FBMD/iPhone;FBSN/iOS;FBSV/17.5]")
MESSENGER = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Mobile/15E148 LightSpeed [FBAN/MessengerLiteForiOS;FBAV/460.0.0.29.106;FBDV/iPhone13,2]")
TIKTOK_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240805.005; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36 trill_360105 AppName/musical_ly "
                  "BytedanceWebview/d8a21c6")
SNAPCHAT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Mobile/15E148 Snapchat/13.0.0.40 (like Safari/8618.1.15.10.15, panda)")
LINKEDIN = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Mobile/15E148 [LinkedInApp]/9.29.6730")
ANDROID_WEBVIEW = ("Mozilla/5.0 (Linux; Android 13; SM-S911B Build/TP1A.220624.014; wv) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Version/4.0 Chrome/127.0.6533.103 Mobile Safari/537.36")
SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/18.1 Mobile/15E148 Safari/604.1")
CHROME_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1")
CHROME_ANDROID = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Mobile Safari/537.36")
SAMSUNG = ("Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
           "SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36")
DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/131.0.0.0 Safari/537.36")
PINTEREST_CRAWLER = "Pinterest/0.2 (+https://www.pinterest.com/bot.html)"
INVITE = "abcdefghijklmnop1234"


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://omnitrackr.xyz/auth/google/callback")


@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(kind, key):
    return sum(count for (day, k, name), count in RECORDER._pending.items() if k == kind and name == key)


# ---------------------------------------------------------------- telling app browsers apart

@pytest.mark.parametrize("agent, name", [
    (IG_IOS, "Instagram"), (FB_IOS, "Facebook"), (MESSENGER, "Messenger"), (TIKTOK_ANDROID, "TikTok"),
    (SNAPCHAT, "Snapchat"), (LINKEDIN, "LinkedIn"), (ANDROID_WEBVIEW, app_browsers.OTHER_APP),
])
def test_apps_browsers_are_named(agent, name):
    assert app_browsers.app_name(agent) == name


@pytest.mark.parametrize("agent", [SAFARI, CHROME_IOS, CHROME_ANDROID, SAMSUNG, DESKTOP, PINTEREST_CRAWLER, "", None])
def test_real_browsers_are_left_alone(agent):
    assert app_browsers.app_name(agent) is None


def test_platform_picks_the_steps():
    assert app_browsers.platform(IG_IOS) == "ios"
    assert app_browsers.platform(TIKTOK_ANDROID) == "android"
    assert app_browsers.platform(DESKTOP) == "other"
    assert app_browsers.is_phone(IG_IOS) and not app_browsers.is_phone(DESKTOP)


# ---------------------------------------------------------------- Continue with Google inside an app

def test_google_inside_an_app_opens_the_continue_page(client, google, recorder):
    response = client.get(f"/auth/google/start?invite={INVITE}", follow_redirects=False,
                          headers={"user-agent": IG_IOS, "referer": "http://testserver/in-order/star-wars"})
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert location.path == "/continue"
    assert parse_qs(location.query) == {"from": ["/in-order/star-wars"], "invite": [INVITE]}
    assert "no-store" in response.headers["cache-control"]
    # No state cookie: nobody went to Google.
    assert "omnitrackr_google_state" not in response.headers.get("set-cookie", "")
    assert counted("funnel", "inapp_google_caught") == 1
    assert counted(funnel.PHONE_KIND, "inapp_google_caught") == 1
    assert counted("funnel", "google_signin_started") == 0


def test_try_google_here_anyway_goes_to_google(client, google, recorder):
    response = client.get(f"/auth/google/start?invite={INVITE}&here=1", follow_redirects=False,
                          headers={"user-agent": IG_IOS})
    assert response.status_code == 303
    assert response.headers["location"].startswith("https://accounts.google.com/")
    assert counted("funnel", "inapp_google_anyway") == 1


@pytest.mark.parametrize("agent", [SAFARI, CHROME_ANDROID, DESKTOP])
def test_real_browsers_still_go_straight_to_google(client, google, agent):
    response = client.get("/auth/google/start", follow_redirects=False, headers={"user-agent": agent})
    assert response.headers["location"].startswith("https://accounts.google.com/")


def test_a_strange_invite_or_referer_is_dropped(client, google):
    response = client.get("/auth/google/start?invite=<script>", follow_redirects=False,
                          headers={"user-agent": IG_IOS, "referer": "https://evil.example/in-order/star-wars"})
    assert response.headers["location"] == "/continue"


def test_unconfigured_google_keeps_its_old_answer_inside_apps(client):
    response = client.get("/auth/google/start", follow_redirects=False, headers={"user-agent": IG_IOS})
    assert response.headers["location"] == "/?google_error=unavailable#landing-auth"


# ---------------------------------------------------------------- the /continue page

def test_inside_an_app_the_page_explains_and_offers_email(client, google):
    response = client.get(f"/continue?from=/in-order/star-wars&invite={INVITE}", headers={"user-agent": IG_IOS})
    assert response.status_code == 200
    page = response.text
    assert "Finish in Safari" in page
    assert "Google doesn't allow sign-ins inside Instagram's built-in browser" in page
    assert 'data-continue="app"' in page and 'data-platform="ios"' in page
    assert f'data-invite="{INVITE}"' in page and 'data-from="/in-order/star-wars"' in page
    assert "Open in browser" in page and "data-copy-link" in page
    assert 'href="/#signup" data-continue-email' in page and 'href="/#login"' in page
    assert f'/auth/google/start?invite={INVITE}&amp;here=1' in page
    # No Chrome button on an iPhone.
    assert "data-open-chrome" not in page
    assert response.headers["cache-control"] == "private, no-store"
    assert "noindex" in response.headers["x-robots-tag"] and 'content="noindex, follow"' in page
    # The phone "Start tracking" sheet stays off, so Sign up with email goes straight to the form.
    assert 'data-signup-sheet="off"' in page and 'data-signup-sheet="google"' not in page
    assert "/static/continue.js?v=" in page and "/static/guest-list.js?v=" in page


def test_android_apps_get_an_open_in_chrome_button(client, google):
    page = client.get("/continue", headers={"user-agent": TIKTOK_ANDROID}).text
    assert "Finish in Chrome" in page and "TikTok's built-in browser" in page
    assert 'href="intent://omnitrackr.xyz/continue?via=app#Intent;scheme=https;package=com.android.chrome;end"' in page


def test_an_unnamed_android_app_reads_naturally(client, google):
    page = client.get("/continue", headers={"user-agent": ANDROID_WEBVIEW}).text
    assert "inside this app's built-in browser" in page and "Email works inside this app" in page


def test_in_a_real_browser_the_page_offers_google_first(client, google):
    page = client.get(f"/continue?via=app&invite={INVITE}", headers={"user-agent": SAFARI}).text
    assert 'data-continue="browser"' in page
    assert "Now finish with one tap" in page
    assert f'href="/auth/google/start?invite={INVITE}" rel="nofollow" data-continue-google' in page
    assert "Sign up with email" in page and "Finish in Safari" not in page
    plain = client.get("/continue", headers={"user-agent": DESKTOP}).text
    assert "Make your free account" in plain


def test_without_google_set_up_the_page_offers_email(client):
    page = client.get("/continue", headers={"user-agent": IG_IOS}).text
    assert 'data-continue="browser"' in page
    assert "data-continue-google" not in page
    assert 'class="site-btn site-btn--primary continue-wide" href="/#signup"' in page


def test_a_signed_in_member_is_sent_to_their_library(client, google):
    client.cookies.set("omnitrackr_session", "anything")
    page = client.get("/continue", headers={"user-agent": SAFARI}).text
    assert 'data-continue="member"' in page and "Open your library" in page


@pytest.mark.parametrize("value", ["//evil.example/x", "/auth/google/start", "/continue", "/api/x", "/", "javascript:alert(1)",
                                   "/in-order/<b>", "https://omnitrackr.xyz/in-order/x"])
def test_only_plain_site_paths_are_linked_back_to(value):
    assert continue_page.from_path(value) is None


def test_referer_must_be_this_site():
    assert continue_page.referer_path("https://omnitrackr.xyz/in-order/star-wars?x=1", "omnitrackr.xyz") == "/in-order/star-wars"
    assert continue_page.referer_path("https://evil.example/in-order/star-wars", "omnitrackr.xyz") is None
    assert continue_page.referer_path("https://omnitrackr.xyz/", "omnitrackr.xyz") is None
    assert continue_page.referer_path(None, "omnitrackr.xyz") is None


# ---------------------------------------------------------------- counting phones and app browsers

def test_events_from_phones_are_also_counted_for_phones(client, recorder):
    client.post("/api/funnel", json={"event": "signup_form_opened"}, headers={"user-agent": SAFARI})
    client.post("/api/funnel", json={"event": "signup_form_opened"}, headers={"user-agent": DESKTOP})
    assert counted("funnel", "signup_form_opened") == 2
    assert counted(funnel.PHONE_KIND, "signup_form_opened") == 1


def test_the_page_reports_its_own_moments_but_not_the_servers():
    for event in ("inapp_chrome_opened", "inapp_link_copied", "inapp_email_chosen", "carry_arrived",
                  "carry_titles_moved", "continue_google", "continue_email"):
        assert event in funnel.CLIENT_EVENTS
    # Recorded by the server when Google is pressed; a browser can't add to them.
    assert "inapp_google_caught" not in funnel.CLIENT_EVENTS
    assert "inapp_google_anyway" not in funnel.CLIENT_EVENTS
    assert "inapp_google_caught" in funnel.SERVER_EVENTS


def test_summary_puts_phones_next_to_every_device():
    counts = {"landing_seen": 40, "signup_form_opened": 8, "signup_submitted": 2, "google_account_created": 3,
              "signup_created": 5, "inapp_google_caught": 4}
    phones = {"landing_seen": 10, "signup_form_opened": 2, "google_account_created": 1, "signup_created": 1}
    shaped = funnel.summary(counts, phones)
    rows = {row["event"]: row for row in shaped["phones"]}
    assert rows["landing_seen"]["count"] == 40 and rows["landing_seen"]["phones"] == 10
    assert rows["signup_sent"]["count"] == 5 and rows["signup_sent"]["phones"] == 1
    assert [item["count"] for item in shaped["app_browser"] if item["event"] == "inapp_google_caught"] == [4]
    # Older callers still work.
    assert funnel.summary(counts)["phones"][0]["phones"] == 0


def test_people_by_device_and_inside_apps_are_counted(client, recorder):
    for agent in (IG_IOS, SAFARI, DESKTOP):
        client.post("/api/visit", json={"path": "/in-order/star-wars"},
                    headers={"user-agent": agent, "sec-fetch-site": "same-origin"})
    devices = {key: count for (day, kind, key), count in RECORDER._pending.items() if kind == "human_people_device"}
    apps = {key: count for (day, kind, key), count in RECORDER._pending.items() if kind == "human_app"}
    assert devices.get("mobile") == 2 and devices.get("desktop") == 1
    assert apps == {"Instagram": 1}


def test_site_stats_reads_the_phone_counts(db_session):
    db = db_session
    from app.routers import site_stats
    today = date(2026, 11, 26)
    for kind, key, count in [("funnel", "landing_seen", 30), (funnel.PHONE_KIND, "landing_seen", 6),
                             ("human_people_device", "mobile", 9), ("human_people_device", "desktop", 21),
                             ("human_app", "Instagram", 3), ("funnel", "inapp_google_caught", 2)]:
        db.add(models.SiteTrafficDaily(day=today, kind=kind, key=key, count=count))
    db.commit()
    shaped = site_stats._funnel(db, 30, today)
    assert shaped["phones"][0] == {"event": "landing_seen", "label": "Homepage seen by a person", "count": 30, "phones": 6}
    assert shaped["people_devices"] == [{"key": "desktop", "count": 21}, {"key": "mobile", "count": 9}]
    assert shaped["app_browser_people"] == [{"key": "Instagram", "count": 3}]
    assert shaped["phones_since"] == "2026-11-26"


def test_site_stats_page_has_the_new_sections():
    template = (ROOT / "app/templates/site_stats.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/site-stats.js").read_text(encoding="utf-8")
    assert 'id="phoneFunnel"' in template and 'id="appBrowsers"' in template
    assert "renderPhones" in script and "phoneReport" in script
