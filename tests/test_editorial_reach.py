"""Public pages point readers at the written guides and speak to readers, not reviewers (Oct 17 2026)."""
from datetime import datetime, timedelta, timezone

import pytest

from app import daily, editorial_index, site_chrome, title_search
from app.discover_guides import GUIDES as DISCOVER_GUIDES
from app.if_you_liked_guides import GUIDES as LIKED_GUIDES
from app.in_order_guides import GUIDES as ORDER_GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def on_day(monkeypatch):
    """Pin "today" to puzzle number n (noon US Eastern)."""
    def pin(number):
        moment = datetime.combine(daily.date_for(number), datetime.min.time()) + timedelta(hours=17)
        fixed = moment.replace(tzinfo=timezone.utc)
        real = daily.now_local
        monkeypatch.setattr(daily, "now_local", lambda now=None: real(now or fixed))
    return pin


def header(html):
    return html[html.index('<header class="site-header">'):html.index("</header>")]


def test_editorial_index_lists_every_guide_newest_first():
    pieces = editorial_index.entries()
    assert len(pieces) == len(DISCOVER_GUIDES) + len(LIKED_GUIDES) + len(ORDER_GUIDES) + 2  # + monthly editions
    dates = [piece["updated"] for piece in pieces]
    assert dates == sorted(dates, reverse=True)
    latest = editorial_index.latest(6)
    assert len(latest) == 6 and len({piece["section"] for piece in latest}) == 4


def test_header_leads_with_the_guides(client):
    nav = header(client.get("/").text)
    for href in ("/discover", "/in-order", "/if-you-liked", "/daily"):
        assert f'href="{href}"' in nav
    assert 'href="/collections/explore"' not in nav
    assert [key for key, _, _ in site_chrome.NAV_ITEMS[:site_chrome.NAV_PRIMARY]] == ["discover", "in-order", "if-you-liked"]


@pytest.mark.parametrize("path, href", [("/in-order", "/in-order"), ("/in-order/star-wars", "/in-order"),
                                        ("/if-you-liked/interstellar", "/if-you-liked"), ("/daily", "/daily"),
                                        ("/discover", "/discover"), ("/pick", "/discover")])
def test_each_section_marks_its_own_menu_item(client, path, href):
    nav = header(client.get(path).text)
    assert f'href="{href}" aria-current="page"' in nav


def test_homepage_shows_the_newest_guides(client):
    html = client.get("/").text
    assert 'id="reads-title">New from the guides</h2>' in html
    for piece in editorial_index.latest(6):
        assert f'href="{piece["href"]}"' in html
    assert "<!--LATEST_GUIDES-->" not in html


def test_site_map_links_every_guide(client):
    html = client.get("/site-map").text
    assert "<!--GUIDE_DIRECTORY-->" not in html
    for piece in editorial_index.entries():
        assert f'href="{piece["href"]}"' in html
    for phrase in ("crawlers", "reviewers", "search inventory"):
        assert phrase not in html.split("<main", 1)[1]


def test_trust_pages_speak_to_readers(client):
    about = client.get("/about").text
    assert "Who runs it" in about and "written with AI assistance" in about and "ko-fi.com/omnitrackr" in about
    standards = client.get("/content-quality")
    assert "<h1>Editorial Standards</h1>" in standards.text
    assert 'content="index, follow' in standards.text and "x-robots-tag" not in standards.headers
    for html in (about, standards.text):
        main = html.split("<main", 1)[1]
        for phrase in ("robots.txt", "sitemap", "crawl", "thin app shell", "search engines", "reviewers"):
            assert phrase not in main, phrase


@pytest.mark.parametrize("path", ["/in-order/star-wars", "/if-you-liked/interstellar", "/in-order",
                                  "/if-you-liked", "/discover", "/daily"])
def test_guides_disclose_ai_assistance_without_claiming_hand_writing(client, path):
    html = client.get(path).text
    assert "Hand-written" not in html and "reviewed by the editors" not in html and "written by hand" not in html
    if path.count("/") == 2 or path == "/daily":
        assert "AI assistance" in html


def test_monthly_edition_discloses_ai_assistance(client):
    html = client.get("/discover/monthly/october-2026").text
    assert "prepared by OmniTrackr with AI assistance" in html and 'href="/content-quality"' in html


def test_daily_archive_has_its_styles_and_first_clues(client, on_day):
    on_day(3)
    html = client.get("/daily/archive").text
    assert "/static/daily.css?v=" in html
    for number in (1, 2):
        assert daily.puzzle(number)["clues"][0].replace("'", "&#x27;") in html
        assert daily.puzzle(number)["title"] not in html
    assert "About the puzzles" in html


def test_past_puzzle_links_its_guide_inside_the_spoiler(client, on_day):
    on_day(3)
    html = client.get("/daily/1").text  # Interstellar, which has an "If you liked" guide
    spoiler = html[html.index("<details data-daily-spoiler>"):html.index("</details>", html.index("<details data-daily-spoiler>"))]
    assert 'href="/if-you-liked/interstellar"' in spoiler
    assert 'href="/if-you-liked/interstellar"' not in html.replace(spoiler, "").split("<footer", 1)[0]
    assert "Tips from the editors" not in html and 'href="/daily#how-to-play"' in html
    assert 'id="how-to-play"' in client.get("/daily").text
