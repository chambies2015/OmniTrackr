"""The installed app (Nov 2026): install counters, members who open it from the icon, the /app page,
the self-contained offline page, iPhone launch screens and shortcut icons."""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import app_install, auth, models
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"}


@pytest.fixture(autouse=True)
def counters(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "app" and name == key)


def member(db, name="riley"):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True)
    db.add(user)
    db.commit()
    return user


def headers(user=None):
    extra = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"} if user is not None else {}
    return {**CHROME, **extra}


def event(client, name, user=None, **extra):
    return client.post("/api/app/event", headers=headers(user), json={"event": name, **extra})


# ---------------------------------------------------------------- counters

def test_whitelisted_events_count_and_others_are_ignored(client):
    for name in ("offer_sheet", "install_sheet", "steps_ios_safari", "later_card", "prompt_accepted", "installed"):
        assert event(client, name).status_code == 204
    assert event(client, "anything_else").status_code == 204
    assert event(client, "offer_" + "x" * 30).status_code == 204
    assert [counted(key) for key in ("offer_sheet", "install_sheet", "steps_ios_safari", "later_card",
                                      "prompt_accepted", "installed")] == [1] * 6
    assert counted("anything_else") == 0
    assert all(kind != "app" or name in app_install.CLIENT_EVENTS | {"shared_in"}
               for (_, kind, name) in RECORDER._pending)


def test_bots_are_not_counted(client):
    client.post("/api/app/event", headers={"User-Agent": "Googlebot/2.1"}, json={"event": "offer_card"})
    client.post("/api/app/event", headers={"User-Agent": "Mozilla/5.0 HeadlessChrome/130"}, json={"event": "offer_card"})
    assert counted("offer_card") == 0


def test_guest_open_counts_without_a_member_row(client, db_session):
    assert event(client, "opened", platform="android").status_code == 204
    assert counted("opened") == 1
    assert db_session.query(models.InstalledAppOpen).count() == 0


def test_member_opens_are_noted_once_a_day_with_each_kind_of_device(client, db_session):
    user = member(db_session)
    event(client, "opened", user, platform="ios")
    event(client, "opened", user, platform="ios")  # a second device the same day
    row = db_session.query(models.InstalledAppOpen).filter_by(user_id=user.id).one()
    assert (row.open_days, row.platforms, row.last_opened_on) == (1, "ios", date.today())
    assert counted("opened") == 2
    # A guest open that signed in later the same day: note the member, don't count the device twice.
    other = member(db_session, "ash")
    event(client, "opened", other, platform="android", repeat=True)
    assert counted("opened") == 2
    assert db_session.query(models.InstalledAppOpen).filter_by(user_id=other.id).one().platforms == "android"
    # The next day on a computer adds the platform.
    assert app_install.record_open(db_session, user, "desktop", today=date.today() + timedelta(days=1)) is True
    db_session.refresh(row)
    assert (row.open_days, row.platforms) == (2, "desktop,ios")
    assert app_install.record_open(db_session, user, "nonsense", today=date.today() + timedelta(days=2)) is True
    db_session.refresh(row)
    assert row.platforms == "desktop,ios"


def test_status_says_which_devices_a_member_uses_and_nothing_for_guests(client, db_session):
    user = member(db_session)
    assert client.get("/api/app/status", headers=headers()).json() == {"platforms": []}
    assert client.get("/api/app/status", headers=headers(user)).json() == {"platforms": []}
    event(client, "opened", user, platform="ios")
    response = client.get("/api/app/status", headers=headers(user))
    assert response.json() == {"platforms": ["ios"]}
    assert response.headers["Cache-Control"] == "private, no-store"


def test_share_target_counts_shares(client):
    response = client.get("/share", params={"text": "Dune https://www.imdb.com/title/tt15239678/"}, headers=CHROME,
                          follow_redirects=False)
    assert response.status_code == 303
    assert counted("shared_in") == 1


def test_site_stats_block(db_session):
    user = member(db_session)
    other = member(db_session, "ash")
    now = datetime.utcnow()
    app_install.record_open(db_session, user, "ios")
    app_install.record_open(db_session, other, "android", today=(now - timedelta(days=20)).date())
    old = db_session.query(models.InstalledAppOpen).filter_by(user_id=other.id).one()
    old.first_opened_at = now - timedelta(days=40)
    for key, amount in (("offer_sheet", 5), ("install_sheet", 2), ("later_sheet", 1), ("steps_ios_safari", 2),
                        ("prompt_accepted", 1), ("opened", 9)):
        db_session.add(models.SiteTrafficDaily(day=now.date(), kind="app", key=key, count=amount))
    db_session.add(models.SiteTrafficDaily(day=(now - timedelta(days=60)).date(), kind="app", key="offer_sheet", count=50))
    db_session.commit()
    stats = app_install.stats(db_session, 30, now)
    assert (stats["members"], stats["members_7d"], stats["members_range"], stats["new_members"]) == (2, 1, 2, 1)
    assert stats["by_platform"] == [{"platform": "iPhone and iPad", "count": 1}, {"platform": "Android", "count": 1},
                                    {"platform": "computers", "count": 0}]
    sheet = next(row for row in stats["offers"] if row["place"] == app_install.PLACES["sheet"])
    assert (sheet["shown"], sheet["pressed"], sheet["later"]) == (5, 2, 1)
    assert {"browser": app_install.STEPS["ios_safari"], "count": 2} in stats["steps"]
    outcomes = {row["label"]: row["count"] for row in stats["outcomes"]}
    assert outcomes[app_install.OUTCOMES["opened"]] == 9 and outcomes[app_install.OUTCOMES["prompt_accepted"]] == 1


