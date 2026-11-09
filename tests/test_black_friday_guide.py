"""Black Friday and Cyber Monday guide (/holidays/black-friday), Nov 2026."""
import re
from datetime import date
from pathlib import Path

import pytest

from app import affiliate, editorial_index, guide_links, models, title_pages, title_search
from app.deal_guides import GUIDE, PICKS, SECTIONS
from app.gift_guides import GIFTS
from app.routers import deals_guide

TAG = "omnitrackr-20"
PATH = "/holidays/black-friday"


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def tagged(monkeypatch):
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", TAG)


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter_by(username=username).one()


def _words():
    texts = GUIDE["intro"] + GUIDE["method"] + [GUIDE["calendar_intro"]]
    texts += [q + " " + a for q, a in GUIDE["faq"]]
    texts += [name + " " + text for name, text in GUIDE["checks"]]
    texts += [entry["text"] for entry in GUIDE["calendar"]]
    for section in SECTIONS:
        texts += section["intro"] + section["drops"] + section["holds"]
        texts += [pick["why"] + " " + pick["check"] for pick in section["picks"]]
    return sum(len(text.split()) for text in texts)


def test_the_guide_is_long_and_every_pick_is_complete():
    assert _words() >= 3500
    assert 60 <= len(GUIDE["summary"]) <= 260
    assert len(GUIDE["checks"]) == 5
    kinds = [kind for section in SECTIONS for kind in section["kinds"]]
    assert sorted(kinds) == sorted(title_pages.KINDS)  # every tracked format has a home
    for section in SECTIONS:
        assert re.fullmatch(r"[a-z0-9-]{1,40}", section["key"]) and section["intro"] and section["tagline"]
        assert len(section["picks"]) == 3 and len(section["drops"]) >= 2 and len(section["holds"]) >= 2
        for pick in section["picks"]:
            assert re.fullmatch(r"[a-z0-9-]{2,60}", pick["id"])
            assert pick["name"] and pick["why"] and pick["check"]
            if pick.get("search"):
                assert pick["store"] in affiliate.SEARCH_STORES
            if pick.get("link"):
                assert pick["link"][0].startswith("https://") and "amazon." not in pick["link"][0]
            if pick["kind"] is not None:
                assert pick["kind"] in title_pages.KINDS and pick["title"] and 1900 < pick["year"] < 2030
    assert len(PICKS) == sum(len(section["picks"]) for section in SECTIONS)


def test_no_pick_repeats_the_gift_guide():
    gift_titles = {(gift["kind"], gift.get("title")) for gift in GIFTS.values() if gift.get("title")}
    for pick in PICKS.values():
        assert pick["id"] not in GIFTS
        if pick.get("title"):
            assert (pick["kind"], pick["title"]) not in gift_titles, pick["id"]


def test_no_prices_in_the_writing():
    text = repr(GUIDE)
    assert not re.search(r"\$\s?\d|\d+\s?(dollars|USD)\b|£\d|€\d", text)


def test_calendar_dates_fall_on_the_right_days():
    days = {entry["name"]: date.fromisoformat(entry["date"]) for entry in GUIDE["calendar"]}
    assert days["Black Friday"] == date(2026, 11, 27) and days["Black Friday"].weekday() == 4
    assert days["Cyber Monday"] == date(2026, 11, 30) and days["Cyber Monday"].weekday() == 0
    assert days["Thanksgiving"].weekday() == 3 and days["Small Business Saturday"].weekday() == 5
    assert deals_guide.BLACK_FRIDAY == "2026-11-27" and deals_guide.CYBER_MONDAY == "2026-11-30"


