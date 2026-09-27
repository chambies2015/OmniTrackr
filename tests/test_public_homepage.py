"""The anonymous homepage: structure, live Release Radar strip, and graceful fallbacks."""
import re
from datetime import date
from html.parser import HTMLParser

from app import release_radar as radar
from app.routers import release_radar as radar_routes
from tests.release_radar_fixtures import install_fixture_providers

TODAY = date(2026, 9, 27)


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def warm_fixture_cache(client, monkeypatch):
    install_fixture_providers(today=TODAY, monkeypatch=monkeypatch)
    for path in ("/release-radar/movies/2026-10", "/release-radar/tv", "/release-radar/anime", "/release-radar/games"):
        assert client.get(path).status_code == 200


def test_homepage_keeps_auth_and_navigation_contracts(client):
    html = client.get("/").text
    tags = Tags(html).tags
    ids = {attrs.get("id") for _, attrs in tags}
    for required in ("landingPage", "landing-auth", "authTitle", "authError", "authSuccess", "loginForm", "registerForm",
                     "forgotPasswordForm", "resetPasswordForm", "resendVerificationContainer", "loginFormElement",
                     "registerFormElement", "showRegister", "showForgotPassword"):
        assert required in ids, required
    assert sum(1 for tag, _ in tags if tag == "h1") == 1
    assert any(a.get("data-action") == "show-register-form" for _, a in tags)
    menu = html[html.index('<details class="lp-menu">'):html.index("</details>")]
    for href in ("/release-radar", "/discover", "/reviews", "/collections/explore", "/guides", "/faq"):
        assert f'href="{href}"' in menu
    assert 'data-action="show-login-form"' in menu


def test_hero_vortex_respects_reduced_motion(client):
    html = client.get("/").text
    assert '<source srcset="/vortex-still.webp" media="(prefers-reduced-motion: reduce)">' in html
    assert '<img src="/vortex.webp"' in html
    assert "/vortex.gif" not in html  # the 12 MB original is never requested by the homepage


def test_footer_links_cover_public_site(client):
    html = client.get("/").text
    footer = html[html.index('<footer'):html.index('</footer>')]
    for href in ("/release-radar", "/discover", "/reviews", "/guides", "/faq", "/about", "/contact", "/privacy",
                 "/terms", "/advertising", "https://ko-fi.com/omnitrackr"):
        assert f'href="{href}"' in footer, href


def test_radar_strip_hidden_until_data_is_cached(client):
    html = client.get("/").text
    assert "<!--RELEASE_RADAR_STRIP-->" not in html
    assert "Coming out soon" not in html


def test_radar_strip_shows_upcoming_titles(client, monkeypatch):
    warm_fixture_cache(client, monkeypatch)
    html = client.get("/").text
    strip = html[html.index('class="lp-section lp-radar"'):]
    strip = strip[:strip.index("</section>")]
    cards = re.findall(r'<a class="lp-radar-card" href="([^"]+)"', strip)
    assert 4 <= len(cards) <= radar_routes.HOME_STRIP_MAX
    assert all(href.startswith("/release-radar/") and "#item-" in href for href in cards)
    assert "Coming out soon" in strip and 'href="/release-radar"' in strip
    categories = re.findall(r'lp-radar-card__type">(\w+)<', strip)
    assert max(categories.count(label) for label in set(categories)) <= 3
    dates = re.findall(r'<time datetime="([\d-]+)"', strip)
    assert dates == sorted(dates) and all(TODAY.isoformat() <= d for d in dates)
    assert "<script>" not in strip


def test_radar_strip_skips_past_and_far_future_titles(monkeypatch):
    install_fixture_providers(today=TODAY, monkeypatch=monkeypatch)
    items = [
        radar.make_item(category="games", key=f"rawg-{n}", title=f"Game {n}", release_date=day, source_url=None, popularity=100 - n)
        for n, day in enumerate(["2026-09-20", "2026-09-28", "2026-10-02", "2026-10-10", "2026-10-30", "2026-11-20"])
    ]
    for item in items:
        item["window"] = "2026-10"
    cache = radar.RadarCache(None)
    cache.entries[radar.month_window("games", 2026, 10).cache_key] = {"items": items, "fetched_at": 9e12, "error": None}
    monkeypatch.setattr(radar, "CACHE", cache)
    chosen = radar_routes.home_strip_items(today=TODAY)
    assert [i["title"] for i in chosen] == ["Game 1", "Game 2", "Game 3"]  # 21-day window, max 3 per category
    assert radar_routes.home_strip_html(today=TODAY) == ""  # fewer than 4 titles: no strip


def test_homepage_survives_a_broken_strip(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(radar_routes, "home_strip_html", boom)
    response = client.get("/")
    assert response.status_code == 200
    assert "Remember more than" in response.text and "provider exploded" not in response.text


def test_landing_assets_are_versioned(client):
    html = client.get("/").text
    assert re.search(r'/static/public-landing\.css\?v=[\w-]+', html)
    assert re.search(r'/static/public-landing\.js\?v=[\w-]+', html)
    css = client.get("/static/public-landing.css").text
    assert "prefers-reduced-motion" in css and "body.lp" in css