def test_site_stats_page_lists_the_block():
    html = Path("app/templates/site_stats.html").read_text(encoding="utf-8")
    assert 'id="growthApp"' in html
    js = Path("app/static/site-stats.js").read_text(encoding="utf-8")
    assert "growthApp: [" in js and "growthApp: 'The app on home screens'" in js


def test_removing_a_member_removes_their_app_row(db_session):
    user = member(db_session)
    app_install.record_open(db_session, user, "ios")
    column = models.InstalledAppOpen.__table__.c.user_id
    assert next(iter(column.foreign_keys)).ondelete == "CASCADE"


# ---------------------------------------------------------------- pages and files

def test_dashboard_dialog_has_steps_for_every_browser(authenticated_client):
    html = authenticated_client.get("/").text
    assert app_install.STEPS_MARKER not in html
    for route, heading, _steps in app_install.STEP_GUIDES:
        assert f'data-install-steps="{route}" data-install-title="{heading}"' in html
    assert 'data-install-steps="ios_safari" data-install-title="Add OmniTrackr to your Home Screen">' in html
    assert 'data-install-steps="in_app" data-install-title="Open this page in your browser first" hidden>' in html
    assert 'id="installAppSheet" class="install-sheet" aria-labelledby="installAppSheetTitle" hidden' in html
    assert "data-install-copy-link" in html


def test_app_page_explains_and_offers_the_install(client):
    response = client.get("/app")
    assert response.status_code == 200
    html = response.text
    assert "<h1 id=\"appPageTitle\">OmniTrackr on your home screen</h1>" in html
    assert 'data-install-app="page" hidden' in html and 'id="installAppDialog"' in html
    assert 'rel="manifest"' in html and "/static/pwa.js?v=" in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/app">' in html
    for heading in ("iPhone and iPad (Safari)", "Android", "Computers", "What you get", "Questions"):
        assert heading in html
    assert 'class="site-footer' in html and 'href="/app"' in html
    assert "content-security-policy" in {key.lower() for key in response.headers}


def test_offline_page_stands_alone_and_reloads_when_back_online(client):
    response = client.get("/offline")
    html = response.text
    assert response.status_code == 200 and "You're offline" in html
    assert "site.css" not in html  # stored by the worker on its own, so no outside stylesheet
    assert "addEventListener('online'" in html and "offline_seen" in html
    nonce = re.search(r"script-src[^;]*'nonce-([^']+)'", response.headers["content-security-policy"])
    assert nonce and f'nonce="{nonce.group(1)}"' in html
    worker = Path("app/static/sw.js").read_text(encoding="utf-8")
    assert "cache.addAll([new Request(OFFLINE_URL, { cache: 'reload' }), OFFLINE_ICON])" in worker
    assert "/static/icons/icon-192.png?v=20261003-pwa-1" in html and "OFFLINE_ICON = '/static/icons/icon-192.png?v=20261003-pwa-1'" in worker


def test_manifest_shortcuts_have_icons_and_add_a_title_comes_first(client):
    data = json.loads(client.get("/manifest.webmanifest").text)
    first = data["shortcuts"][0]
    assert first["name"] == "Add a title" and first["url"].startswith("/?find=")
    for shortcut in data["shortcuts"][:4]:
        assert shortcut["url"].endswith("utm_source=app_shortcut")
        icon = shortcut["icons"][0]
        response = client.get(icon["src"])
        assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert data["related_applications"][0]["platform"] == "webapp"
    assert data["prefer_related_applications"] is False


@pytest.mark.parametrize("template", ["index.html", "public_landing.html"])
def test_iphone_launch_screens_exist_for_every_link(client, template):
    html = Path(f"app/templates/{template}").read_text(encoding="utf-8")
    links = re.findall(r'<link rel="apple-touch-startup-image" media="([^"]+)" href="([^"]+)">', html)
    assert len(links) == 13
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in html
    for media, href in links:
        width, height, ratio = map(int, re.search(r"device-width: (\d+)px\) and \(device-height: (\d+)px\) and "
                                                  r"\(-webkit-device-pixel-ratio: (\d+)\)", media).groups())
        assert f"launch-{width * ratio}x{height * ratio}.png" in href
        assert client.get(href).status_code == 200