def test_guide_reads_without_an_account_and_carries_the_disclosure(client, tagged):
    response = client.get(PATH)
    assert response.status_code == 200
    html = response.text
    assert "<h1>" in html and GUIDE["headline"] in html
    assert html.count('class="gg-gift bf-pick"') == len(PICKS)
    searches = sum(1 for pick in PICKS.values() if pick.get("search"))
    assert html.count('rel="sponsored noopener noreferrer"') == searches
    assert f"tag={TAG}" in html and html.index("As an Amazon Associate") < html.index("amazon.com/s?")
    assert "recordstoreday.com/SpecialReleases" in html
    assert '"FAQPage"' in html and '"ItemList"' in html
    assert "/?next=%2Fholidays%2Fblack-friday#signup" in html and "Your list for the sales" not in html
    assert "/static/ad-loader.js" in html and "/static/deals-guide.css" in html
    assert 'href="/holidays/gifts"' in html and 'href="/holidays"' in html
    assert "Cookie" in response.headers["vary"]


def test_without_a_tag_the_guide_has_no_shop_links(client, monkeypatch):
    monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
    html = client.get(PATH).text
    assert "amazon.com" not in html and "As an Amazon Associate" not in html
    assert html.count('class="gg-gift bf-pick"') == len(PICKS)


def test_members_see_their_own_list_and_their_formats_first(authenticated_client, db_session, tagged):
    user = _user(db_session)
    for number in range(3):
        db_session.add(models.Manga(user_id=user.id, title=f"Series {number}", author="Someone", read=False))
    db_session.add(models.Book(user_id=user.id, title="Loved <Book>", author="An Author", year=2001, read=True, rating=9))
    db_session.commit()
    before = db_session.query(models.GiftList).count()
    html = authenticated_client.get(PATH).text
    assert "Your list for the sales" in html and "/static/ad-loader.js" not in html
    assert "Series 2" in html and "Loved &lt;Book&gt;" in html and "<Book>" not in html
    assert "Sorted for you" in html
    sections = re.findall(r'<section class="sn-shelf bf-section" id="([a-z-]+)"', html)
    assert sections[0] == "manga" and sorted(sections) == sorted(section["key"] for section in SECTIONS)
    assert "library_category=manga&amp;library_item=" in html
    assert html.count("bf-mine__buy") == 4
    # Reading the page never makes a gift list or changes the library.
    assert db_session.query(models.GiftList).count() == before


def test_a_member_with_an_empty_library_gets_a_hint(authenticated_client):
    html = authenticated_client.get(PATH).text
    assert "Your list for the sales" in html and "Open your library" in html


@pytest.mark.parametrize("today, expected", [
    (date(2026, 11, 9), "18 days to Black Friday"),
    (date(2026, 11, 26), "1 day to Black Friday"),
    (date(2026, 11, 27), "It's Black Friday today"),
    (date(2026, 11, 28), "Cyber Monday is on November 30"),
    (date(2026, 11, 30), "It's Cyber Monday today"),
    (date(2026, 12, 5), ""),
])
def test_countdown(today, expected):
    assert deals_guide.countdown(today) == expected


def test_calendar_marks_the_current_day():
    def now(today):
        html = deals_guide._calendar(today)
        found = re.findall(r'<li class="[^"]*bf-day--now[^"]*">.*?<h3>([^<]+)</h3>', html)
        return found[0] if found else None
    assert now(date(2026, 11, 9)) is None
    assert now(date(2026, 11, 24)) == "The early week"
    assert now(date(2026, 11, 27)) == "Black Friday"
    assert now(date(2026, 11, 29)) == "Small Business Saturday"
    assert now(date(2026, 12, 3)) is None
    assert now(date(2026, 12, 20)) == "Steam Winter Sale"


def test_the_guide_is_linked_from_the_hub_sitemap_index_and_loader(client):
    assert f'href="{PATH}"' in client.get("/holidays").text
    assert f"https://omnitrackr.xyz{PATH}</loc>" in client.get("/sitemap.xml").text
    assert any(piece["href"] == PATH for piece in editorial_index.entries())
    assert guide_links._source("seasonal", PATH) is GUIDE
    assert PATH in client.get("/llms.txt").text
    root = Path(__file__).parents[1] / "app" / "static"
    assert "gifts|black-friday|" in (root / "ad-loader.js").read_text(encoding="utf-8")
    assert "holidays\\/(?:gifts|black-friday)" in (root / "auth.js").read_text(encoding="utf-8")
